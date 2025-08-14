from __future__ import annotations

import os
from typing import cast

import PySide6QtAds as QtAds
from PySide6QtAds import CDockManager, CDockWidget
from qtpy.QtCore import QSettings, QSize, Qt
from qtpy.QtGui import QAction
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
from bec_widgets.widgets.containers.advanced_dock_area.toolbar_components.workspace_actions import (
    WorkspaceConnection,
    workspace_bundle,
)
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow
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

MODULE_PATH = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_DEFAULT_PROFILES_DIR = os.path.join(os.path.dirname(__file__), "states", "default")
_USER_PROFILES_DIR = os.path.join(os.path.dirname(__file__), "states", "user")


def _profiles_dir() -> str:
    path = os.environ.get("BECWIDGETS_PROFILE_DIR", _USER_PROFILES_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def _profile_path(name: str) -> str:
    return os.path.join(_profiles_dir(), f"{name}.ini")


SETTINGS_KEYS = {
    "geom": "mainWindow/Geometry",
    "state": "mainWindow/State",
    "ads_state": "mainWindow/DockingState",
    "manifest": "manifest/widgets",
    "readonly": "profile/readonly",
}


def list_profiles() -> list[str]:
    return sorted(os.path.splitext(f)[0] for f in os.listdir(_profiles_dir()) if f.endswith(".ini"))


def is_profile_readonly(name: str) -> bool:
    """Check if a profile is marked as read-only."""
    settings = open_settings(name)
    return settings.value(SETTINGS_KEYS["readonly"], False, type=bool)


def set_profile_readonly(name: str, readonly: bool) -> None:
    """Set the read-only status of a profile."""
    settings = open_settings(name)
    settings.setValue(SETTINGS_KEYS["readonly"], readonly)
    settings.sync()


def open_settings(name: str) -> QSettings:
    return QSettings(_profile_path(name), QSettings.IniFormat)


def write_manifest(settings: QSettings, docks: list[CDockWidget]) -> None:
    settings.beginWriteArray(SETTINGS_KEYS["manifest"], len(docks))
    for i, dock in enumerate(docks):
        settings.setArrayIndex(i)
        w = dock.widget()
        settings.setValue("object_name", w.objectName())
        settings.setValue("widget_class", w.__class__.__name__)
        settings.setValue("closable", getattr(dock, "_default_closable", True))
        settings.setValue("floatable", getattr(dock, "_default_floatable", True))
        settings.setValue("movable", getattr(dock, "_default_movable", True))
    settings.endArray()


def read_manifest(settings: QSettings) -> list[dict]:
    items: list[dict] = []
    count = settings.beginReadArray(SETTINGS_KEYS["manifest"])
    for i in range(count):
        settings.setArrayIndex(i)
        items.append(
            {
                "object_name": settings.value("object_name"),
                "widget_class": settings.value("widget_class"),
                "closable": settings.value("closable", type=bool),
                "floatable": settings.value("floatable", type=bool),
                "movable": settings.value("movable", type=bool),
            }
        )
    settings.endArray()
    return items


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


class AdvancedDockArea(BECMainWindow):
    RPC = True
    PLUGIN = False
    USER_ACCESS = ["new", "widget_map", "widget_list", "lock_workspace", "attach_all", "delete_all"]

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        # Setting the dock manager with flags
        QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.eConfigFlag.FocusHighlighting, True)
        QtAds.CDockManager.setConfigFlag(
            QtAds.CDockManager.eConfigFlag.RetainTabSizeWhenCloseButtonHidden, True
        )
        QtAds.CDockManager.setConfigFlag(
            QtAds.CDockManager.eConfigFlag.HideSingleCentralWidgetTitleBar, True
        )
        self.dock_manager = CDockManager(self)

        # Dock manager helper variables
        self._locked = False  # Lock state of the workspace

        # Toolbar
        self.dark_mode_button = DarkModeButton(parent=self, toolbar=True)
        self._setup_toolbar()
        self._hook_toolbar()

        # Populate and hook the workspace combo
        self._refresh_workspace_list()

        # State manager
        self.state_manager = WidgetStateManager(self)

        # Insert Mode menu
        self._editable = None
        self._setup_developer_mode_menu()

        # Notification center re-raise
        self.notification_centre.raise_()
        self.statusBar().raise_()

    def minimumSizeHint(self):
        return QSize(1200, 800)

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
        bda = ToolbarBundle("dock_actions", self.toolbar.components)
        bda.add_action("attach_all")
        bda.add_action("screenshot")
        bda.add_action("dark_mode")
        self.toolbar.add_bundle(bda)

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
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

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

        self.toolbar.components.get_action("attach_all").action.triggered.connect(self.attach_all)
        self.toolbar.components.get_action("screenshot").action.triggered.connect(self.screenshot)

    def _setup_developer_mode_menu(self):
        """Add a 'Developer' checkbox to the View menu after theme actions."""
        mb = self.menuBar()

        # Find the View menu (inherited from BECMainWindow)
        view_menu = None
        for action in mb.actions():
            if action.menu() and action.menu().title() == "View":
                view_menu = action.menu()
                break

        if view_menu is None:
            # If View menu doesn't exist, create it
            view_menu = mb.addMenu("View")

        # Add separator after existing theme actions
        view_menu.addSeparator()

        # Add Developer mode checkbox
        self._developer_mode_action = QAction("Developer", self, checkable=True)

        # Default selection based on current lock state
        self._editable = not self.lock_workspace
        self._developer_mode_action.setChecked(self._editable)

        # Wire up action
        self._developer_mode_action.triggered.connect(self._on_developer_mode_toggled)

        view_menu.addAction(self._developer_mode_action)

    def _on_developer_mode_toggled(self, checked: bool) -> None:
        """Handle developer mode checkbox toggle."""
        self._set_editable(checked)

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
        if hasattr(self, "_developer_mode_action"):
            self._developer_mode_action.setChecked(editable)

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
    ) -> BECWidget:
        """
        Creates a new widget or reuses an existing one and schedules its dock creation.

        Args:
            widget (BECWidget | str): The widget instance or a string specifying the
                type of widget to create.
            closable (bool): Whether the dock should be closable. Defaults to True.
            floatable (bool): Whether the dock should be floatable. Defaults to True.
            movable (bool): Whether the dock should be movable. Defaults to True.
            start_floating (bool): Whether to start the dock in a floating state. Defaults to False.

        Returns:
            widget: The widget instance.
        """
        # 1) Instantiate or look up the widget (this schedules the BECConnector naming logic)
        if isinstance(widget, str):
            widget = cast(BECWidget, widget_handler.create_widget(widget_type=widget, parent=self))
            widget.name_established.connect(
                lambda: self._create_dock_with_name(
                    widget=widget,
                    closable=closable,
                    floatable=floatable,
                    movable=movable,
                    start_floating=start_floating,
                )
            )
        return widget

    def _create_dock_with_name(
        self,
        widget: BECWidget,
        closable: bool = True,
        floatable: bool = False,
        movable: bool = True,
        start_floating: bool = False,
    ):
        self._make_dock(
            widget,
            closable=closable,
            floatable=floatable,
            movable=movable,
            area=QtAds.DockWidgetArea.RightDockWidgetArea,
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
            if os.path.exists(_profile_path(name)) and is_profile_readonly(name):
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
                    if os.path.exists(_profile_path(name)) and is_profile_readonly(name):
                        return self.save_profile()
                else:
                    return
        else:
            # If name is provided directly, assume not read-only unless already exists
            readonly = False
            if os.path.exists(_profile_path(name)) and is_profile_readonly(name):
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
        settings.setValue(SETTINGS_KEYS["state"], self.saveState())
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
        window_state = settings.value(SETTINGS_KEYS["state"])
        if window_state:
            self.restoreState(window_state)
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

        file_path = _profile_path(name)
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
    # Styling
    ################################################################################

    def cleanup(self):
        """
        Cleanup the dock area.
        """
        self.delete_all()
        self.dark_mode_button.close()
        self.dark_mode_button.deleteLater()
        super().cleanup()


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    dispatcher = BECDispatcher(gui_id="ads")
    main_window = AdvancedDockArea()
    main_window.show()
    main_window.resize(800, 600)
    sys.exit(app.exec())
