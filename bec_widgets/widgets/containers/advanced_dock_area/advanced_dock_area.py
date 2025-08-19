from __future__ import annotations

import os
from typing import Literal, cast

import PySide6QtAds as QtAds
from PySide6QtAds import CDockManager, CDockWidget
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from bec_widgets import BECWidget, SafeProperty, SafeSlot
from bec_widgets.cli.rpc.rpc_widget_handler import widget_handler
from bec_widgets.utils import BECDispatcher
from bec_widgets.utils.property_editor import PropertyEditor
from bec_widgets.utils.toolbars.actions import (
    ExpandableMenuAction,
    MaterialIconAction,
    WidgetAction,
)
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.utils.widget_state_manager import WidgetStateManager
from bec_widgets.widgets.containers.advanced_dock_area.profile_utils import (
    SETTINGS_KEYS,
    is_profile_readonly,
    list_profiles,
    open_settings,
    profile_path,
    read_manifest,
    set_profile_readonly,
    write_manifest,
)
from bec_widgets.widgets.containers.advanced_dock_area.toolbar_components.workspace_actions import (
    WorkspaceConnection,
    workspace_bundle,
)
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindowNoRPC
from bec_widgets.widgets.control.device_control.positioner_box import PositionerBox
from bec_widgets.widgets.control.scan_control import ScanControl
from bec_widgets.widgets.editors.vscode.vscode import VSCodeEditor
from bec_widgets.widgets.plots.heatmap.heatmap import Heatmap
from bec_widgets.widgets.plots.image.image import Image
from bec_widgets.widgets.plots.motor_map.motor_map import MotorMap
from bec_widgets.widgets.plots.multi_waveform.multi_waveform import MultiWaveform
from bec_widgets.widgets.plots.scatter_waveform.scatter_waveform import ScatterWaveform
from bec_widgets.widgets.plots.waveform.waveform import Waveform
from bec_widgets.widgets.progress.ring_progress_bar import RingProgressBar
from bec_widgets.widgets.services.bec_queue.bec_queue import BECQueue
from bec_widgets.widgets.services.bec_status_box.bec_status_box import BECStatusBox
from bec_widgets.widgets.utility.logpanel import LogPanel
from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton


class DockSettingsDialog(QDialog):

    def __init__(self, parent: QWidget, target: QWidget):
        super().__init__(parent)
        self.setWindowTitle("Dock Settings")
        self.setModal(True)
        layout = QVBoxLayout(self)

        # Property editor
        self.prop_editor = PropertyEditor(target, self, show_only_bec=True)
        layout.addWidget(self.prop_editor)


