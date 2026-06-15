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
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.toolbars.actions import MaterialIconAction, WidgetAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.widgets.services.beamline_states.beamline_state_pill import BeamlineStatePill
from bec_widgets.widgets.services.beamline_states.dialogs import (
    AddBeamlineStateDialog,
    DeviceFilterDialog,
    StatusFilterDialog,
)


class _BeamlineStateListModel(QAbstractListModel):
    """
    Model owning beamline state row identity, configuration data, and section headers.

    Rows are identified by ``("state", name)`` or ``("header", kind)`` keys so state rows and
    section header rows share one diff-based update path.
    """

    NameRole = Qt.ItemDataRole.UserRole + 1
    ConfigRole = Qt.ItemDataRole.UserRole + 2
    HeaderRole = Qt.ItemDataRole.UserRole + 3

    INTERLOCK_HEADER = "interlock"
    OTHERS_HEADER = "others"
    HEADER_LABELS = {
        INTERLOCK_HEADER: "Scan interlock states",
        OTHERS_HEADER: "Not included in scan interlock",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._row_keys: list[tuple[str, str]] = []
        self._row_indices: dict[tuple[str, str], int] = {}
        self._state_configs: dict[str, messages.BeamlineStateConfig] = {}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._row_keys)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._row_keys):
            return None
        kind, value = self._row_keys[index.row()]
        if kind == "header":
            if role == Qt.ItemDataRole.DisplayRole:
                return self.HEADER_LABELS[value]
            if role == self.HeaderRole:
                return value
            return None
        if role in (Qt.ItemDataRole.DisplayRole, self.NameRole):
            return value
        if role == self.ConfigRole:
            return self._state_configs.get(value)
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid() or not 0 <= index.row() < len(self._row_keys):
            return Qt.ItemFlag.NoItemFlags
        if self._row_keys[index.row()][0] == "header":
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def set_states(
        self, state_configs: list[messages.BeamlineStateConfig], interlock_names: set[str]
    ) -> None:
        # Ordering comes from ``state_configs``; ``interlock_names`` is only a membership set.
        new_configs = {state.name: state for state in state_configs}
        interlock = [name for name in new_configs if name in interlock_names]
        others = [name for name in new_configs if name not in interlock_names]

        new_keys: list[tuple[str, str]] = []
        if interlock:
            new_keys.append(("header", self.INTERLOCK_HEADER))
            new_keys.extend(("state", name) for name in interlock)
            if others:
                new_keys.append(("header", self.OTHERS_HEADER))
        new_keys.extend(("state", name) for name in others)
        new_key_set = set(new_keys)

        for row in reversed(
            [row for row, key in enumerate(self._row_keys) if key not in new_key_set]
        ):
            self.beginRemoveRows(QModelIndex(), row, row)
            kind, value = self._row_keys.pop(row)
            if kind == "state":
                self._state_configs.pop(value, None)
            self.endRemoveRows()
        self._rebuild_rows()

        for target_row, key in enumerate(new_keys):
            if key not in self._row_indices:
                self.beginInsertRows(QModelIndex(), target_row, target_row)
                self._row_keys.insert(target_row, key)
                if key[0] == "state":
                    self._state_configs[key[1]] = new_configs[key[1]]
                self.endInsertRows()
                self._rebuild_rows()
                continue

            current_row = self._row_indices[key]
            if current_row != target_row:
                destination_row = target_row if current_row > target_row else target_row + 1
                self.beginMoveRows(
                    QModelIndex(), current_row, current_row, QModelIndex(), destination_row
                )
                self._row_keys.insert(target_row, self._row_keys.pop(current_row))
                self.endMoveRows()
                self._rebuild_rows()

            if key[0] == "state" and self._state_configs.get(key[1]) != new_configs[key[1]]:
                self._state_configs[key[1]] = new_configs[key[1]]
                index = self.index(self._row_indices[key], 0)
                self.dataChanged.emit(index, index, [self.ConfigRole])

    def _rebuild_rows(self) -> None:
        self._row_indices = {key: row for row, key in enumerate(self._row_keys)}

    def index_for_name(self, name: str) -> QModelIndex:
        row = self._row_indices.get(("state", name))
        if row is None:
            return QModelIndex()
        return self.index(row, 0)


