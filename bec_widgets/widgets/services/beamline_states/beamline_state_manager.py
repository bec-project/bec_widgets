from __future__ import annotations

import sys
from typing import Any

from bec_lib import bl_states, messages
from bec_lib.endpoints import MessageEndpoints
from bec_qthemes import material_icon
from qtpy.QtCore import QAbstractListModel, QModelIndex, QSize, Qt
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListView,
    QMessageBox,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.widgets.services.beamline_states.beamline_state_pill import BeamlineStatePill
from bec_widgets.widgets.services.beamline_states.dialogs import (
    AddBeamlineStateDialog,
    DeviceFilterDialog,
    StatusFilterDialog,
)


class _BeamlineStateListModel(QAbstractListModel):
    """Model owning beamline state row identity and configuration data."""

    NameRole = Qt.ItemDataRole.UserRole + 1
    ConfigRole = Qt.ItemDataRole.UserRole + 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state_order: list[str] = []
        self._state_rows: dict[str, int] = {}
        self._state_configs: dict[str, messages.BeamlineStateConfig] = {}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._state_order)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._state_order):
            return None
        name = self._state_order[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, self.NameRole):
            return name
        if role == self.ConfigRole:
            return self._state_configs.get(name)
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def set_states(self, state_configs: list[messages.BeamlineStateConfig]) -> None:
        new_order = [state.name for state in state_configs]
        new_configs = {state.name: state for state in state_configs}

        for row in reversed(
            [row for row, name in enumerate(self._state_order) if name not in new_configs]
        ):
            self.beginRemoveRows(QModelIndex(), row, row)
            name = self._state_order.pop(row)
            self._state_configs.pop(name, None)
            self.endRemoveRows()
        self._rebuild_rows()

        for target_row, name in enumerate(new_order):
            if name not in self._state_rows:
                self.beginInsertRows(QModelIndex(), target_row, target_row)
                self._state_order.insert(target_row, name)
                self._state_configs[name] = new_configs[name]
                self.endInsertRows()
                self._rebuild_rows()
                continue

            current_row = self._state_rows[name]
            if current_row != target_row:
                destination_row = target_row if current_row > target_row else target_row + 1
                self.beginMoveRows(
                    QModelIndex(), current_row, current_row, QModelIndex(), destination_row
                )
                self._state_order.insert(target_row, self._state_order.pop(current_row))
                self.endMoveRows()
                self._rebuild_rows()

            if self._state_configs.get(name) != new_configs[name]:
                self._state_configs[name] = new_configs[name]
                index = self.index(self._state_rows[name], 0)
                self.dataChanged.emit(index, index, [self.ConfigRole])

    def _rebuild_rows(self) -> None:
        self._state_rows = {name: row for row, name in enumerate(self._state_order)}

    def index_for_name(self, name: str) -> QModelIndex:
        row = self._state_rows.get(name)
        if row is None:
            return QModelIndex()
        return self.index(row, 0)


