from __future__ import annotations

import os
from functools import partial
from typing import TYPE_CHECKING, List, Literal, get_args

import yaml
from bec_lib import config_helper
from bec_lib.bec_yaml_loader import yaml_load
from bec_lib.file_utils import DeviceConfigWriter
from bec_lib.logger import bec_logger
from bec_lib.messages import ConfigAction
from bec_lib.plugin_helper import plugin_package_name, plugin_repo_path
from bec_qthemes import apply_theme, material_icon
from qtpy.QtCore import QMetaObject, Qt, QThreadPool, Signal
from qtpy.QtWidgets import (
    QApplication,
    QFileDialog,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.applications.views.device_manager_view.device_manager_dialogs import (
    ConfigChoiceDialog,
    DeviceFormDialog,
)
from bec_widgets.applications.views.device_manager_view.device_manager_dialogs.upload_redis_dialog import (
    UploadRedisDialog,
)
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.widgets.containers.advanced_dock_area.basic_dock_area import DockAreaWidget
from bec_widgets.widgets.control.device_manager.components import (
    DeviceTable,
    DMConfigView,
    DocstringView,
    OphydValidation,
)
from bec_widgets.widgets.control.device_manager.components._util import SharedSelectionSignal
from bec_widgets.widgets.control.device_manager.components.ophyd_validation.ophyd_validation_utils import (
    ConfigStatus,
    ConnectionStatus,
)
from bec_widgets.widgets.progress.device_initialization_progress_bar.device_initialization_progress_bar import (
    DeviceInitializationProgressBar,
)
from bec_widgets.widgets.services.device_browser.device_item.config_communicator import (
    CommunicateConfigAction,
)
from bec_widgets.widgets.utility.spinner.spinner import SpinnerWidget

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib.client import BECClient

logger = bec_logger.logger

_yes_no_question = partial(
    QMessageBox.question,
    buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    defaultButton=QMessageBox.StandardButton.No,
)


class CustomBusyWidget(QWidget):
    """Custom busy widget to show during device config upload."""

    cancel_requested = Signal()

    def __init__(self, parent=None, client: BECClient | None = None):
        super().__init__(parent=parent)

        # Widgets
        progress = DeviceInitializationProgressBar(parent=self, client=client)

        # Spinner
        spinner = SpinnerWidget(parent=self)
        scale = self._ui_scale()
        spinner_size = int(scale * 0.12) if scale else 1
        spinner_size = max(32, min(spinner_size, 64))
        spinner.setFixedSize(spinner_size, spinner_size)

        # Cancel button
        cancel_button = QPushButton("Cancel Upload", parent=self)
        cancel_button.setIcon(material_icon("cancel"))
        cancel_button.clicked.connect(self.cancel_requested.emit)
        button_height = int(spinner_size * 0.9)
        button_height = max(36, min(button_height, 72))
        aspect_ratio = 3.8  # width / height, visually stable for text buttons
        button_width = int(button_height * aspect_ratio)
        cancel_button.setFixedSize(button_width, button_height)
        color = get_accent_colors()
        cancel_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {color.emergency.name()};
                color: white;
                font-weight: 600;
                border-radius: 6px;
            }}
            """
        )

        # Layout
        content_layout = QVBoxLayout(self)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(16)
        content_layout.addStretch()
        content_layout.addWidget(spinner, 0, Qt.AlignmentFlag.AlignHCenter)
        content_layout.addWidget(progress, 0, Qt.AlignmentFlag.AlignHCenter)
        content_layout.addStretch()
        content_layout.addWidget(cancel_button, 0, Qt.AlignmentFlag.AlignHCenter)

    def _ui_scale(self) -> int:
        parent = self.parent()
        if not parent:
            return 0
        return min(parent.width(), parent.height())

    def showEvent(self, event):
        """Show event to start the spinner."""
        super().showEvent(event)
        for child in self.findChildren(SpinnerWidget):
            child.start()

    def hideEvent(self, event):
        """Hide event to stop the spinner."""
        super().hideEvent(event)
        for child in self.findChildren(SpinnerWidget):
            child.stop()


class DeviceManagerDisplayWidget(DockAreaWidget):
    """Device Manager main display widget. This contains all sub-widgets and the toolbar."""

    RPC = False

    request_ophyd_validation = Signal(list, bool, bool)

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent=parent, variant="compact", *args, **kwargs)

        # State variable for config upload
        self._config_upload_active: bool = False

        # Push to Redis dialog
        self._upload_redis_dialog: UploadRedisDialog | None = None
        self._dialog_validation_connection: QMetaObject.Connection | None = None

        # NOTE: We need here a seperate config helper instance to avoid conflicts with
        # other communications to REDIS as uploading a config through a CommunicationConfigAction
        # will block if we use the config_helper from self.client.config._config_helper
        self._config_helper = config_helper.ConfigHelper(self.client.connector)
        self._shared_selection = SharedSelectionSignal()

        # Custom upload widget for busy overlay
        self._custom_overlay_widget: QWidget | None = None

        # Device Table View widget
        self.device_table_view = DeviceTable(self)

        # Device Config View widget
        self.dm_config_view = DMConfigView(self)

        # Docstring View
        self.dm_docs_view = DocstringView(self)

        # Ophyd Test view
        self.ophyd_widget_view = QWidget(self)
        layout = QVBoxLayout(self.ophyd_widget_view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.ophyd_test_view = OphydValidation(self, hide_legend=False)
        layout.addWidget(self.ophyd_test_view)

        # Validation Results view
        self.validation_results = QTextEdit(self)
        self.validation_results.setReadOnly(True)
        self.validation_results.setPlaceholderText("Validation results will appear here...")
        layout.addWidget(self.validation_results)
        self.ophyd_test_view.item_clicked.connect(self._ophyd_test_item_clicked_cb)

        for signal, slots in [
            (
                self.device_table_view.selected_devices,
                (self.dm_config_view.on_select_config, self.dm_docs_view.on_select_config),
            ),
            (
                self.ophyd_test_view.validation_completed,
                (self.device_table_view.update_device_validation,),
            ),
            (
                self.ophyd_test_view.multiple_validations_completed,
                (self.device_table_view.update_multiple_device_validations,),
            ),
            (self.request_ophyd_validation, (self.ophyd_test_view.change_device_configs,)),
            (
                self.device_table_view.device_configs_changed,
                (self.ophyd_test_view.device_table_config_changed,),
            ),
            (
                self.device_table_view.device_config_in_sync_with_redis,
                (self._update_config_enabled_button,),
            ),
            (self.device_table_view.device_row_dbl_clicked, (self._edit_device_action,)),
        ]:
            for slot in slots:
                signal.connect(slot)

        # Add toolbar
        self._add_toolbar()

        # Build dock layout using shared helpers
        self._build_docks()

        logger.info("Connecting application about to quit signal to device manager view...")
        QApplication.instance().aboutToQuit.connect(self._about_to_quit_handler)

    ##############################
    ### Custom set busy widget ###
    ##############################

    def create_busy_state_widget(self) -> QWidget:
        """Create a custom busy state widget for uploading device configurations."""
        widget = CustomBusyWidget(parent=self, client=self.client)
        widget.cancel_requested.connect(self._cancel_device_config_upload)
        return widget

    ################################
    ### Application quit handler ###
    ################################

    @SafeSlot()
    def _about_to_quit_handler(self):
        """Handle application about to quit event. If config upload is active, cancel it."""
        logger.info("Application is quitting, checking for active config upload...")
        if self._config_upload_active:
            logger.info("Application is quitting, cancelling active config upload...")
            self._config_helper.send_config_request(
                action="cancel", config=None, wait_for_response=True, timeout_s=10
            )
            logger.info("Config upload cancelled.")

    def _set_busy_wrapper(self, enabled: bool):
        """Thin wrapper around set_busy to flip the state variable."""
        self._busy_overlay.set_opacity(0.8)
        self._config_upload_active = enabled
        self.set_busy(enabled=enabled)

    ##############################
    ### Toolbar and Dock setup ###
    ##############################

    def _add_toolbar(self):
        self.toolbar = ModularToolBar(self)

        # Add IO actions
        self._add_io_actions()
        self._add_table_actions()
        self.toolbar.show_bundles(["IO", "Table"])
        self._root_layout.insertWidget(0, self.toolbar)

    def _build_docks(self) -> None:
        # Central device table
        self.device_table_view_dock = self.new(
            self.device_table_view,
            return_dock=True,
            closable=False,
            floatable=False,
            movable=False,
            show_title_bar=False,
        )

        # Bottom area: docstrings
        self.dm_docs_view_dock = self.new(
            self.dm_docs_view,
            where="bottom",
            relative_to=self.device_table_view_dock,
            return_dock=True,
            closable=False,
            floatable=False,
            movable=False,
            show_title_bar=False,
        )
        # Config view left of docstrings
        self.dm_config_view_dock = self.new(
            self.dm_config_view,
            where="left",
            relative_to=self.dm_docs_view_dock,
            return_dock=True,
            closable=False,
            floatable=False,
            movable=False,
            show_title_bar=False,
        )

        # Right area: ophyd test + validation
        self.ophyd_test_dock_view = self.new(
            self.ophyd_widget_view,
            where="right",
            relative_to=self.device_table_view_dock,
            return_dock=True,
            closable=False,
            floatable=False,
            movable=False,
            show_title_bar=False,
        )

        self.set_layout_ratios(splitter_overrides={0: [7, 3], 1: [3, 7]})

    def _add_io_actions(self):
        # Create IO bundle
        io_bundle = ToolbarBundle("IO", self.toolbar.components)

        # Load from disk
        load = MaterialIconAction(
            text_position="under",
            icon_name="file_open",
            parent=self,
            tooltip="Load configuration file from disk",
            label_text="Load Config",
        )
        self.toolbar.components.add_safe("load", load)
        load.action.triggered.connect(self._load_file_action)
        io_bundle.add_action("load")

        # Add safe to disk
        save_to_disk = MaterialIconAction(
            text_position="under",
            icon_name="file_save",
            parent=self,
            tooltip="Save config to disk",
            label_text="Save Config",
        )
        self.toolbar.components.add_safe("save_to_disk", save_to_disk)
        save_to_disk.action.triggered.connect(self._save_to_disk_action)
        io_bundle.add_action("save_to_disk")

        # Add flush config in redis
        flush_redis = MaterialIconAction(
            text_position="under",
            icon_name="delete_sweep",
            parent=self,
            tooltip="Flush current config in BEC Server",
            label_text="Flush loaded Config",
        )
        flush_redis.action.triggered.connect(self._flush_redis_action)
        self.toolbar.components.add_safe("flush_redis", flush_redis)
        io_bundle.add_action("flush_redis")

        # Add load config from redis
        load_redis = MaterialIconAction(
            text_position="under",
            icon_name="cached",
            parent=self,
            tooltip="Load current config from BEC Server",
            label_text="Get loaded Config",
        )
        load_redis.action.triggered.connect(self._load_redis_action)
        self.toolbar.components.add_safe("load_redis", load_redis)
        io_bundle.add_action("load_redis")

        # Update config action
        update_config_redis = MaterialIconAction(
            text_position="under",
            icon_name="cloud_upload",
            parent=self,
            tooltip="Update current config in BEC Server",
            label_text="Update Config",
        )
        update_config_redis.action.setEnabled(False)

        update_config_redis.action.triggered.connect(self._update_redis_action)
        self.toolbar.components.add_safe("update_config_redis", update_config_redis)
        io_bundle.add_action("update_config_redis")

        # Add load config from plugin dir
        self.toolbar.add_bundle(io_bundle)

    # Table actions
    def _add_table_actions(self) -> None:
        table_bundle = ToolbarBundle("Table", self.toolbar.components)

        # Reset composed view
        reset_composed = MaterialIconAction(
            text_position="under",
            icon_name="delete_sweep",
            parent=self,
            tooltip="Reset current composed config view",
            label_text="Reset Config View",
        )
        reset_composed.action.triggered.connect(self._reset_composed_view)
        self.toolbar.components.add_safe("reset_composed", reset_composed)
        table_bundle.add_action("reset_composed")

        # Add device
        add_device = MaterialIconAction(
            text_position="under",
            icon_name="add",
            parent=self,
            tooltip="Add new device",
            label_text="Add Device",
        )
        add_device.action.triggered.connect(self._add_device_action)
        self.toolbar.components.add_safe("add_device", add_device)
        table_bundle.add_action("add_device")

        # Remove device
        remove_device = MaterialIconAction(
            text_position="under",
            icon_name="remove",
            parent=self,
            tooltip="Remove device",
            label_text="Remove Device",
        )
        remove_device.action.triggered.connect(self._remove_device_action)
        self.toolbar.components.add_safe("remove_device", remove_device)
        table_bundle.add_action("remove_device")

        # Rerun validation
        rerun_validation = MaterialIconAction(
            text_position="under",
            icon_name="checklist",
            parent=self,
            tooltip="Run device validation with 'connect' on selected devices",
            label_text="Validate Connection",
        )
        rerun_validation.action.triggered.connect(self._run_validate_connection)
        self.toolbar.components.add_safe("rerun_validation", rerun_validation)
        table_bundle.add_action("rerun_validation")

        # Add load config from plugin dir
        self.toolbar.add_bundle(table_bundle)

    #######################
    ### Action Handlers ###
    #######################

    @SafeSlot()
    @SafeSlot(bool)
    def _run_validate_connection(self, connect: bool = True):
        """Action for the 'rerun_validation' action to rerun validation on selected devices."""
        configs = list(self.device_table_view.get_selected_device_configs())
        if not configs:
            configs = self.device_table_view.get_device_config()
        # Adjust the state of the icons in the device table view
        self.device_table_view.update_multiple_device_validations(
            [
                (cfg, ConfigStatus.UNKNOWN.value, ConnectionStatus.UNKNOWN.value, "")
                for cfg in configs
            ]
        )
        self.request_ophyd_validation.emit(configs, True, connect)

    def _update_config_enabled_button(self, enabled: bool):
        action = self.toolbar.components.get_action("update_config_redis")
        action.action.setEnabled(not enabled)
        if enabled:
            action.action.setToolTip("Push current config to BEC Server")
        else:
            action.action.setToolTip("Current config is in sync with BEC Server, button disabled.")

    @SafeSlot()
    def _load_file_action(self):
        """Action for the 'load' action to load a config from disk for the io_bundle of the toolbar."""
        config_path = self._get_config_base_path()

        # Implement the file loading logic here
        start_dir = os.path.abspath(config_path)
        file_path = self._get_file_path(start_dir, "open_file")
        if file_path:
            self._load_config_from_file(file_path)

    def _get_config_base_path(self) -> str:
        """Get the base path for device configurations."""
        try:
            plugin_path = plugin_repo_path()
            plugin_name = plugin_package_name()
            config_path = os.path.join(plugin_path, plugin_name, "device_configs")
        except ValueError:
            # Get the recovery config path as fallback
            config_path = self._get_recovery_config_path()
            logger.warning(
                f"No plugin repository installed, fallback to recovery config path: {config_path}"
            )
        return config_path

    def _get_file_path(self, start_dir: str, mode: Literal["open_file", "save_file"]) -> str:
        ALLOWED_EXTS = [".yaml", ".yml"]
        filter_str = "YAML files (*.yaml *.yml);;All Files (*)"
        initial_filter = "YAML files (*.yaml *.yml);;"
        if mode == "open_file":
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                caption="Select Config File",
                dir=start_dir,
                filter=filter_str,
                selectedFilter=initial_filter,
            )
        else:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                caption="Save Config File",
                dir=start_dir,
                filter=filter_str,
                selectedFilter=initial_filter,
            )
        if not file_path:
            return ""
        _, ext = os.path.splitext(file_path)
        if ext.lower() not in ALLOWED_EXTS:
            file_path += ".yaml"
        return file_path

    def _load_config_from_file(self, file_path: str):
        """
        Load device config from a given file path and update the device table view.

        Args:
            file_path (str): Path to the configuration file.
        """
        try:
            config = [{"name": k, **v} for k, v in yaml_load(file_path).items()]
        except Exception as e:
            logger.error(f"Failed to load config from file {file_path}. Error: {e}")
            return
        self._open_config_choice_dialog(config)

    def _open_config_choice_dialog(self, config: List[dict]):
        """
        Open a dialog to choose whether to replace or add the loaded config.

        Args:
            config (List[dict]): List of device configurations loaded from the file.
        """
        if len(self.device_table_view.get_device_config()) == 0:
            # If no config is composed yet, load directly
            self.device_table_view.set_device_config(config)
            return
        dialog = ConfigChoiceDialog(self)
        result = dialog.exec()
        if result == ConfigChoiceDialog.Result.REPLACE:
            self.device_table_view.set_device_config(config)
        elif result == ConfigChoiceDialog.Result.ADD:
            self.device_table_view.add_device_configs(config)

    @SafeSlot()
    def _flush_redis_action(self):
        """Action to flush the current config in Redis."""
        if self.client.device_manager is None:
            logger.error("No device manager connected, cannot load config from BEC Server.")
            return
        if len(self.client.device_manager.devices) == 0:
            logger.info("No devices in BEC Server, nothing to flush.")
            QMessageBox.information(
                self, "No Devices", "There is currently no config loaded on the BEC Server."
            )
            return
        reply = _yes_no_question(
            self,
            "Flush BEC Server Config",
            "Do you really want to flush the current config in BEC Server?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.client.config.reset_config()
            logger.info("Successfully flushed configuration in BEC Server.")
            # Check if config is in sync, enable load redis button
            self.device_table_view.device_config_in_sync_with_redis.emit(
                self.device_table_view._is_config_in_sync_with_redis()
            )
            validation_results = self.device_table_view.get_validation_results()
            for config, config_status, connnection_status in validation_results.values():
                if connnection_status == ConnectionStatus.CONNECTED.value:
                    self.device_table_view.update_device_validation(
                        config, config_status, ConnectionStatus.CAN_CONNECT, ""
                    )

    @SafeSlot()
    def _load_redis_action(self):
        """Action for the 'load_redis' action to load the current config from Redis for the io_bundle of the toolbar."""
        if self.client.device_manager is None:
            logger.error("No device manager connected, cannot load config from BEC Server.")
            return
        if not self.device_table_view.get_device_config():
            # If no config is composed yet, load directly
            self.device_table_view.set_device_config(
                self.client.device_manager._get_redis_device_config()
            )
            return
        reply = _yes_no_question(
            self,
            "Load currently active config in BEC Server",
            "Do you really want to discard the current config and reload?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.device_table_view.set_device_config(
                self.client.device_manager._get_redis_device_config()
            )

    @SafeSlot()
    def _update_redis_action(self) -> None | QMessageBox.StandardButton:
        """Action to push the current composition to Redis using the upload dialog."""
        # Check if validations are still running
        if self.ophyd_test_view.running_ophyd_tests is True:
            return QMessageBox.warning(
                self, "Validation in Progress", "Please wait for the validation to finish."
            )

        # Get all device configurations with their validation status
        validation_results = self.device_table_view.get_validation_results()
        # Create and show upload dialog
        self._upload_redis_dialog = UploadRedisDialog(
            parent=self, device_configs=validation_results
        )
        self._upload_redis_dialog.request_ophyd_validation.connect(
            self.request_ophyd_validation.emit
        )

        # Show dialog
        reply = self._upload_redis_dialog.exec_()

        if reply == UploadRedisDialog.UploadAction.OK:
            self._push_composition_to_redis(action="set")
        elif reply == UploadRedisDialog.UploadAction.CANCEL:
            self.ophyd_test_view.cancel_all_validations()
        elif reply == UploadRedisDialog.UploadAction.CONNECTION_TEST_REQUESTED:
            return QMessageBox.information(
                self, "Connection Test Requested", "Running connection test on untested devices."
            )

    def _push_composition_to_redis(self, action: ConfigAction):
        """Push the current device composition to Redis."""
        if action not in get_args(ConfigAction):
            logger.error(f"Invalid config action: {action} for uploading to BEC Server.")
            return
        config = {cfg.pop("name"): cfg for cfg in self.device_table_view.get_device_config()}
        threadpool = QThreadPool.globalInstance()
        comm = CommunicateConfigAction(self._config_helper, None, config, action)
        comm.signals.done.connect(self._handle_push_complete_to_communicator)
        comm.signals.error.connect(self._handle_exception_from_communicator)
        threadpool.start(comm)
        self._set_busy_wrapper(enabled=True)

    def _cancel_device_config_upload(self):
        """Cancel the device configuration upload process."""
        threadpool = QThreadPool.globalInstance()
        comm = CommunicateConfigAction(self._config_helper, None, {}, "cancel")
        # Cancelling will raise an exception in the communicator, so we connect to the failure handler
        comm.signals.error.connect(self._handle_cancel_config_upload_failed)
        threadpool.start(comm)

    def _handle_cancel_config_upload_failed(self, exception: Exception):
        """Handle failure to cancel the config upload."""
        QMessageBox.critical(self, "Error Cancelling Upload", f"{str(exception)}")
        self._set_busy_wrapper(enabled=False)

        validation_results = self.device_table_view.get_validation_results()
        devices_to_update = []
        for config, config_status, connection_status in validation_results.values():
            devices_to_update.append(
                (config, config_status, ConnectionStatus.UNKNOWN.value, "Upload Cancelled")
            )
        # Rerun validation of all devices after cancellation
        self.device_table_view.update_multiple_device_validations(devices_to_update)
        self.ophyd_test_view.change_device_configs(
            [cfg for cfg, _, _, _ in devices_to_update], added=True, skip_validation=False
        )
        # Config is in sync with BEC, so we update the state
        self.device_table_view.device_config_in_sync_with_redis.emit(False)

        # Cleanup custom overlay widget
        if self._custom_overlay_widget is not None:
            self._custom_overlay_widget.close()
            self._custom_overlay_widget.deleteLater()
            self._custom_overlay_widget = None

    def _handle_push_complete_to_communicator(self):
        """Handle completion of the config push to Redis."""
        self._set_busy_wrapper(enabled=False)
        # Cleanup custom overlay widget
        if self._custom_overlay_widget is not None:
            self._custom_overlay_widget.close()
            self._custom_overlay_widget.deleteLater()
            self._custom_overlay_widget = None

    def _handle_exception_from_communicator(self, exception: Exception):
        """Handle exceptions from the config communicator."""
        QMessageBox.critical(
            self,
            "Error Uploading Config",
            f"An error occurred while uploading the configuration to BEC Server:\n{str(exception)}",
        )
        self._set_busy_wrapper(enabled=False)
        if self._custom_overlay_widget is not None:
            self._custom_overlay_widget.close()
            self._custom_overlay_widget.deleteLater()
            self._custom_overlay_widget = None

    @SafeSlot()
    def _save_to_disk_action(self):
        """Action for the 'save_to_disk' action to save the current config to disk."""
        # Check if plugin repo is installed...
        try:
            config_path = self._get_recovery_config_path()
        except ValueError:
            # Get the recovery config path as fallback
            config_path = os.path.abspath(os.path.expanduser("~"))
            logger.warning(f"Failed to find recovery config path, fallback to: {config_path}")

        # Implement the file loading logic here
        file_path = self._get_file_path(config_path, "save_file")
        if file_path:
            config = {cfg.pop("name"): cfg for cfg in self.device_table_view.get_device_config()}
            if os.path.exists(file_path):
                reply = _yes_no_question(
                    self,
                    "Overwrite File",
                    f"The file '{file_path}' already exists. Do you want to overwrite it?",
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
            with open(file_path, "w") as file:
                file.write(yaml.dump(config))

    # Table actions
    @SafeSlot()
    def _reset_composed_view(self):
        """Action for the 'reset_composed_view' action to reset the composed view."""
        reply = _yes_no_question(
            self,
            "Clear View",
            "You are about to clear the current composed config view, please confirm...",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.device_table_view.clear_device_configs()

    @SafeSlot(dict)
    def _edit_device_action(self, device_config: dict):
        """Action to edit a selected device configuration."""
        dialog = DeviceFormDialog(parent=self, add_btn_text="Apply Changes")
        dialog.accepted_data.connect(self._update_device_to_table_from_dialog)
        dialog.set_device_config(device_config)
        dialog.open()

    @SafeSlot()
    def _add_device_action(self):
        """Action for the 'add_device' action to add a new device."""
        dialog = DeviceFormDialog(parent=self, add_btn_text="Add Device")
        dialog.accepted_data.connect(self._add_to_table_from_dialog)
        dialog.open()

    @SafeSlot(dict, int, int, str, str)
    def _update_device_to_table_from_dialog(
        self,
        data: dict,
        config_status: int,
        connection_status: int,
        msg: str,
        old_device_name: str = "",
    ):
        if old_device_name and old_device_name != data.get("name", ""):
            self.device_table_view.remove_device(old_device_name)
        self._add_to_table_from_dialog(data, config_status, connection_status, msg, old_device_name)

    @SafeSlot(dict, int, int, str, str)
    def _add_to_table_from_dialog(
        self,
        data: dict,
        config_status: int,
        connection_status: int,
        msg: str,
        old_device_name: str = "",
    ):
        if connection_status == ConnectionStatus.UNKNOWN.value:
            self.device_table_view.update_device_configs([data], skip_validation=False)
        else:  # Connection status was tested in dialog
            # If device is connected, we remove it from the ophyd validation view
            self.device_table_view.update_device_configs([data], skip_validation=True)
            # Update validation status in device table view and ophyd validation view
            self.ophyd_test_view._on_device_test_completed(
                data, config_status, connection_status, msg
            )

    @SafeSlot()
    def _remove_device_action(self):
        """Action for the 'remove_device' action to remove a device."""
        configs = self.device_table_view.get_selected_device_configs()
        if not configs:
            QMessageBox.warning(
                self, "No devices selected", "Please select devices from the table to remove."
            )
            return
        if self.device_table_view._remove_configs_dialog([cfg["name"] for cfg in configs]):
            self.device_table_view.remove_device_configs(configs)

    @SafeSlot(dict, int, int, str, str)
    def _ophyd_test_item_clicked_cb(
        self, device_config: dict, config_status: int, connection_status: int, msg: str, md_msg: str
    ) -> None:
        self.validation_results.setMarkdown(md_msg)

    def _get_recovery_config_path(self) -> str:
        """Get the recovery config path from the log_writer config."""
        # pylint: disable=protected-access
        log_writer_config = self.client._service_config.config.get("log_writer", {})
        writer = DeviceConfigWriter(service_config=log_writer_config)
        return os.path.abspath(os.path.expanduser(writer.get_recovery_directory()))


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

    app = QApplication(sys.argv)
    w = QWidget()
    l = QVBoxLayout()
    w.setLayout(l)
    apply_theme("dark")
    button = DarkModeButton()
    l.addWidget(button)
    device_manager_view = DeviceManagerDisplayWidget()
    l.addWidget(device_manager_view)
    w.show()
    w.setWindowTitle("Device Manager View")
    screen = app.primaryScreen()
    screen_geometry = screen.availableGeometry()
    screen_width = screen_geometry.width()
    screen_height = screen_geometry.height()
    # 70% of screen height, keep 16:9 ratio
    height = int(screen_height * 0.9)
    width = int(height * (16 / 9))

    # If width exceeds screen width, scale down
    if width > screen_width * 0.9:
        width = int(screen_width * 0.9)
        height = int(width / (16 / 9))

    w.resize(width, height)
    sys.exit(app.exec_())