class SaveProfileDialog(QDialog):
    """Dialog for saving workspace profiles with read-only option."""

    def __init__(self, parent: QWidget, current_name: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Save Workspace Profile")
        self.setModal(True)
        self.resize(400, 150)
        layout = QVBoxLayout(self)

        # Name input
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Profile Name:"))
        self.name_edit = QLineEdit(current_name)
        self.name_edit.setPlaceholderText("Enter profile name...")
        name_row.addWidget(self.name_edit)
        layout.addLayout(name_row)

        # Read-only checkbox
        self.readonly_checkbox = QCheckBox("Mark as read-only (cannot be overwritten or deleted)")
        layout.addWidget(self.readonly_checkbox)

        # Info label
        info_label = QLabel("Read-only profiles are protected from modification and deletion.")
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.save_btn = QPushButton("Save")
        self.save_btn.setDefault(True)
        cancel_btn = QPushButton("Cancel")
        self.save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        # Enable/disable save button based on name input
        self.name_edit.textChanged.connect(self._update_save_button)
        self._update_save_button()

    def _update_save_button(self):
        """Enable save button only when name is not empty."""
        self.save_btn.setEnabled(bool(self.name_edit.text().strip()))

    def get_profile_name(self) -> str:
        """Get the entered profile name."""
        return self.name_edit.text().strip()

    def is_readonly(self) -> bool:
        """Check if the profile should be marked as read-only."""
        return self.readonly_checkbox.isChecked()


class AdvancedDockArea(BECWidget, QWidget):
    RPC = True
    PLUGIN = False
    USER_ACCESS = [
        "new",
        "widget_map",
        "widget_list",
        "lock_workspace",
        "attach_all",
        "delete_all",
        "mode",
        "mode.setter",
    ]

    # Define a signal for mode changes
    mode_changed = Signal(str)

    def __init__(
        self,
        parent=None,
        mode: str = "developer",
        default_add_direction: Literal["left", "right", "top", "bottom"] = "right",
        *args,
        **kwargs,
    ):
        super().__init__(parent=parent, *args, **kwargs)

        # Title (as a top-level QWidget it can have a window title)
        self.setWindowTitle("Advanced Dock Area")

        # Top-level layout hosting a toolbar and the dock manager
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        # Init Dock Manager
        self.dock_manager = CDockManager(self)
        self.dock_manager.setStyleSheet("")

        # Dock manager helper variables
        self._locked = False  # Lock state of the workspace

        # Initialize mode property first (before toolbar setup)
        self._mode = "developer"
        self._default_add_direction = (
            default_add_direction
            if default_add_direction in ("left", "right", "top", "bottom")
            else "right"
        )

        # Toolbar
        self.dark_mode_button = DarkModeButton(parent=self, toolbar=True)
        self._setup_toolbar()
        self._hook_toolbar()

        # Place toolbar and dock manager into layout
        self._root_layout.addWidget(self.toolbar)
        self._root_layout.addWidget(self.dock_manager, 1)

        # Populate and hook the workspace combo
        self._refresh_workspace_list()

        # State manager
        self.state_manager = WidgetStateManager(self)

        # Developer mode state
        self._editable = None
        # Initialize default editable state based on current lock
        self._set_editable(True)  # default to editable; will sync toolbar toggle below

        # Sync Developer toggle icon state after initial setup
        dev_action = self.toolbar.components.get_action("developer_mode").action
        dev_action.setChecked(self._editable)

        # Apply the requested mode after everything is set up
        self.mode = mode

    def _make_dock(
        self,
        widget: QWidget,
        *,
        closable: bool,
        floatable: bool,
        movable: bool = True,
        area: QtAds.DockWidgetArea = QtAds.DockWidgetArea.RightDockWidgetArea,
        start_floating: bool = False,
    ) -> CDockWidget:
        dock = CDockWidget(widget.objectName())
        dock.setWidget(widget)
        dock.setFeature(CDockWidget.DockWidgetDeleteOnClose, True)
        dock.setFeature(CDockWidget.CustomCloseHandling, True)
        dock.setFeature(CDockWidget.DockWidgetClosable, closable)
        dock.setFeature(CDockWidget.DockWidgetFloatable, floatable)
        dock.setFeature(CDockWidget.DockWidgetMovable, movable)

        self._install_dock_settings_action(dock, widget)

        def on_dock_close():
            widget.close()
            dock.closeDockWidget()
            dock.deleteDockWidget()

        def on_widget_destroyed():
            if not isValid(dock):
                return
            dock.closeDockWidget()
            dock.deleteDockWidget()

        dock.closeRequested.connect(on_dock_close)
        if hasattr(widget, "widget_removed"):
            widget.widget_removed.connect(on_widget_destroyed)

        dock.setMinimumSizeHintMode(CDockWidget.eMinimumSizeHintMode.MinimumSizeHintFromDockWidget)
        self.dock_manager.addDockWidget(area, dock)
        if start_floating:
            dock.setFloating()
        return dock

    def _install_dock_settings_action(self, dock: CDockWidget, widget: QWidget) -> None:
        action = MaterialIconAction(
            icon_name="settings", tooltip="Dock settings", filled=True, parent=self
        ).action
        action.setToolTip("Dock settings")
        action.setObjectName("dockSettingsAction")
        action.triggered.connect(lambda: self._open_dock_settings_dialog(dock, widget))
        dock.setTitleBarActions([action])
        dock.setting_action = action

    def _open_dock_settings_dialog(self, dock: CDockWidget, widget: QWidget) -> None:
        dlg = DockSettingsDialog(self, widget)
        dlg.resize(600, 600)
        dlg.exec()

    def _apply_dock_lock(self, locked: bool) -> None:
        if locked:
            self.dock_manager.lockDockWidgetFeaturesGlobally()
        else:
            self.dock_manager.lockDockWidgetFeaturesGlobally(QtAds.CDockWidget.NoDockWidgetFeatures)

    def _delete_dock(self, dock: CDockWidget) -> None:
        w = dock.widget()
        if w and isValid(w):
            w.close()
            w.deleteLater()
        if isValid(dock):
            dock.closeDockWidget()
            dock.deleteDockWidget()

    def _area_from_where(self, where: str | None) -> QtAds.DockWidgetArea:
        """Return ADS DockWidgetArea from a human-friendly direction string.
        If *where* is None, fall back to instance default.
        """
        d = (where or getattr(self, "_default_add_direction", "right") or "right").lower()
        mapping = {
            "left": QtAds.DockWidgetArea.LeftDockWidgetArea,
            "right": QtAds.DockWidgetArea.RightDockWidgetArea,
            "top": QtAds.DockWidgetArea.TopDockWidgetArea,
            "bottom": QtAds.DockWidgetArea.BottomDockWidgetArea,
        }
        return mapping.get(d, QtAds.DockWidgetArea.RightDockWidgetArea)

    ################################################################################
    # Toolbar Setup
    ################################################################################

    def _setup_toolbar(self):
        self.toolbar = ModularToolBar(parent=self)

        PLOT_ACTIONS = {
            "waveform": (Waveform.ICON_NAME, "Add Waveform", "Waveform"),
            "scatter_waveform": (
                ScatterWaveform.ICON_NAME,
                "Add Scatter Waveform",
                "ScatterWaveform",
            ),
            "multi_waveform": (MultiWaveform.ICON_NAME, "Add Multi Waveform", "MultiWaveform"),
            "image": (Image.ICON_NAME, "Add Image", "Image"),
            "motor_map": (MotorMap.ICON_NAME, "Add Motor Map", "MotorMap"),
            "heatmap": (Heatmap.ICON_NAME, "Add Heatmap", "Heatmap"),
        }
        DEVICE_ACTIONS = {
            "scan_control": (ScanControl.ICON_NAME, "Add Scan Control", "ScanControl"),
            "positioner_box": (PositionerBox.ICON_NAME, "Add Device Box", "PositionerBox"),
        }
        UTIL_ACTIONS = {
            "queue": (BECQueue.ICON_NAME, "Add Scan Queue", "BECQueue"),
            "vs_code": (VSCodeEditor.ICON_NAME, "Add VS Code", "VSCodeEditor"),
            "status": (BECStatusBox.ICON_NAME, "Add BEC Status Box", "BECStatusBox"),
            "progress_bar": (
                RingProgressBar.ICON_NAME,
                "Add Circular ProgressBar",
                "RingProgressBar",
            ),
            "log_panel": (LogPanel.ICON_NAME, "Add LogPanel - Disabled", "LogPanel"),
            "sbb_monitor": ("train", "Add SBB Monitor", "SBBMonitor"),
        }

        # Create expandable menu actions (original behavior)
        def _build_menu(key: str, label: str, mapping: dict[str, tuple[str, str, str]]):
            self.toolbar.components.add_safe(
                key,
                ExpandableMenuAction(
                    label=label,
                    actions={
                        k: MaterialIconAction(
                            icon_name=v[0], tooltip=v[1], filled=True, parent=self
                        )
                        for k, v in mapping.items()
                    },
                ),
            )
            b = ToolbarBundle(key, self.toolbar.components)
            b.add_action(key)
            self.toolbar.add_bundle(b)

        _build_menu("menu_plots", "Add Plot ", PLOT_ACTIONS)
        _build_menu("menu_devices", "Add Device Control ", DEVICE_ACTIONS)
        _build_menu("menu_utils", "Add Utils ", UTIL_ACTIONS)

        # Create flat toolbar bundles for each widget type
        def _build_flat_bundles(category: str, mapping: dict[str, tuple[str, str, str]]):
            bundle = ToolbarBundle(f"flat_{category}", self.toolbar.components)

            for action_id, (icon_name, tooltip, widget_type) in mapping.items():
                # Create individual action for each widget type
                flat_action_id = f"flat_{action_id}"
                self.toolbar.components.add_safe(
                    flat_action_id,
                    MaterialIconAction(
                        icon_name=icon_name, tooltip=tooltip, filled=True, parent=self
                    ),
                )
                bundle.add_action(flat_action_id)

            self.toolbar.add_bundle(bundle)

        _build_flat_bundles("plots", PLOT_ACTIONS)
        _build_flat_bundles("devices", DEVICE_ACTIONS)
        _build_flat_bundles("utils", UTIL_ACTIONS)

        # Workspace
        spacer_bundle = ToolbarBundle("spacer_bundle", self.toolbar.components)
        spacer = QWidget(parent=self.toolbar.components.toolbar)
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.toolbar.components.add_safe("spacer", WidgetAction(widget=spacer, adjust_size=False))
        spacer_bundle.add_action("spacer")
        self.toolbar.add_bundle(spacer_bundle)

        self.toolbar.add_bundle(workspace_bundle(self.toolbar.components))
        self.toolbar.connect_bundle(
            "workspace", WorkspaceConnection(components=self.toolbar.components, target_widget=self)
        )

        # Dock actions
        self.toolbar.components.add_safe(
            "attach_all",
            MaterialIconAction(
                icon_name="zoom_in_map", tooltip="Attach all floating docks", parent=self
            ),
        )
        self.toolbar.components.add_safe(
            "screenshot",
            MaterialIconAction(icon_name="photo_camera", tooltip="Take Screenshot", parent=self),
        )
        self.toolbar.components.add_safe(
            "dark_mode", WidgetAction(widget=self.dark_mode_button, adjust_size=False, parent=self)
        )
        # Developer mode toggle (moved from menu into toolbar)
        self.toolbar.components.add_safe(
            "developer_mode",
            MaterialIconAction(
                icon_name="code", tooltip="Developer Mode", checkable=True, parent=self
            ),
        )
        bda = ToolbarBundle("dock_actions", self.toolbar.components)
        bda.add_action("attach_all")
        bda.add_action("screenshot")
        bda.add_action("dark_mode")
        bda.add_action("developer_mode")
        self.toolbar.add_bundle(bda)

        # Default bundle configuration (show menus by default)
        self.toolbar.show_bundles(
            [
                "menu_plots",
                "menu_devices",
                "menu_utils",
                "spacer_bundle",
                "workspace",
                "dock_actions",
            ]
        )

        # Store mappings on self for use in _hook_toolbar
        self._ACTION_MAPPINGS = {
            "menu_plots": PLOT_ACTIONS,
            "menu_devices": DEVICE_ACTIONS,
            "menu_utils": UTIL_ACTIONS,
        }

    def _hook_toolbar(self):

        def _connect_menu(menu_key: str):
            menu = self.toolbar.components.get_action(menu_key)
            mapping = self._ACTION_MAPPINGS[menu_key]
            for key, (_, _, widget_type) in mapping.items():
                act = menu.actions[key].action
                if widget_type == "LogPanel":
                    act.setEnabled(False)  # keep disabled per issue #644
                else:
                    act.triggered.connect(lambda _, t=widget_type: self.new(widget=t))

        _connect_menu("menu_plots")
        _connect_menu("menu_devices")
        _connect_menu("menu_utils")

        # Connect flat toolbar actions
        def _connect_flat_actions(category: str, mapping: dict[str, tuple[str, str, str]]):
            for action_id, (_, _, widget_type) in mapping.items():
                flat_action_id = f"flat_{action_id}"
                flat_action = self.toolbar.components.get_action(flat_action_id).action
                if widget_type == "LogPanel":
                    flat_action.setEnabled(False)  # keep disabled per issue #644
                else:
                    flat_action.triggered.connect(lambda _, t=widget_type: self.new(widget=t))

        _connect_flat_actions("plots", self._ACTION_MAPPINGS["menu_plots"])
        _connect_flat_actions("devices", self._ACTION_MAPPINGS["menu_devices"])
        _connect_flat_actions("utils", self._ACTION_MAPPINGS["menu_utils"])

        self.toolbar.components.get_action("attach_all").action.triggered.connect(self.attach_all)
        self.toolbar.components.get_action("screenshot").action.triggered.connect(self.screenshot)
        # Developer mode toggle
        self.toolbar.components.get_action("developer_mode").action.toggled.connect(
            self._on_developer_mode_toggled
        )

    def _set_editable(self, editable: bool) -> None:
        self.lock_workspace = not editable
        self._editable = editable

        # Sync the toolbar lock toggle with current mode
        lock_action = self.toolbar.components.get_action("lock").action
        lock_action.setChecked(not editable)
        lock_action.setVisible(editable)

        attach_all_action = self.toolbar.components.get_action("attach_all").action
        attach_all_action.setVisible(editable)

        # Show full creation menus only when editable; otherwise keep minimal set
        if editable:
            self.toolbar.show_bundles(
                [
                    "menu_plots",
                    "menu_devices",
                    "menu_utils",
                    "spacer_bundle",
                    "workspace",
                    "dock_actions",
                ]
            )
        else:
            self.toolbar.show_bundles(["spacer_bundle", "workspace", "dock_actions"])

        # Keep Developer mode UI in sync
        self.toolbar.components.get_action("developer_mode").action.setChecked(editable)

    def _on_developer_mode_toggled(self, checked: bool) -> None:
        """Handle developer mode checkbox toggle."""
        self._set_editable(checked)

    ################################################################################
    # Adding widgets
    ################################################################################
    @SafeSlot(popup_error=True)
    def new(
        self,
        widget: BECWidget | str,
        closable: bool = True,
        floatable: bool = True,
        movable: bool = True,
        start_floating: bool = False,
        where: Literal["left", "right", "top", "bottom"] | None = None,
    ) -> BECWidget:
        """
        Create a new widget (or reuse an instance) and add it as a dock.

        Args:
            widget: Widget instance or a string widget type (factory-created).
            closable: Whether the dock is closable.
            floatable: Whether the dock is floatable.
            movable: Whether the dock is movable.
            start_floating: Start the dock in a floating state.
            where: Preferred area to add the dock: "left" | "right" | "top" | "bottom".
                   If None, uses the instance default passed at construction time.
        Returns:
            The widget instance.
        """
        target_area = self._area_from_where(where)

        # 1) Instantiate or look up the widget
        if isinstance(widget, str):
            widget = cast(BECWidget, widget_handler.create_widget(widget_type=widget, parent=self))
            widget.name_established.connect(
                lambda: self._create_dock_with_name(
                    widget=widget,
                    closable=closable,
                    floatable=floatable,
                    movable=movable,
                    start_floating=start_floating,
                    area=target_area,
                )
            )
            return widget

        # If a widget instance is passed, dock it immediately
        self._create_dock_with_name(
            widget=widget,
            closable=closable,
            floatable=floatable,
            movable=movable,
            start_floating=start_floating,
            area=target_area,
        )
        return widget

    def _create_dock_with_name(
        self,
        widget: BECWidget,
        closable: bool = True,
        floatable: bool = False,
        movable: bool = True,
        start_floating: bool = False,
        area: QtAds.DockWidgetArea | None = None,
    ):
        target_area = area or self._area_from_where(None)
        self._make_dock(
            widget,
            closable=closable,
            floatable=floatable,
            movable=movable,
            area=target_area,
            start_floating=start_floating,
        )
        self.dock_manager.setFocus()

    ################################################################################
    # Dock Management
    ################################################################################

    def dock_map(self) -> dict[str, CDockWidget]:
        """
        Return the dock widgets map as dictionary with names as keys and dock widgets as values.

        Returns:
            dict: A dictionary mapping widget names to their corresponding dock widgets.
        """
        return self.dock_manager.dockWidgetsMap()

    def dock_list(self) -> list[CDockWidget]:
        """
        Return the list of dock widgets.

        Returns:
            list: A list of all dock widgets in the dock area.
        """
        return self.dock_manager.dockWidgets()

    def widget_map(self) -> dict[str, QWidget]:
        """
        Return a dictionary mapping widget names to their corresponding BECWidget instances.

        Returns:
            dict: A dictionary mapping widget names to BECWidget instances.
        """
        return {dock.objectName(): dock.widget() for dock in self.dock_list()}

    def widget_list(self) -> list[QWidget]:
        """
        Return a list of all BECWidget instances in the dock area.

        Returns:
            list: A list of all BECWidget instances in the dock area.
        """
        return [dock.widget() for dock in self.dock_list() if isinstance(dock.widget(), QWidget)]

    @SafeSlot()
    def attach_all(self):
        """
        Return all floating docks to the dock area, preserving tab groups within each floating container.
        """
        for container in self.dock_manager.floatingWidgets():
            docks = container.dockWidgets()
            if not docks:
                continue
            target = docks[0]
            self.dock_manager.addDockWidget(QtAds.DockWidgetArea.RightDockWidgetArea, target)
            for d in docks[1:]:
                self.dock_manager.addDockWidgetTab(
                    QtAds.DockWidgetArea.RightDockWidgetArea, d, target
                )

    @SafeSlot()
    def delete_all(self):
        """Delete all docks and widgets."""
        for dock in list(self.dock_manager.dockWidgets()):
            self._delete_dock(dock)

    ################################################################################
    # Workspace Management
    ################################################################################
    @SafeProperty(bool)
    def lock_workspace(self) -> bool:
        """
        Get or set the lock state of the workspace.

        Returns:
            bool: True if the workspace is locked, False otherwise.
        """
        return self._locked

    @lock_workspace.setter
    def lock_workspace(self, value: bool):
        """
        Set the lock state of the workspace. Docks remain resizable, but are not movable or closable.

        Args:
            value (bool): True to lock the workspace, False to unlock it.
        """
        self._locked = value
        self._apply_dock_lock(value)
        self.toolbar.components.get_action("save_workspace").action.setVisible(not value)
        self.toolbar.components.get_action("delete_workspace").action.setVisible(not value)
        for dock in self.dock_list():
            dock.setting_action.setVisible(not value)

    @SafeSlot(str)
    def save_profile(self, name: str | None = None):
        """
        Save the current workspace profile.

        Args:
            name (str | None): The name of the profile. If None, a dialog will prompt for a name.
        """
        if not name:
            # Use the new SaveProfileDialog instead of QInputDialog
            dialog = SaveProfileDialog(self)
            if dialog.exec() != QDialog.Accepted:
                return
            name = dialog.get_profile_name()
            readonly = dialog.is_readonly()

            # Check if profile already exists and is read-only
            if os.path.exists(profile_path(name)) and is_profile_readonly(name):
                suggested_name = f"{name}_custom"
                reply = QMessageBox.warning(
                    self,
                    "Read-only Profile",
                    f"The profile '{name}' is marked as read-only and cannot be overwritten.\n\n"
                    f"Would you like to save it with a different name?\n"
                    f"Suggested name: '{suggested_name}'",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                if reply == QMessageBox.Yes:
                    # Show dialog again with suggested name pre-filled
                    dialog = SaveProfileDialog(self, suggested_name)
                    if dialog.exec() != QDialog.Accepted:
                        return
                    name = dialog.get_profile_name()
                    readonly = dialog.is_readonly()

                    # Check again if the new name is also read-only (recursive protection)
                    if os.path.exists(profile_path(name)) and is_profile_readonly(name):
                        return self.save_profile()
                else:
                    return
        else:
            # If name is provided directly, assume not read-only unless already exists
            readonly = False
            if os.path.exists(profile_path(name)) and is_profile_readonly(name):
                QMessageBox.warning(
                    self,
                    "Read-only Profile",
                    f"The profile '{name}' is marked as read-only and cannot be overwritten.",
                    QMessageBox.Ok,
                )
                return

        # Display saving placeholder
        workspace_combo = self.toolbar.components.get_action("workspace_combo").widget
        workspace_combo.blockSignals(True)
        workspace_combo.insertItem(0, f"{name}-saving")
        workspace_combo.setCurrentIndex(0)
        workspace_combo.blockSignals(False)

        # Save the profile
        settings = open_settings(name)
        settings.setValue(SETTINGS_KEYS["geom"], self.saveGeometry())
        settings.setValue(
            SETTINGS_KEYS["state"], b""
        )  # No QMainWindow state; placeholder for backward compat
        settings.setValue(SETTINGS_KEYS["ads_state"], self.dock_manager.saveState())
        self.dock_manager.addPerspective(name)
        self.dock_manager.savePerspectives(settings)
        self.state_manager.save_state(settings=settings)
        write_manifest(settings, self.dock_list())

        # Set read-only status if specified
        if readonly:
            set_profile_readonly(name, readonly)

        settings.sync()
        self._refresh_workspace_list()
        workspace_combo.setCurrentText(name)

    def load_profile(self, name: str | None = None):
        """
        Load a workspace profile.

        Args:
            name (str | None): The name of the profile. If None, a dialog will prompt for a name.
        """
        # FIXME this has to be tweaked
        if not name:
            name, ok = QInputDialog.getText(
                self, "Load Workspace", "Enter the name of the workspace profile to load:"
            )
            if not ok or not name:
                return
        settings = open_settings(name)

        for item in read_manifest(settings):
            obj_name = item["object_name"]
            widget_class = item["widget_class"]
            if obj_name not in self.widget_map():
                w = widget_handler.create_widget(widget_type=widget_class, parent=self)
                w.setObjectName(obj_name)
                self._make_dock(
                    w,
                    closable=item["closable"],
                    floatable=item["floatable"],
                    movable=item["movable"],
                    area=QtAds.DockWidgetArea.RightDockWidgetArea,
                )

        geom = settings.value(SETTINGS_KEYS["geom"])
        if geom:
            self.restoreGeometry(geom)
        # No window state for QWidget-based host; keep for backwards compat read
        # window_state = settings.value(SETTINGS_KEYS["state"])  # ignored
        dock_state = settings.value(SETTINGS_KEYS["ads_state"])
        if dock_state:
            self.dock_manager.restoreState(dock_state)
        self.dock_manager.loadPerspectives(settings)
        self.state_manager.load_state(settings=settings)
        self._set_editable(self._editable)

    @SafeSlot()
    def delete_profile(self):
        """
        Delete the currently selected workspace profile file and refresh the combo list.
        """
        combo = self.toolbar.components.get_action("workspace_combo").widget
        name = combo.currentText()
        if not name:
            return

        # Check if profile is read-only
        if is_profile_readonly(name):
            QMessageBox.warning(
                self,
                "Read-only Profile",
                f"The profile '{name}' is marked as read-only and cannot be deleted.\n\n"
                f"Read-only profiles are protected from modification and deletion.",
                QMessageBox.Ok,
            )
            return

        # Confirm deletion for regular profiles
        reply = QMessageBox.question(
            self,
            "Delete Profile",
            f"Are you sure you want to delete the profile '{name}'?\n\n"
            f"This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        file_path = profile_path(name)
        try:
            os.remove(file_path)
        except FileNotFoundError:
            return
        self._refresh_workspace_list()

    def _refresh_workspace_list(self):
        """
        Populate the workspace combo box with all saved profile names (without .ini).
        """
        combo = self.toolbar.components.get_action("workspace_combo").widget
        if hasattr(combo, "refresh_profiles"):
            combo.refresh_profiles()
        else:
            # Fallback for regular QComboBox
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(list_profiles())
            combo.blockSignals(False)

    ################################################################################
    # Mode Switching
    ################################################################################

    @SafeProperty(str)
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, new_mode: str):
        if new_mode not in ["plot", "device", "utils", "developer", "user"]:
            raise ValueError(f"Invalid mode: {new_mode}")
        self._mode = new_mode
        self.mode_changed.emit(new_mode)

        # Update toolbar visibility based on mode
        if new_mode == "user":
            # User mode: show only essential tools
            self.toolbar.show_bundles(["spacer_bundle", "workspace", "dock_actions"])
        elif new_mode == "developer":
            # Developer mode: show all tools (use menu bundles)
            self.toolbar.show_bundles(
                [
                    "menu_plots",
                    "menu_devices",
                    "menu_utils",
                    "spacer_bundle",
                    "workspace",
                    "dock_actions",
                ]
            )
        elif new_mode in ["plot", "device", "utils"]:
            # Specific modes: show flat toolbar for that category
            bundle_name = f"flat_{new_mode}s" if new_mode != "utils" else "flat_utils"
            self.toolbar.show_bundles([bundle_name])
            # self.toolbar.show_bundles([bundle_name, "spacer_bundle", "workspace", "dock_actions"])
        else:
            # Fallback to user mode
            self.toolbar.show_bundles(["spacer_bundle", "workspace", "dock_actions"])

    def cleanup(self):
        """
        Cleanup the dock area.
        """
        self.delete_all()
        self.dark_mode_button.close()
        self.dark_mode_button.deleteLater()
        self.toolbar.cleanup()
        super().cleanup()


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    dispatcher = BECDispatcher(gui_id="ads")
    window = BECMainWindowNoRPC()
    ads = AdvancedDockArea(mode="developer", root_widget=True)
    window.setCentralWidget(ads)
    window.show()
    window.resize(800, 600)

    sys.exit(app.exec())