class _BeamlineStateSectionHeader(QWidget):
    """Section header row (icon + label + rule line) shown above each state group."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("beamline_state_section_header")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._icon = QLabel(self)
        self._label = QLabel(self)
        self._label.setObjectName("beamline_state_section_label")
        self._rule = QWidget(self)
        self._rule.setObjectName("beamline_state_section_rule")
        self._rule.setFixedHeight(1)
        self._rule.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)
        layout.addWidget(self._icon)
        layout.addWidget(self._label)
        layout.addWidget(self._rule, 1, Qt.AlignmentFlag.AlignVCenter)

    def set_header(self, *, icon_name: str, text: str, color: str, filled: bool, rule: str) -> None:
        self._icon.setPixmap(material_icon(icon_name, size=(14, 14), color=color, filled=filled))
        self._label.setText(text)
        self.setStyleSheet(
            "QLabel#beamline_state_section_label {"
            f"color: {color};"
            "font-weight: 700;"
            "font-size: 11px;"
            "}"
            "QWidget#beamline_state_section_rule {"
            f"background-color: {rule};"
            "}"
        )


class _BeamlineStatePillDelegate(QStyledItemDelegate):
    """Delegate providing persistent editors: a pill for state rows, a header widget for headers."""

    HEADER_HEIGHT = 26

    def __init__(self, manager: "BeamlineStateManager") -> None:
        super().__init__(manager)
        self._manager = manager

    def paint(self, _painter, _option: QStyleOptionViewItem, _index: QModelIndex) -> None:
        # Every row is rendered by its persistent editor widget (pill or section header),
        # so the delegate itself paints nothing.
        return

    def createEditor(  # noqa: N802
        self, parent: QWidget, _option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget:
        kind = index.data(_BeamlineStateListModel.HeaderRole)
        if kind is not None:
            header = _BeamlineStateSectionHeader(parent)
            self._manager._section_headers[str(kind)] = header
            return header

        name = index.data(_BeamlineStateListModel.NameRole)
        state_config = index.data(_BeamlineStateListModel.ConfigRole)
        pill = BeamlineStatePill(parent=parent, state_name=name, client=self._manager.client)
        pill.set_state_config(state_config)
        pill.state_changed.connect(self._manager._on_pill_state_changed)
        pill.update_requested.connect(self._manager._update_state_parameters)
        pill.remove_requested.connect(self._manager._remove_state_requested)
        pill.scan_interlock_toggle_requested.connect(self._manager._on_interlock_toggle_requested)
        pill.row_height_changed.connect(lambda name=name: self._manager._sync_pill_item_size(name))
        self._manager._state_pills[str(name)] = pill
        return pill

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:  # noqa: N802
        kind = index.data(_BeamlineStateListModel.HeaderRole)
        if isinstance(editor, _BeamlineStateSectionHeader):
            self._manager._apply_section_header(editor, str(kind))
            return
        if not isinstance(editor, BeamlineStatePill):
            return
        name = index.data(_BeamlineStateListModel.NameRole)
        state_config = index.data(_BeamlineStateListModel.ConfigRole)
        editor.set_state_name(str(name))
        editor.set_state_config(state_config)

    def updateEditorGeometry(  # noqa: N802
        self, editor: QWidget, option: QStyleOptionViewItem, _index: QModelIndex
    ) -> None:
        editor.setGeometry(option.rect)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        if index.data(_BeamlineStateListModel.HeaderRole) is not None:
            return QSize(120, self.HEADER_HEIGHT)
        name = index.data(_BeamlineStateListModel.NameRole)
        pill = self._manager._state_pills.get(str(name))
        if pill is not None:
            return pill.sizeHint()
        return QSize(120, 58)

    def destroyEditor(self, editor: QWidget, index: QModelIndex) -> None:  # noqa: N802
        if isinstance(editor, _BeamlineStateSectionHeader):
            for kind, header in list(self._manager._section_headers.items()):
                if header is editor:
                    self._manager._section_headers.pop(kind, None)
        elif isinstance(editor, BeamlineStatePill):
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
    _STATUS_PRIORITY = {"invalid": 0, "warning": 1, "valid": 2, "unknown": 3}
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
        **kwargs,
    ) -> None:
        super().__init__(
            parent=parent, client=client, config=config, gui_id=gui_id, theme_update=True, **kwargs
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._state_pills: dict[str, BeamlineStatePill] = {}
        self._section_headers: dict[str, _BeamlineStateSectionHeader] = {}
        self._state_configs: dict[str, messages.BeamlineStateConfig] = {}
        self._state_order: list[str] = []
        self._selected_statuses: set[str] | None = None
        self._selected_devices: set[str] | None = None
        self._device_filter_text = ""
        self._hidden_expanded = False
        self._scan_interlock = self.client.builtin_actors.scan_interlock
        self._interlock_enabled = False
        self._interlock_states: dict[str, list[str]] = {}
        self._pending_interlock_statuses: dict[str, list[str]] = {}
        self._updating_interlock_action = False
        self._interlock_action_armed: bool | None = None

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
        self.bec_dispatcher.connect_slot(
            self._refresh_scan_interlock,
            MessageEndpoints.builtin_actor_update_notif("ScanInterlockActor"),
        )
        self._refresh_scan_interlock()
        self.refresh_states()
        self._refresh_hidden_summary()

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
        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        spacer_action = WidgetAction(widget=spacer, adjust_size=False, parent=self)
        scan_interlock = MaterialIconAction(
            "no_encryption",
            "Scan interlock",
            checkable=True,
            filled=True,
            label_text="Scan interlock",
            text_position="beside",
            parent=self,
        )

        add_state.action.triggered.connect(self.open_add_state_dialog)
        filter_states.action.triggered.connect(self.open_status_filter_dialog)
        filter_devices.action.triggered.connect(self.open_device_filter_dialog)
        clear_filters.action.triggered.connect(self.clear_filters)
        collapse_all.action.triggered.connect(self.collapse_all)
        scan_interlock.action.toggled.connect(self._on_interlock_action_toggled)

        toolbar.components.add_safe("add_state", add_state)
        toolbar.components.add_safe("filter_states", filter_states)
        toolbar.components.add_safe("filter_devices", filter_devices)
        toolbar.components.add_safe("clear_filters", clear_filters)
        toolbar.components.add_safe("collapse_all", collapse_all)
        toolbar.components.add_safe("scan_interlock_spacer", spacer_action)
        toolbar.components.add_safe("scan_interlock", scan_interlock)

        bundle = ToolbarBundle("beamline_state_manager", toolbar.components)
        bundle.add_action("add_state")
        bundle.add_action("filter_states")
        bundle.add_action("filter_devices")
        bundle.add_action("clear_filters")
        bundle.add_action("collapse_all")
        bundle.add_action("scan_interlock_spacer")
        bundle.add_separator()
        bundle.add_action("scan_interlock")
        toolbar.add_bundle(bundle)
        toolbar.show_bundles(["beamline_state_manager"])
        if spacer_action.container is not None:
            spacer_action.container.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
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
        self._interlock_action_armed = None
        self._sync_interlock_action()
        self._refresh_section_headers()
        self._refresh_hidden_summary()

    @SafeSlot()
    def open_add_state_dialog(self) -> None:
        dialog = AddBeamlineStateDialog(self, client=self.client)
        config = None
        add_to_interlock = False
        interlock_statuses: list[str] = ["valid", "warning"]
        try:
            accepted = dialog.exec() == QDialog.Accepted
            if accepted:
                config = dialog.config_result
                add_to_interlock = dialog.add_to_interlock()
                interlock_statuses = dialog.interlock_statuses()
        finally:
            dialog.cleanup()
            dialog.deleteLater()

        if config is None:
            return
        try:
            self.client.beamline_states.add(config)
        except Exception as exc:
            QMessageBox.warning(self, "Cannot Add State", str(exc))
            return
        if add_to_interlock:
            try:
                self._scan_interlock.add_state_to_interlock(config.name, interlock_statuses)
            except Exception as exc:
                QMessageBox.warning(self, "Cannot Update Scan Interlock", str(exc))
        else:
            self._pending_interlock_statuses[config.name] = interlock_statuses

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
        state_configs: list[messages.BeamlineStateConfig] = content.get("states", [])
        self._state_configs = {state.name: state for state in state_configs}
        self._state_order = [state.name for state in state_configs]
        self._refresh_view()

    @SafeSlot(dict, dict)
    def _refresh_scan_interlock(
        self, _content: dict[str, Any] | None = None, _metadata: dict[str, Any] | None = None
    ) -> None:
        """Re-read the scan-interlock state from BEC and refresh the displayed pills."""
        try:
            self._interlock_enabled = bool(self._scan_interlock.enabled)
            self._interlock_states = dict(self._scan_interlock.states_watched)
        except Exception as exc:
            QMessageBox.warning(self, "Scan Interlock Unavailable", str(exc))
            return
        self._refresh_view()

    def _refresh_view(self) -> None:
        """Render the current state and scan-interlock bookkeeping in one pass."""
        self._sync_interlock_action()
        expanded_names = {name for name, pill in self._state_pills.items() if pill.is_expanded()}
        # Both sections are ordered by status severity (invalid, warning, unknown, valid). The
        # sort is stable, so the configured order is kept within each status.
        ordered_names = sorted(self._state_order, key=self._status_rank)
        state_configs = [self._state_configs[name] for name in ordered_names]
        self._model.set_states(state_configs, set(self._interlock_states))
        self._open_persistent_editors(expanded_names)
        for name, pill in self._state_pills.items():
            self._apply_interlock_to_pill(name, pill)
        self._refresh_section_headers()
        self._apply_filters()

    def _sync_interlock_action(self) -> None:
        action = self._toolbar.components.get_action("scan_interlock").action
        self._updating_interlock_action = True
        try:
            action.setChecked(self._interlock_enabled)
        finally:
            self._updating_interlock_action = False
        if self._interlock_enabled == self._interlock_action_armed:
            return
        self._interlock_action_armed = self._interlock_enabled
        if self._interlock_enabled:
            action.setIcon(
                material_icon(
                    "lock",
                    size=(20, 20),
                    filled=True,
                    color=get_accent_colors().success.name(),
                    convert_to_pixmap=False,
                )
            )
            action.setToolTip("Scan interlock is armed. Click to disable it.")
        else:
            action.setIcon(
                material_icon("no_encryption", size=(20, 20), filled=True, convert_to_pixmap=False)
            )
            action.setToolTip("Scan interlock is disabled. Click to arm it.")

    def _apply_interlock_to_pill(self, name: str, pill: BeamlineStatePill) -> None:
        required_statuses = self._interlock_states.get(name)
        if required_statuses is None and name in self._pending_interlock_statuses:
            pill.set_interlock_statuses(self._pending_interlock_statuses.pop(name))
        pill.set_scan_interlock(required_statuses, self._is_interlock_triggered(name))

    def _apply_section_header(self, header: _BeamlineStateSectionHeader, kind: str) -> None:
        colors = BeamlineStatePill._state_colors("unknown")
        armed = kind == _BeamlineStateListModel.INTERLOCK_HEADER and self._interlock_enabled
        header.set_header(
            icon_name=(
                "lock" if kind == _BeamlineStateListModel.INTERLOCK_HEADER else "lock_open_right"
            ),
            text=_BeamlineStateListModel.HEADER_LABELS[kind],
            color=colors["foreground"] if armed else colors["muted"],
            filled=armed,
            rule=colors["border"],
        )

    def _refresh_section_headers(self) -> None:
        for kind, header in self._section_headers.items():
            self._apply_section_header(header, kind)

    def _is_interlock_triggered(self, name: str) -> bool:
        accepted_statuses = self._interlock_states.get(name)
        if not accepted_statuses or not self._interlock_enabled:
            return False
        status = self._state_status(name)
        return status is not None and status not in accepted_statuses

    def _status_rank(self, name: str) -> int:
        """Sort rank of a state by status severity: invalid < warning < unknown < valid."""
        return self._STATUS_PRIORITY.get(
            self._state_status(name) or "unknown", self._STATUS_PRIORITY["unknown"]
        )

    def _state_status(self, name: str) -> str | None:
        """Latest status of a state, from its live pill or the connector cache.

        The connector fallback lets the sections be ordered by status severity even on the
        first render, before the pills (and their statuses) have been created.
        """
        pill = self._state_pills.get(name)
        if pill is not None:
            return pill._status
        msg = self.client.connector.get_last(MessageEndpoints.beamline_state(name), key="data")
        if msg is None:
            return None
        return str(msg.content.get("status", "unknown")).lower()

    @SafeSlot(bool)
    def _on_interlock_action_toggled(self, checked: bool) -> None:
        if self._updating_interlock_action:
            return
        try:
            self._scan_interlock.enabled = bool(checked)
        except Exception as exc:
            QMessageBox.warning(self, "Cannot Toggle Scan Interlock", str(exc))
        self._refresh_scan_interlock()

    @SafeSlot(str, bool)
    def _on_interlock_toggle_requested(self, state_name: str, include: bool) -> None:
        try:
            if include:
                pill = self._state_pills.get(state_name)
                statuses = pill.interlock_statuses if pill is not None else ["valid", "warning"]
                self._scan_interlock.add_state_to_interlock(state_name, statuses)
            else:
                self._scan_interlock.remove_state_from_interlock(state_name)
        except Exception as exc:
            QMessageBox.warning(self, "Cannot Update Scan Interlock", str(exc))
            return
        self._refresh_scan_interlock()

    def _open_persistent_editors(self, expanded_names: set[str] | None = None) -> None:
        expanded_names = expanded_names or set()
        for row in range(self._model.rowCount()):
            index = self._model.index(row, 0)
            self._view.openPersistentEditor(index)
            if index.data(_BeamlineStateListModel.HeaderRole) is not None:
                continue
            name = str(index.data(_BeamlineStateListModel.NameRole))
            pill = self._state_pills.get(name)
            if pill is not None:
                pill.set_expanded(name in expanded_names)
                self._sync_pill_item_size(name)

    def _apply_filters(self) -> None:
        visible_names = []
        hidden_names = []
        for name in self._state_order:
            # States watched by the scan interlock are exempt from filtering.
            if name in self._interlock_states or self._is_state_visible(name):
                visible_names.append(name)
            else:
                hidden_names.append(name)

        visible_set = set(visible_names)
        show_hidden = self._hidden_expanded and bool(hidden_names)
        shown_interlock = 0
        shown_others = 0
        for row in range(self._model.rowCount()):
            index = self._model.index(row, 0)
            if index.data(_BeamlineStateListModel.HeaderRole) is not None:
                continue
            name = str(index.data(_BeamlineStateListModel.NameRole))
            shown = name in visible_set or show_hidden
            self._view.setRowHidden(row, not shown)
            if shown:
                if name in self._interlock_states:
                    shown_interlock += 1
                else:
                    shown_others += 1
            self._sync_pill_item_size(name)
        for row in range(self._model.rowCount()):
            index = self._model.index(row, 0)
            kind = index.data(_BeamlineStateListModel.HeaderRole)
            if kind is None:
                continue
            shown_count = (
                shown_interlock
                if kind == _BeamlineStateListModel.INTERLOCK_HEADER
                else shown_others
            )
            self._view.setRowHidden(row, shown_count == 0)
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
        # Status drives the per-section severity ordering (and the interlock triggered flag),
        # so any change re-renders the list.
        self._refresh_view()

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
        self.bec_dispatcher.disconnect_slot(
            self._refresh_scan_interlock,
            MessageEndpoints.builtin_actor_update_notif("ScanInterlockActor"),
        )
        for row in range(self._model.rowCount()):
            self._view.closePersistentEditor(self._model.index(row, 0))
        for pill in list(self._state_pills.values()):
            pill.cleanup()
            pill.deleteLater()
        self._state_pills.clear()
        self._section_headers.clear()
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