class _BeamlineStatePillDelegate(QStyledItemDelegate):
    """Delegate that provides BeamlineStatePill persistent editors for list rows."""

    def __init__(self, manager: "BeamlineStateManager") -> None:
        super().__init__(manager)
        self._manager = manager

    def paint(self, _painter, _option: QStyleOptionViewItem, _index: QModelIndex) -> None:
        return

    def createEditor(  # noqa: N802
        self, parent: QWidget, _option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget:
        name = index.data(_BeamlineStateListModel.NameRole)
        state_config = index.data(_BeamlineStateListModel.ConfigRole)
        pill = BeamlineStatePill(parent=parent, state_name=name, client=self._manager.client)
        pill.idle_card_background = self._manager.idle_card_background
        pill.set_state_config(state_config)
        pill.state_changed.connect(self._manager._on_pill_state_changed)
        pill.update_requested.connect(self._manager._update_state_parameters)
        pill.remove_requested.connect(self._manager._remove_state_requested)
        pill.row_height_changed.connect(lambda name=name: self._manager._sync_pill_item_size(name))
        self._manager._state_pills[str(name)] = pill
        return pill

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:  # noqa: N802
        if not isinstance(editor, BeamlineStatePill):
            return
        name = index.data(_BeamlineStateListModel.NameRole)
        state_config = index.data(_BeamlineStateListModel.ConfigRole)
        editor.set_state_name(str(name))
        editor.idle_card_background = self._manager.idle_card_background
        editor.set_state_config(state_config)

    def updateEditorGeometry(  # noqa: N802
        self, editor: QWidget, option: QStyleOptionViewItem, _index: QModelIndex
    ) -> None:
        editor.setGeometry(option.rect)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        name = index.data(_BeamlineStateListModel.NameRole)
        pill = self._manager._state_pills.get(str(name))
        if pill is not None:
            return pill.sizeHint()
        return QSize(120, 58)

    def destroyEditor(self, editor: QWidget, index: QModelIndex) -> None:  # noqa: N802
        if isinstance(editor, BeamlineStatePill):
            name = editor.state_name
            if name and self._manager._state_pills.get(name) is editor:
                self._manager._state_pills.pop(name, None)
            editor.cleanup()
        super().destroyEditor(editor, index)


class _BeamlineStateListView(QListView):
    """List view using persistent pill editors."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("beamline_state_pill_view")
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QListView.Shape.NoFrame)
        self.setSpacing(6)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(
            "QListView#beamline_state_pill_view {"
            "background: transparent;"
            "border: none;"
            "}"
            "QListView#beamline_state_pill_view::item {"
            "background: transparent;"
            "border: none;"
            "padding: 0;"
            "}"
            "QListView#beamline_state_pill_view::item:selected {"
            "background: transparent;"
            "border: none;"
            "}"
        )


class BeamlineStateManager(BECWidget, QWidget):
    """
    Widget displaying and managing all BEC beamline states.

    The manager subscribes to ``MessageEndpoints.available_beamline_states()`` and creates,
    updates, or removes child ``BeamlineStatePill`` widgets as the set of configured states changes.
    """

    PLUGIN = True
    ICON_NAME = "format_list_bulleted"
    USER_ACCESS = [
        "clear_filters",
        "collapse_all",
        "state_summary",
        "remove",
        "attach",
        "detach",
        "screenshot",
    ]

    def __init__(
        self,
        parent: QWidget | None = None,
        client=None,
        config: ConnectionConfig | None = None,
        gui_id: str | None = None,
        idle_card_background: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(
            parent=parent, client=client, config=config, gui_id=gui_id, theme_update=True, **kwargs
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._state_pills: dict[str, BeamlineStatePill] = {}
        self._state_configs: dict[str, messages.BeamlineStateConfig] = {}
        self._state_order: list[str] = []
        self._selected_statuses: set[str] | None = None
        self._selected_devices: set[str] | None = None
        self._device_filter_text = ""
        self._hidden_expanded = False
        self._idle_card_background = False
        self.idle_card_background = idle_card_background

        self._empty_label = QLabel(
            "No beamline states available.\n Add new state from toolbar or CLI.", self
        )
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._toolbar = self._create_toolbar()
        self._model = _BeamlineStateListModel(self)
        self._view = _BeamlineStateListView(self)
        self._delegate = _BeamlineStatePillDelegate(self)
        self._view.setModel(self._model)
        self._view.setItemDelegate(self._delegate)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._empty_label)
        layout.addWidget(self._view, 1)
        self._hidden_summary = QToolButton(self)
        self._hidden_summary.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._hidden_summary.setCheckable(True)
        self._hidden_summary.toggled.connect(self._toggle_hidden_states)
        layout.addWidget(self._hidden_summary)
        self.setLayout(layout)

        self.bec_dispatcher.connect_slot(
            self.update_available_states, MessageEndpoints.available_beamline_states()
        )
        self.refresh_states()
        self._refresh_hidden_summary()

    @SafeProperty(bool, default=False)
    def idle_card_background(self) -> bool:
        """
        Whether idle collapsed pills keep the status-tinted card background.
        """
        return self._idle_card_background

    @idle_card_background.setter
    def idle_card_background(self, enabled: bool) -> None:
        self._idle_card_background = enabled
        for pill in self._state_pills.values():
            pill.idle_card_background = self._idle_card_background

    def set_idle_card_background(self, enabled: bool) -> None:
        """Set whether idle collapsed pills keep the status-tinted card background."""
        self.idle_card_background = enabled

    def _create_toolbar(self) -> ModularToolBar:
        toolbar = ModularToolBar(parent=self)

        add_state = MaterialIconAction("add", "Add beamline state", filled=True, parent=self)
        filter_states = MaterialIconAction(
            "filter_alt", "Filter displayed state status", filled=True, parent=self
        )
        filter_devices = MaterialIconAction(
            "devices", "Filter displayed devices", filled=True, parent=self
        )
        clear_filters = MaterialIconAction(
            "filter_alt_off", "Clear beamline state filters", filled=True, parent=self
        )
        collapse_all = MaterialIconAction(
            "collapse_all", "Collapse all states", filled=True, parent=self
        )

        add_state.action.triggered.connect(self.open_add_state_dialog)
        filter_states.action.triggered.connect(self.open_status_filter_dialog)
        filter_devices.action.triggered.connect(self.open_device_filter_dialog)
        clear_filters.action.triggered.connect(self.clear_filters)
        collapse_all.action.triggered.connect(self.collapse_all)

        toolbar.components.add_safe("add_state", add_state)
        toolbar.components.add_safe("filter_states", filter_states)
        toolbar.components.add_safe("filter_devices", filter_devices)
        toolbar.components.add_safe("clear_filters", clear_filters)
        toolbar.components.add_safe("collapse_all", collapse_all)

        bundle = ToolbarBundle("beamline_state_manager", toolbar.components)
        bundle.add_action("add_state")
        bundle.add_action("filter_states")
        bundle.add_action("filter_devices")
        bundle.add_action("clear_filters")
        bundle.add_action("collapse_all")
        toolbar.add_bundle(bundle)
        toolbar.show_bundles(["beamline_state_manager"])
        return toolbar

    @SafeSlot(str)
    def apply_theme(self, _theme: str) -> None:
        colors = BeamlineStatePill._state_colors("unknown")
        self.setStyleSheet(
            "BeamlineStateManager { border: none; }"
            "QToolButton#hidden_states_summary {"
            f"background-color: {colors['background']};"
            f"border: 1px solid {colors['border']};"
            "border-radius: 6px;"
            "padding: 6px;"
            "text-align: left;"
            "}"
        )
        for pill in self._state_pills.values():
            pill.apply_theme(_theme)
        self._refresh_hidden_summary()

    @SafeSlot()
    def open_add_state_dialog(self) -> None:
        dialog = AddBeamlineStateDialog(self, client=self.client)
        config = None
        try:
            accepted = dialog.exec() == QDialog.Accepted
            if accepted:
                config = dialog.config_result
        finally:
            dialog.cleanup()
            dialog.deleteLater()

        if config is None:
            return
        try:
            self.client.beamline_states.add(config)
        except Exception as exc:
            QMessageBox.warning(self, "Cannot Add State", str(exc))

    @SafeSlot()
    def open_status_filter_dialog(self) -> None:
        dialog = StatusFilterDialog(self._selected_statuses, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self._selected_statuses = dialog.selected_statuses()
        self._apply_filters()

    @SafeSlot()
    def open_device_filter_dialog(self) -> None:
        devices = sorted(
            {
                device
                for state in self._state_configs.values()
                if (device := self._state_device(state)) is not None
            }
        )
        dialog = DeviceFilterDialog(devices, self._selected_devices, self._device_filter_text, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self._selected_devices = dialog.selected_devices()
        self._device_filter_text = dialog.filter_text()
        self._apply_filters()

    @SafeSlot()
    def clear_filters(self) -> None:
        self._selected_statuses = None
        self._selected_devices = None
        self._device_filter_text = ""
        self._hidden_expanded = False
        self._apply_filters()

    @SafeSlot()
    def collapse_all(self) -> None:
        """Collapse the settings panel of all displayed state pills."""
        for pill in self._state_pills.values():
            pill.set_expanded(False)

    def state_summary(self) -> dict[str, dict[str, str]]:
        """
        Return all beamline states (including filtered ones) with their current status and label.

        Returns:
            dict: Mapping of state name to a dictionary with ``status`` and ``label`` keys.
        """

        return {
            name: {"status": pill._status, "label": pill._label}
            for name, pill in self._state_pills.items()
        }

    @SafeSlot()
    def refresh_states(self) -> None:
        """Fetch the latest cached available beamline states and update the list immediately."""
        msg = self.client.connector.get_last(
            MessageEndpoints.available_beamline_states(), key="data"
        )
        if msg is not None:
            self.update_available_states(msg.content, msg.metadata)

    @SafeSlot(dict, dict)
    def update_available_states(
        self, content: dict[str, Any], _metadata: dict[str, Any] | None = None
    ) -> None:
        """Update the displayed pills from ``AvailableBeamlineStatesMessage`` content."""
        expanded_names = {name for name, pill in self._state_pills.items() if pill.is_expanded()}
        state_configs: list[messages.BeamlineStateConfig] = content.get("states", [])
        if state_configs == list(self._state_configs.values()):
            self._apply_filters()
            return
        self._state_configs = {state.name: state for state in state_configs}
        self._state_order = [state.name for state in state_configs]
        self._model.set_states(state_configs)
        self._open_persistent_editors(expanded_names)
        self._apply_filters()

    def _open_persistent_editors(self, expanded_names: set[str] | None = None) -> None:
        expanded_names = expanded_names or set()
        for row in range(self._model.rowCount()):
            index = self._model.index(row, 0)
            self._view.openPersistentEditor(index)
            name = str(index.data(_BeamlineStateListModel.NameRole))
            pill = self._state_pills.get(name)
            if pill is not None:
                pill.set_expanded(name in expanded_names)
                self._sync_pill_item_size(name)

    def _apply_filters(self) -> None:
        visible_names = []
        hidden_names = []
        for name in self._state_order:
            if self._is_state_visible(name):
                visible_names.append(name)
            else:
                hidden_names.append(name)

        visible_set = set(visible_names)
        show_hidden = self._hidden_expanded and bool(hidden_names)
        for row, name in enumerate(self._state_order):
            hidden_by_filter = name not in visible_set
            self._view.setRowHidden(row, hidden_by_filter and not show_hidden)
            self._sync_pill_item_size(name)
        self._empty_label.setVisible(
            not visible_names and not (self._hidden_expanded and hidden_names)
        )
        self._view.setVisible(bool(visible_names) or (self._hidden_expanded and bool(hidden_names)))
        self._refresh_hidden_summary(hidden_count=len(hidden_names))

    def _sync_pill_item_size(self, name: str) -> None:
        index = self._model.index_for_name(name)
        if not index.isValid():
            return
        self._model.dataChanged.emit(index, index, [Qt.ItemDataRole.SizeHintRole])
        self._view.update(index)

    def _is_state_visible(self, name: str) -> bool:
        pill = self._state_pills.get(name)
        if self._selected_statuses is not None and (
            pill is None or pill._status not in self._selected_statuses
        ):
            return False

        device = self._state_device(self._state_configs.get(name))
        if self._selected_devices is not None and device not in self._selected_devices:
            return False

        tokens = [
            token.strip().casefold()
            for token in self._device_filter_text.split(",")
            if token.strip()
        ]
        if tokens:
            if device is None:
                return False
            device_lower = device.casefold()
            if not any(token in device_lower for token in tokens):
                return False
        return True

    @SafeSlot(str, str, str)
    def _on_pill_state_changed(self, _name: str, _status: str, _label: str) -> None:
        if self._selected_statuses is not None:
            self._apply_filters()

    @SafeSlot(str, object)
    def _update_state_parameters(
        self, state_name: str, config: bl_states.BeamlineStateConfig
    ) -> None:
        state_client = getattr(self.client.beamline_states, state_name, None)
        if state_client is None:
            QMessageBox.warning(
                self, "Cannot Update State", f"Beamline state '{state_name}' is not available."
            )
            return
        try:
            state_client.update_parameters(**config.model_dump(exclude={"name"}))
        except Exception as exc:
            QMessageBox.warning(self, "Cannot Update State", str(exc))
            return
        pill = self._state_pills.get(state_name)
        if pill is not None:
            pill.mark_current_settings_clean()

    @SafeSlot(str)
    def _remove_state_requested(self, state_name: str) -> None:
        reply = QMessageBox.question(
            self,
            "Remove Beamline State",
            f"Remove beamline state '{state_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.client.beamline_states.delete(state_name)
        except Exception as exc:
            QMessageBox.warning(self, "Cannot Remove State", str(exc))

    @SafeSlot(bool)
    def _toggle_hidden_states(self, checked: bool) -> None:
        self._hidden_expanded = bool(checked)
        self._apply_filters()

    def _refresh_hidden_summary(self, hidden_count: int | None = None) -> None:
        if hidden_count is None:
            hidden_count = sum(1 for name in self._state_order if not self._is_state_visible(name))
        self._hidden_summary.setObjectName("hidden_states_summary")
        self._hidden_summary.setVisible(hidden_count > 0)
        self._hidden_summary.setChecked(self._hidden_expanded and hidden_count > 0)
        icon_name = "expand_less" if self._hidden_expanded else "expand_more"
        self._hidden_summary.setIcon(material_icon(icon_name, convert_to_pixmap=False))
        suffix = "state is" if hidden_count == 1 else "states are"
        action = "Hide" if self._hidden_expanded else "Show"
        self._hidden_summary.setText(
            f"{hidden_count} {suffix} hidden by filters. {action} hidden states."
        )

    @staticmethod
    def _state_device(state: messages.BeamlineStateConfig | None) -> str | None:
        device = state.parameters.get("device") if state is not None else None
        return str(device) if device else None

    def cleanup(self) -> None:
        self.bec_dispatcher.disconnect_slot(
            self.update_available_states, MessageEndpoints.available_beamline_states()
        )
        for row in range(self._model.rowCount()):
            self._view.closePersistentEditor(self._model.index(row, 0))
        for pill in list(self._state_pills.values()):
            pill.cleanup()
            pill.deleteLater()
        self._state_pills.clear()
        self._toolbar.components.cleanup()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)

    from bec_widgets.utils.colors import apply_theme
    from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

    apply_theme("dark")

    window = QWidget()
    window.setWindowTitle("Beamline States")
    layout = QVBoxLayout(window)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    theme_row = QHBoxLayout()
    theme_row.addStretch(1)
    theme_row.addWidget(DarkModeButton(parent=window))
    layout.addLayout(theme_row)
    layout.addWidget(BeamlineStateManager(parent=window), 1)

    window.resize(760, 480)
    window.show()
    sys.exit(app.exec())
