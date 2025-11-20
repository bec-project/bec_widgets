from __future__ import annotations

import os
from typing import Callable, Literal, Mapping, Sequence

from bec_lib import bec_logger
from qtpy.QtCore import QTimer, Signal
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import (
    QApplication,
    QDialog,
    QInputDialog,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import bec_widgets.widgets.containers.qt_ads as QtAds
from bec_widgets import BECWidget, SafeProperty, SafeSlot
from bec_widgets.cli.rpc.rpc_widget_handler import widget_handler
from bec_widgets.utils import BECDispatcher
from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.toolbars.actions import (
    ExpandableMenuAction,
    MaterialIconAction,
    WidgetAction,
)
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.utils.widget_state_manager import WidgetStateManager
from bec_widgets.widgets.containers.advanced_dock_area.basic_dock_area import DockAreaWidget
from bec_widgets.widgets.containers.advanced_dock_area.profile_utils import (
    SETTINGS_KEYS,
    default_profile_candidates,
    delete_profile_files,
    get_last_profile,
    is_profile_read_only,
    is_quick_select,
    list_quick_profiles,
    load_default_profile_screenshot,
    load_user_profile_screenshot,
    now_iso_utc,
    open_default_settings,
    open_user_settings,
    profile_origin,
    profile_origin_display,
    read_manifest,
    restore_user_from_default,
    sanitize_namespace,
    set_last_profile,
    set_quick_select,
    user_profile_candidates,
    write_manifest,
)
from bec_widgets.widgets.containers.advanced_dock_area.settings.dialogs import (
    RestoreProfileDialog,
    SaveProfileDialog,
)
from bec_widgets.widgets.containers.advanced_dock_area.settings.workspace_manager import (
    WorkSpaceManager,
)
from bec_widgets.widgets.containers.advanced_dock_area.toolbar_components.workspace_actions import (
    WorkspaceConnection,
    workspace_bundle,
)
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindowNoRPC
from bec_widgets.widgets.containers.qt_ads import CDockWidget
from bec_widgets.widgets.control.device_control.positioner_box import PositionerBox, PositionerBox2D
from bec_widgets.widgets.control.scan_control import ScanControl
from bec_widgets.widgets.editors.web_console.web_console import WebConsole
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

logger = bec_logger.logger

_PROFILE_NAMESPACE_UNSET = object()

PROFILE_STATE_KEYS = {key: SETTINGS_KEYS[key] for key in ("geom", "state", "ads_state")}


class AdvancedDockArea(DockAreaWidget):
    RPC = True
    PLUGIN = False
    USER_ACCESS = [
        "new",
        "dock_map",
        "dock_list",
        "widget_map",
        "widget_list",
        "lock_workspace",
        "attach_all",
        "delete_all",
        "set_layout_ratios",
        "describe_layout",
        "print_layout_structure",
        "mode",
        "mode.setter",
    ]

    # Define a signal for mode changes
    mode_changed = Signal(str)
    profile_changed = Signal(str)

    def __init__(
        self,
        parent=None,
        mode: Literal["plot", "device", "utils", "user", "creator"] = "creator",
        default_add_direction: Literal["left", "right", "top", "bottom"] = "right",
        profile_namespace: str | None = None,
        auto_profile_namespace: bool = True,
        instance_id: str | None = None,
        auto_save_upon_exit: bool = True,
        enable_profile_management: bool = True,
        restore_initial_profile: bool = True,
        **kwargs,
    ):
        self._profile_namespace_hint = profile_namespace
        self._profile_namespace_auto = auto_profile_namespace
        self._profile_namespace_resolved: str | None | object = _PROFILE_NAMESPACE_UNSET
        self._instance_id = sanitize_namespace(instance_id) if instance_id else None
        self._auto_save_upon_exit = auto_save_upon_exit
        self._profile_management_enabled = enable_profile_management
        self._restore_initial_profile = restore_initial_profile
        super().__init__(
            parent,
            default_add_direction=default_add_direction,
            title="Advanced Dock Area",
            **kwargs,
        )

        # Initialize mode property first (before toolbar setup)
        self._mode = mode

        # Toolbar
        self.dark_mode_button = DarkModeButton(parent=self, toolbar=True)
        self.dark_mode_button.setVisible(enable_profile_management)
        self._setup_toolbar()
        self._hook_toolbar()

        # Popups
        self.save_dialog = None
        self.manage_dialog = None

        # Place toolbar above the dock manager provided by the base class
        self._root_layout.insertWidget(0, self.toolbar)

        # Populate and hook the workspace combo
        self._refresh_workspace_list()
        self._current_profile_name = None
        self._pending_autosave_skip: tuple[str, str] | None = None
        self._exit_snapshot_written = False

        # State manager
        self.state_manager = WidgetStateManager(
            self, serialize_from_root=True, root_id="AdvancedDockArea"
        )

        # Developer mode state
        self._editable = None
        # Initialize default editable state based on current lock
        self._set_editable(True)  # default to editable; will sync toolbar toggle below

        # Sync Developer toggle icon state after initial setup #TODO temporary disable
        # dev_action = self.toolbar.components.get_action("developer_mode").action
        # dev_action.setChecked(self._editable)

        # Apply the requested mode after everything is set up
        self.mode = mode
        if self._restore_initial_profile:
            self._fetch_initial_profile()

    def _fetch_initial_profile(self):
        # Restore last-used profile if available; otherwise fall back to combo selection
        combo = self.toolbar.components.get_action("workspace_combo").widget
        namespace = self.profile_namespace
        init_profile = None
        instance_id = self._last_profile_instance_id()
        if instance_id:
            inst_profile = get_last_profile(
                namespace=namespace, instance=instance_id, allow_namespace_fallback=False
            )
            if inst_profile and self._profile_exists(inst_profile, namespace):
                init_profile = inst_profile
        if not init_profile:
            last = get_last_profile(namespace=namespace)
            if last and self._profile_exists(last, namespace):
                init_profile = last
            else:
                text = combo.currentText()
                init_profile = text if text else None
        if not init_profile:
            if self._profile_exists("general", namespace):
                init_profile = "general"
        if init_profile:
            # Defer initial load to the event loop so child widgets exist before state restore.
            QTimer.singleShot(0, lambda: self._load_initial_profile(init_profile))

    def _load_initial_profile(self, name: str) -> None:
        """Load the initial profile after construction when the event loop is running."""
        self.load_profile(name)
        combo = self.toolbar.components.get_action("workspace_combo").widget
        combo.blockSignals(True)
        combo.setCurrentText(name)
        combo.blockSignals(False)

    def _customize_dock(self, dock: CDockWidget, widget: QWidget) -> None:
        prefs = getattr(dock, "_dock_preferences", {}) or {}
        if prefs.get("show_settings_action") is None:
            prefs = dict(prefs)
            prefs["show_settings_action"] = True
            dock._dock_preferences = prefs
        super()._customize_dock(dock, widget)

    @SafeSlot(popup_error=True)
    def new(
        self,
        widget: QWidget | str,
        *,
        closable: bool = True,
        floatable: bool = True,
        movable: bool = True,
        start_floating: bool = False,
        where: Literal["left", "right", "top", "bottom"] | None = None,
        on_close: Callable[[CDockWidget, QWidget], None] | None = None,
        tab_with: CDockWidget | QWidget | str | None = None,
        relative_to: CDockWidget | QWidget | str | None = None,
        return_dock: bool = False,
        show_title_bar: bool | None = None,
        title_buttons: Mapping[str, bool] | Sequence[str] | str | None = None,
        show_settings_action: bool | None = None,
        promote_central: bool = False,
        **widget_kwargs,
    ) -> QWidget | CDockWidget | BECWidget:
        """
        Override the base helper so dock settings are available by default.

        The flag remains user-configurable (pass ``False`` to hide the action).
        """
        if show_settings_action is None:
            show_settings_action = True
        return super().new(
            widget,
            closable=closable,
            floatable=floatable,
            movable=movable,
            start_floating=start_floating,
            where=where,
            on_close=on_close,
            tab_with=tab_with,
            relative_to=relative_to,
            return_dock=return_dock,
            show_title_bar=show_title_bar,
            title_buttons=title_buttons,
            show_settings_action=show_settings_action,
            promote_central=promote_central,
            **widget_kwargs,
        )

    def _apply_dock_lock(self, locked: bool) -> None:
        if locked:
            self.dock_manager.lockDockWidgetFeaturesGlobally()
        else:
            self.dock_manager.lockDockWidgetFeaturesGlobally(QtAds.CDockWidget.NoDockWidgetFeatures)

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
            "positioner_box_2D": (
                PositionerBox2D.ICON_NAME,
                "Add Device 2D Box",
                "PositionerBox2D",
            ),
        }
        UTIL_ACTIONS = {
            "queue": (BECQueue.ICON_NAME, "Add Scan Queue", "BECQueue"),
            "status": (BECStatusBox.ICON_NAME, "Add BEC Status Box", "BECStatusBox"),
            "progress_bar": (
                RingProgressBar.ICON_NAME,
                "Add Circular ProgressBar",
                "RingProgressBar",
            ),
            "terminal": (WebConsole.ICON_NAME, "Add Terminal", "WebConsole"),
            "bec_shell": (WebConsole.ICON_NAME, "Add BEC Shell", "WebConsole"),
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
                        icon_name=icon_name,
                        tooltip=tooltip,
                        filled=True,
                        parent=self,
                        label_text=widget_type,
                        text_position="under",
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

        self.toolbar.add_bundle(
            workspace_bundle(self.toolbar.components, enable_tools=self._profile_management_enabled)
        )
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
        self.toolbar.components.get_action("attach_all").action.setVisible(
            self._profile_management_enabled
        )
        self.toolbar.components.add_safe(
            "screenshot",
            MaterialIconAction(icon_name="photo_camera", tooltip="Take Screenshot", parent=self),
        )
        self.toolbar.components.get_action("screenshot").action.setVisible(
            self._profile_management_enabled
        )
        dark_mode_action = WidgetAction(
            widget=self.dark_mode_button, adjust_size=False, parent=self
        )
        dark_mode_action.widget.setVisible(self._profile_management_enabled)
        self.toolbar.components.add_safe("dark_mode", dark_mode_action)

        bda = ToolbarBundle("dock_actions", self.toolbar.components)
        bda.add_action("attach_all")
        bda.add_action("screenshot")
        bda.add_action("dark_mode")
        # bda.add_action("developer_mode") #TODO temporary disable
        self.toolbar.add_bundle(bda)

        self._apply_toolbar_layout()

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

            # first two items not needed for this part
            for key, (_, _, widget_type) in mapping.items():
                act = menu.actions[key].action
                if widget_type == "LogPanel":
                    act.setEnabled(False)  # keep disabled per issue #644
                elif key == "terminal":
                    act.triggered.connect(
                        lambda _, t=widget_type: self.new(widget=t, closable=True, startup_cmd=None)
                    )
                elif key == "bec_shell":
                    act.triggered.connect(
                        lambda _, t=widget_type: self.new(
                            widget=t,
                            closable=True,
                            startup_cmd=f"bec --gui-id {self.bec_dispatcher.cli_server.gui_id}",
                            show_settings_action=True,
                        )
                    )
                else:
                    act.triggered.connect(lambda _, t=widget_type: self.new(widget=t))

        _connect_menu("menu_plots")
        _connect_menu("menu_devices")
        _connect_menu("menu_utils")

        def _connect_flat_actions(mapping: dict[str, tuple[str, str, str]]):
            for action_id, (_, _, widget_type) in mapping.items():
                flat_action_id = f"flat_{action_id}"
                flat_action = self.toolbar.components.get_action(flat_action_id).action
                if widget_type == "LogPanel":
                    flat_action.setEnabled(False)  # keep disabled per issue #644
                else:
                    flat_action.triggered.connect(lambda _, t=widget_type: self.new(t))

        _connect_flat_actions(self._ACTION_MAPPINGS["menu_plots"])
        _connect_flat_actions(self._ACTION_MAPPINGS["menu_devices"])
        _connect_flat_actions(self._ACTION_MAPPINGS["menu_utils"])

        self.toolbar.components.get_action("attach_all").action.triggered.connect(self.attach_all)
        self.toolbar.components.get_action("screenshot").action.triggered.connect(self.screenshot)

    def _set_editable(self, editable: bool) -> None:
        self.lock_workspace = not editable
        self._editable = editable

        if self._profile_management_enabled:
            self.toolbar.components.get_action("attach_all").action.setVisible(editable)

    def _on_developer_mode_toggled(self, checked: bool) -> None:
        """Handle developer mode checkbox toggle."""
        self._set_editable(checked)

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
        if self._profile_management_enabled:
            self.toolbar.components.get_action("save_workspace").action.setVisible(not value)
        for dock in self.dock_list():
            dock.setting_action.setVisible(not value)

    def _last_profile_instance_id(self) -> str | None:
        """
        Identifier used to scope the last-profile entry for this dock area.

        When unset, profiles are scoped only by namespace.
        """
        return self._instance_id

    def _resolve_profile_namespace(self) -> str | None:
        if self._profile_namespace_resolved is not _PROFILE_NAMESPACE_UNSET:
            return self._profile_namespace_resolved  # type: ignore[return-value]

        candidate = self._profile_namespace_hint
        if self._profile_namespace_auto:
            if not candidate:
                obj_name = self.objectName()
                candidate = obj_name if obj_name else None
            if not candidate:
                title = self.windowTitle()
                candidate = title if title and title.strip() else None
            if not candidate:
                mode_name = getattr(self, "_mode", None) or "creator"
                candidate = f"{mode_name}_workspace"
            if not candidate:
                candidate = self.__class__.__name__

        resolved = sanitize_namespace(candidate) if candidate else None
        if not resolved:
            resolved = "general"
        self._profile_namespace_resolved = resolved  # type: ignore[assignment]
        return resolved

    @property
    def profile_namespace(self) -> str | None:
        """Namespace used to scope user/default profile files for this dock area."""
        return self._resolve_profile_namespace()

    def _active_profile_name_or_default(self) -> str:
        name = getattr(self, "_current_profile_name", None)
        if not name:
            name = "general"
            self._current_profile_name = name
        return name

    def _profile_exists(self, name: str, namespace: str | None) -> bool:
        return any(
            os.path.exists(path) for path in user_profile_candidates(name, namespace)
        ) or any(os.path.exists(path) for path in default_profile_candidates(name, namespace))

    def _write_snapshot_to_settings(self, settings, save_preview: bool = True) -> None:
        self.save_to_settings(settings, keys=PROFILE_STATE_KEYS)
        self.state_manager.save_state(settings=settings)
        write_manifest(settings, self.dock_list())
        if save_preview:
            ba = self.screenshot_bytes()
            if ba and len(ba) > 0:
                settings.setValue(SETTINGS_KEYS["screenshot"], ba)
                settings.setValue(SETTINGS_KEYS["screenshot_at"], now_iso_utc())

        logger.info(f"Workspace snapshot written to settings: {settings.fileName()}")

    @SafeSlot(str)
    def save_profile(self, name: str | None = None):
        """
        Save the current workspace profile.

        On first save of a given name:
          - writes a default copy to states/default/<name>.ini with tag=default and created_at
          - writes a user copy   to states/user/<name>.ini    with tag=user    and created_at
        On subsequent saves of user-owned profiles:
          - updates both the default and user copies so restore uses the latest snapshot.
        Read-only bundled profiles cannot be overwritten.

        Args:
            name (str | None): The name of the profile to save. If None, prompts the user.
        """

        namespace = self.profile_namespace

        def _profile_exists(profile_name: str) -> bool:
            return profile_origin(profile_name, namespace=namespace) != "unknown"

        initial_name = name or ""
        quickselect_default = is_quick_select(name, namespace=namespace) if name else False

        current_profile = getattr(self, "_current_profile_name", "") or ""
        dialog = SaveProfileDialog(
            self,
            current_name=initial_name,
            current_profile_name=current_profile,
            name_exists=_profile_exists,
            profile_origin=lambda n: profile_origin(n, namespace=namespace),
            origin_label=lambda n: profile_origin_display(n, namespace=namespace),
            quick_select_checked=quickselect_default,
        )
        if dialog.exec() != QDialog.Accepted:
            return

        name = dialog.get_profile_name()
        quickselect = dialog.is_quick_select()
        origin_before_save = profile_origin(name, namespace=namespace)
        overwrite_default = dialog.overwrite_existing and origin_before_save == "settings"
        # Display saving placeholder
        workspace_combo = self.toolbar.components.get_action("workspace_combo").widget
        workspace_combo.blockSignals(True)
        workspace_combo.insertItem(0, f"{name}-saving")
        workspace_combo.setCurrentIndex(0)
        workspace_combo.blockSignals(False)

        # Create or update default copy controlled by overwrite flag
        should_write_default = overwrite_default or not any(
            os.path.exists(path) for path in default_profile_candidates(name, namespace)
        )
        if should_write_default:
            ds = open_default_settings(name, namespace=namespace)
            self._write_snapshot_to_settings(ds)
            if not ds.value(SETTINGS_KEYS["created_at"], ""):
                ds.setValue(SETTINGS_KEYS["created_at"], now_iso_utc())
            # Ensure new profiles are not quick-select by default
            if not ds.value(SETTINGS_KEYS["is_quick_select"], None):
                ds.setValue(SETTINGS_KEYS["is_quick_select"], False)

        # Always (over)write the user copy
        us = open_user_settings(name, namespace=namespace)
        self._write_snapshot_to_settings(us)
        if not us.value(SETTINGS_KEYS["created_at"], ""):
            us.setValue(SETTINGS_KEYS["created_at"], now_iso_utc())
        # Ensure new profiles are not quick-select by default (only if missing)
        if not us.value(SETTINGS_KEYS["is_quick_select"], None):
            us.setValue(SETTINGS_KEYS["is_quick_select"], False)

        # set quick select
        if quickselect:
            set_quick_select(name, quickselect, namespace=namespace)

        self._refresh_workspace_list()
        if current_profile and current_profile != name and not dialog.overwrite_existing:
            self._pending_autosave_skip = (current_profile, name)
        else:
            self._pending_autosave_skip = None
        workspace_combo.setCurrentText(name)
        self._current_profile_name = name
        self.profile_changed.emit(name)
        set_last_profile(name, namespace=namespace, instance=self._last_profile_instance_id())
        combo = self.toolbar.components.get_action("workspace_combo").widget
        combo.refresh_profiles(active_profile=name)

    def load_profile(self, name: str | None = None):
        """
        Load a workspace profile.

        Before switching, persist the current profile to the user copy.
        Prefer loading the user copy; fall back to the default copy.
        """
        if not name:  # Gui fallback if the name is not provided
            name, ok = QInputDialog.getText(
                self, "Load Workspace", "Enter the name of the workspace profile to load:"
            )
            if not ok or not name:
                return

        namespace = self.profile_namespace
        prev_name = getattr(self, "_current_profile_name", None)
        skip_pair = getattr(self, "_pending_autosave_skip", None)
        if prev_name and prev_name != name:
            if skip_pair and skip_pair == (prev_name, name):
                self._pending_autosave_skip = None
            else:
                us_prev = open_user_settings(prev_name, namespace=namespace)
                self._write_snapshot_to_settings(us_prev, save_preview=True)

        settings = None
        if any(os.path.exists(path) for path in user_profile_candidates(name, namespace)):
            settings = open_user_settings(name, namespace=namespace)
        elif any(os.path.exists(path) for path in default_profile_candidates(name, namespace)):
            settings = open_default_settings(name, namespace=namespace)
        if settings is None:
            QMessageBox.warning(self, "Profile not found", f"Profile '{name}' not found.")
            return

        # Rebuild widgets and restore states
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

        self.load_from_settings(settings, keys=PROFILE_STATE_KEYS)
        self.state_manager.load_state(settings=settings)
        self._set_editable(self._editable)

        self._current_profile_name = name
        self.profile_changed.emit(name)
        set_last_profile(name, namespace=namespace, instance=self._last_profile_instance_id())
        combo = self.toolbar.components.get_action("workspace_combo").widget
        combo.refresh_profiles(active_profile=name)

    @SafeSlot()
    @SafeSlot(str)
    def restore_user_profile_from_default(self, name: str | None = None):
        """
        Overwrite the user copy of *name* with the default baseline.
        If *name* is None, target the currently active profile.

        Args:
            name (str | None): The name of the profile to restore. If None, uses the current profile.
        """
        target = name or getattr(self, "_current_profile_name", None)
        if not target:
            return
        namespace = self.profile_namespace

        current_pixmap = None
        if self.isVisible():
            current_pixmap = QPixmap()
            ba = bytes(self.screenshot_bytes())
            current_pixmap.loadFromData(ba)
        if current_pixmap is None or current_pixmap.isNull():
            current_pixmap = load_user_profile_screenshot(target, namespace=namespace)
        default_pixmap = load_default_profile_screenshot(target, namespace=namespace)

        if not RestoreProfileDialog.confirm(self, current_pixmap, default_pixmap):
            return

        restore_user_from_default(target, namespace=namespace)
        self.delete_all()
        self.load_profile(target)

    @SafeSlot()
    def delete_profile(self):
        """
        Delete the currently selected workspace profile file and refresh the combo list.
        """
        combo = self.toolbar.components.get_action("workspace_combo").widget
        name = combo.currentText()
        if not name:
            return

        # Protect bundled/module/plugin profiles from deletion
        if is_profile_read_only(name, namespace=self.profile_namespace):
            QMessageBox.information(
                self, "Delete Profile", f"Profile '{name}' is read-only and cannot be deleted."
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

        namespace = self.profile_namespace
        delete_profile_files(name, namespace=namespace)
        self._refresh_workspace_list()

    def _refresh_workspace_list(self):
        """
        Populate the workspace combo box with all saved profile names (without .ini).
        """
        combo = self.toolbar.components.get_action("workspace_combo").widget
        active_profile = getattr(self, "_current_profile_name", None)
        namespace = self.profile_namespace
        if hasattr(combo, "set_quick_profile_provider"):
            combo.set_quick_profile_provider(lambda ns=namespace: list_quick_profiles(namespace=ns))
        if hasattr(combo, "refresh_profiles"):
            combo.refresh_profiles(active_profile)
        else:
            # Fallback for regular QComboBox
            combo.blockSignals(True)
            combo.clear()
            quick_profiles = list_quick_profiles(namespace=namespace)
            items = list(quick_profiles)
            if active_profile and active_profile not in items:
                items.insert(0, active_profile)
            combo.addItems(items)
            if active_profile:
                idx = combo.findText(active_profile)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            if active_profile and active_profile not in quick_profiles:
                combo.setToolTip("Active profile is not in quick select")
            else:
                combo.setToolTip("")
            combo.blockSignals(False)

    ################################################################################
    # Dialog Popups
    ################################################################################

    @SafeSlot()
    def show_workspace_manager(self):
        """
        Show the workspace manager dialog.
        """
        manage_action = self.toolbar.components.get_action("manage_workspaces").action
        if self.manage_dialog is None or not self.manage_dialog.isVisible():
            self.manage_widget = WorkSpaceManager(
                self, target_widget=self, default_profile=self._current_profile_name
            )
            self.manage_dialog = QDialog(modal=False)

            self.manage_dialog.setWindowTitle("Workspace Manager")
            self.manage_dialog.setMinimumSize(1200, 500)
            self.manage_dialog.layout = QVBoxLayout(self.manage_dialog)
            self.manage_dialog.layout.addWidget(self.manage_widget)
            self.manage_dialog.finished.connect(self._manage_dialog_closed)
            self.manage_dialog.show()
            self.manage_dialog.resize(300, 300)
            manage_action.setChecked(True)
        else:
            # If already open, bring it to the front
            self.manage_dialog.raise_()
            self.manage_dialog.activateWindow()
            manage_action.setChecked(True)  # keep it toggle

    def _manage_dialog_closed(self):
        self.manage_widget.close()
        self.manage_widget.deleteLater()
        self.manage_dialog.deleteLater()
        self.manage_dialog = None
        self.toolbar.components.get_action("manage_workspaces").action.setChecked(False)

    ################################################################################
    # Mode Switching
    ################################################################################

    @SafeProperty(str)
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, new_mode: str):
        allowed_modes = ["plot", "device", "utils", "user", "creator"]
        if new_mode not in allowed_modes:
            raise ValueError(f"Invalid mode: {new_mode}")
        self._mode = new_mode
        self.mode_changed.emit(new_mode)
        self._apply_toolbar_layout()

    def _apply_toolbar_layout(self) -> None:
        mode_key = getattr(self, "_mode", "creator")
        if mode_key == "user":
            bundles = ["spacer_bundle", "workspace", "dock_actions"]
        elif mode_key == "creator":
            bundles = [
                "menu_plots",
                "menu_devices",
                "menu_utils",
                "spacer_bundle",
                "workspace",
                "dock_actions",
            ]
        elif mode_key == "plot":
            bundles = ["flat_plots", "spacer_bundle", "workspace", "dock_actions"]
        elif mode_key == "device":
            bundles = ["flat_devices", "spacer_bundle", "workspace", "dock_actions"]
        elif mode_key == "utils":
            bundles = ["flat_utils", "spacer_bundle", "workspace", "dock_actions"]
        else:
            bundles = ["spacer_bundle", "workspace", "dock_actions"]

        if not self._profile_management_enabled:
            flat_only = [b for b in bundles if b.startswith("flat_")]
            if not flat_only:
                flat_only = ["flat_plots", "flat_devices", "flat_utils"]
            bundles = flat_only

        self.toolbar.show_bundles(bundles)

    def prepare_for_shutdown(self) -> None:
        """
        Persist the current workspace snapshot while the UI is still fully visible.
        Called by the main window before initiating widget teardown to avoid capturing
        close-triggered visibility changes.
        """
        if (
            not self._auto_save_upon_exit
            or getattr(self, "_exit_snapshot_written", False)
            or getattr(self, "_destroyed", False)
        ):
            logger.info("ADS prepare_for_shutdown: skipping (already handled or destroyed)")
            return

        name = self._active_profile_name_or_default()

        namespace = self.profile_namespace
        settings = open_user_settings(name, namespace=namespace)
        self._write_snapshot_to_settings(settings)
        set_last_profile(name, namespace=namespace, instance=self._last_profile_instance_id())
        self._exit_snapshot_written = True

    def cleanup(self):
        """
        Cleanup the dock area.
        """
        self.prepare_for_shutdown()
        if self.manage_dialog is not None:
            self.manage_dialog.reject()
            self.manage_dialog = None
        self.delete_all()
        self.dark_mode_button.close()
        self.dark_mode_button.deleteLater()
        self.toolbar.cleanup()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QTabWidget

    app = QApplication(sys.argv)
    apply_theme("dark")
    dispatcher = BECDispatcher(gui_id="ads")
    window = BECMainWindowNoRPC()
    central = QWidget()
    layout = QVBoxLayout(central)
    window.setCentralWidget(central)

    # two dock areas stacked vertically no instance ids
    ads = AdvancedDockArea(mode="creator", enable_profile_management=True)
    ads2 = AdvancedDockArea(mode="creator", enable_profile_management=True)
    layout.addWidget(ads, 1)
    layout.addWidget(ads2, 1)

    # two dock areas inside a tab widget
    tabs = QTabWidget(parent=central)
    ads3 = AdvancedDockArea(mode="creator", enable_profile_management=True, instance_id="AdsTab3")
    ads4 = AdvancedDockArea(mode="creator", enable_profile_management=True, instance_id="AdsTab4")
    tabs.addTab(ads3, "Workspace 3")
    tabs.addTab(ads4, "Workspace 4")
    layout.addWidget(tabs, 1)

    window.show()
    window.resize(800, 1000)

    sys.exit(app.exec())
