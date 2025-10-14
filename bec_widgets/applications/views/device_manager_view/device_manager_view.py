from __future__ import annotations

import os
from functools import partial
from typing import List

import PySide6QtAds as QtAds
import yaml
from bec_lib import config_helper
from bec_lib.bec_yaml_loader import yaml_load
from bec_lib.file_utils import DeviceConfigWriter
from bec_lib.logger import bec_logger
from bec_lib.plugin_helper import plugin_package_name, plugin_repo_path
from bec_qthemes import apply_theme
from PySide6QtAds import CDockManager, CDockWidget
from qtpy.QtCore import Qt, QThreadPool, QTimer
from qtpy.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bec_widgets import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.help_inspector.help_inspector import HelpInspector
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.widgets.control.device_manager.components import (
    DeviceTableView,
    DMConfigView,
    DMOphydTest,
    DocstringView,
)
from bec_widgets.widgets.control.device_manager.components._util import SharedSelectionSignal
from bec_widgets.widgets.control.device_manager.components.available_device_resources.available_device_resources import (
    AvailableDeviceResources,
)
from bec_widgets.widgets.services.device_browser.device_item.config_communicator import (
    CommunicateConfigAction,
)
from bec_widgets.widgets.services.device_browser.device_item.device_config_dialog import (
    PresetClassDeviceConfigDialog,
)

logger = bec_logger.logger

_yes_no_question = partial(
    QMessageBox.question,
    buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    defaultButton=QMessageBox.StandardButton.No,
)


def set_splitter_weights(splitter: QSplitter, weights: List[float]) -> None:
    """
    Apply initial sizes to a splitter using weight ratios, e.g. [1,3,2,1].
    Works for horizontal or vertical splitters and sets matching stretch factors.
    """

    def apply():
        n = splitter.count()
        if n == 0:
            return
        w = list(weights[:n]) + [1] * max(0, n - len(weights))
        w = [max(0.0, float(x)) for x in w]
        tot_w = sum(w)
        if tot_w <= 0:
            w = [1.0] * n
            tot_w = float(n)
        total_px = (
            splitter.width()
            if splitter.orientation() == Qt.Orientation.Horizontal
            else splitter.height()
        )
        if total_px < 2:
            QTimer.singleShot(0, apply)
            return
        sizes = [max(1, int(total_px * (wi / tot_w))) for wi in w]
        diff = total_px - sum(sizes)
        if diff != 0:
            idx = max(range(n), key=lambda i: w[i])
            sizes[idx] = max(1, sizes[idx] + diff)
        splitter.setSizes(sizes)
        for i, wi in enumerate(w):
            splitter.setStretchFactor(i, max(1, int(round(wi * 100))))

    QTimer.singleShot(0, apply)


class ConfigChoiceDialog(QDialog):
    REPLACE = 1
    ADD = 2
    CANCEL = 0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Load Config")
        layout = QVBoxLayout(self)

        label = QLabel("Do you want to replace the current config or add to it?")
        label.setWordWrap(True)
        layout.addWidget(label)

        # Buttons: equal size, stacked vertically
        self.replace_btn = QPushButton("Replace")
        self.add_btn = QPushButton("Add")
        self.cancel_btn = QPushButton("Cancel")
        btn_layout = QHBoxLayout()
        for btn in (self.replace_btn, self.add_btn, self.cancel_btn):
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

        # Connect signals to explicit slots
        self.replace_btn.clicked.connect(self.accept_replace)
        self.add_btn.clicked.connect(self.accept_add)
        self.cancel_btn.clicked.connect(self.reject_cancel)

        self._result = self.CANCEL

    def accept_replace(self):
        self._result = self.REPLACE
        self.accept()

    def accept_add(self):
        self._result = self.ADD
        self.accept()

    def reject_cancel(self):
        self._result = self.CANCEL
        self.reject()

    def result(self):
        return self._result


AVAILABLE_RESOURCE_IS_READY = False


class DeviceManagerView(BECWidget, QWidget):

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent=parent, client=None, *args, **kwargs)

        self._config_helper = config_helper.ConfigHelper(self.client.connector)
        self._shared_selection = SharedSelectionSignal()

        # Top-level layout hosting a toolbar and the dock manager
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)
        self.dock_manager = CDockManager(self)
        self.dock_manager.setStyleSheet("")
        self._root_layout.addWidget(self.dock_manager)

        # Device Table View widget
        self.device_table_view = DeviceTableView(
            self, shared_selection_signal=self._shared_selection
        )
        self.device_table_view_dock = QtAds.CDockWidget(self.dock_manager, "Device Table", self)
        self.device_table_view_dock.setWidget(self.device_table_view)

        # Device Config View widget
        self.dm_config_view = DMConfigView(self)
        self.dm_config_view_dock = QtAds.CDockWidget(self.dock_manager, "Device Config View", self)
        self.dm_config_view_dock.setWidget(self.dm_config_view)

        # Docstring View
        self.dm_docs_view = DocstringView(self)
        self.dm_docs_view_dock = QtAds.CDockWidget(self.dock_manager, "Docstring View", self)
        self.dm_docs_view_dock.setWidget(self.dm_docs_view)

        # Ophyd Test view
        self.ophyd_test_view = DMOphydTest(self)
        self.ophyd_test_dock_view = QtAds.CDockWidget(self.dock_manager, "Ophyd Test View", self)
        self.ophyd_test_dock_view.setWidget(self.ophyd_test_view)

        # Help Inspector
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.help_inspector = HelpInspector(self)
        layout.addWidget(self.help_inspector)
        text_box = QTextEdit(self)
        text_box.setReadOnly(False)
        text_box.setPlaceholderText("Help text will appear here...")
        layout.addWidget(text_box)
        self.help_inspector_dock = QtAds.CDockWidget(self.dock_manager, "Help Inspector", self)
        self.help_inspector_dock.setWidget(widget)

        # Register callback
        self.help_inspector.bec_widget_help.connect(text_box.setMarkdown)

        # Error Logs View
        self.error_logs_view = QTextEdit(self)
        self.error_logs_view.setReadOnly(True)
        self.error_logs_view.setPlaceholderText("Error logs will appear here...")
        self.error_logs_dock = QtAds.CDockWidget(self.dock_manager, "Error Logs", self)
        self.error_logs_dock.setWidget(self.error_logs_view)
        self.ophyd_test_view.validation_msg_md.connect(self.error_logs_view.setMarkdown)

        # Arrange widgets within the QtAds dock manager
        # Central widget area
        self.central_dock_area = self.dock_manager.setCentralWidget(self.device_table_view_dock)
        # Right area - should be pushed into view if something is active
        self.dock_manager.addDockWidget(
            QtAds.DockWidgetArea.RightDockWidgetArea,
            self.ophyd_test_dock_view,
            self.central_dock_area,
        )
        # create bottom area (2-arg -> area)
        self.bottom_dock_area = self.dock_manager.addDockWidget(
            QtAds.DockWidgetArea.BottomDockWidgetArea, self.dm_docs_view_dock
        )

        # YAML view left of docstrings (docks relative to bottom area)
        self.dock_manager.addDockWidget(
            QtAds.DockWidgetArea.LeftDockWidgetArea, self.dm_config_view_dock, self.bottom_dock_area
        )

        # Error/help area right of docstrings (dock relative to bottom area)
        area = self.dock_manager.addDockWidget(
            QtAds.DockWidgetArea.RightDockWidgetArea,
            self.help_inspector_dock,
            self.bottom_dock_area,
        )
        self.dock_manager.addDockWidgetTabToArea(self.error_logs_dock, area)

        for dock in self.dock_manager.dockWidgets():
            dock.setFeature(CDockWidget.DockWidgetClosable, False)
            dock.setFeature(CDockWidget.DockWidgetFloatable, False)
            dock.setFeature(CDockWidget.DockWidgetMovable, False)

        # Apply stretch after the layout is done
        self.set_default_view([2, 8, 2], [7, 3])

        for signal, slots in [
            (
                self.device_table_view.selected_devices,
                (self.dm_config_view.on_select_config, self.dm_docs_view.on_select_config),
            ),
            (
                self.ophyd_test_view.device_validated,
                (self.device_table_view.update_device_validation,),
            ),
            (
                self.device_table_view.device_configs_changed,
                (self.ophyd_test_view.change_device_configs,),
            ),
        ]:
            for slot in slots:
                signal.connect(slot)

        # Once available resource is ready, add it to the view again
        if AVAILABLE_RESOURCE_IS_READY:
            # Available Resources Widget
            self.available_devices = AvailableDeviceResources(
                self, shared_selection_signal=self._shared_selection
            )
            self.available_devices_dock = QtAds.CDockWidget(
                self.dock_manager, "Available Devices", self
            )
            self.available_devices_dock.setWidget(self.available_devices)
            # Connect slots for available reosource
            for signal, slots in [
                (
                    self.available_devices.selected_devices,
                    (self.dm_config_view.on_select_config, self.dm_docs_view.on_select_config),
                ),
                (
                    self.device_table_view.device_configs_changed,
                    (self.available_devices.mark_devices_used,),
                ),
                (
                    self.available_devices.add_selected_devices,
                    (self.device_table_view.add_device_configs,),
                ),
                (
                    self.available_devices.del_selected_devices,
                    (self.device_table_view.remove_device_configs,),
                ),
            ]:
                for slot in slots:
                    signal.connect(slot)

        # Add toolbar
        self._add_toolbar()

    def _add_toolbar(self):
        self.toolbar = ModularToolBar(self)

        # Add IO actions
        self._add_io_actions()
        self._add_table_actions()
        self.toolbar.show_bundles(["IO", "Table"])
        self._root_layout.insertWidget(0, self.toolbar)

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

        # Add load config from redis
        load_redis = MaterialIconAction(
            text_position="under",
            icon_name="cached",
            parent=self,
            tooltip="Load current config from Redis",
            label_text="Get Current Config",
        )
        load_redis.action.triggered.connect(self._load_redis_action)
        self.toolbar.components.add_safe("load_redis", load_redis)
        io_bundle.add_action("load_redis")

        # Update config action
        update_config_redis = MaterialIconAction(
            text_position="under",
            icon_name="cloud_upload",
            parent=self,
            tooltip="Update current config in Redis",
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
            label_text="Reset Config",
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
        rerun_validation.action.triggered.connect(self._rerun_validation_action)
        self.toolbar.components.add_safe("rerun_validation", rerun_validation)
        table_bundle.add_action("rerun_validation")

        # Add load config from plugin dir
        self.toolbar.add_bundle(table_bundle)

    # IO actions
    def _coming_soon(self):
        return QMessageBox.question(
            self,
            "Not implemented yet",
            "This feature has not been implemented yet, will be coming soon...!!",
            QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

    @SafeSlot()
    def _load_file_action(self):
        """Action for the 'load' action to load a config from disk for the io_bundle of the toolbar."""
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

        # Implement the file loading logic here
        start_dir = os.path.abspath(config_path)
        file_path, _ = QFileDialog.getOpenFileName(
            self, caption="Select Config File", dir=start_dir
        )
        self._load_config_from_file(file_path)

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
        dialog = ConfigChoiceDialog(self)
        if dialog.exec():
            if dialog.result() == ConfigChoiceDialog.REPLACE:
                self.device_table_view.set_device_config(config)
            elif dialog.result() == ConfigChoiceDialog.ADD:
                self.device_table_view.add_device_configs(config)

    # TODO would we ever like to add the current config to an existing composition
    @SafeSlot()
    def _load_redis_action(self):
        """Action for the 'load_redis' action to load the current config from Redis for the io_bundle of the toolbar."""
        reply = _yes_no_question(
            self,
            "Load currently active config",
            "Do you really want to discard the current config and reload?",
        )
        if reply == QMessageBox.StandardButton.Yes and self.client.device_manager is not None:
            self.device_table_view.set_device_config(
                self.client.device_manager._get_redis_device_config()
            )
        else:
            return

    @SafeSlot()
    def _update_redis_action(self):
        """Action to push the current composition to Redis"""
        reply = _yes_no_question(
            self,
            "Push composition to Redis",
            "Do you really want to replace the active configuration in the BEC server with the current composition? ",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if self.device_table_view.table.contains_invalid_devices():
            return QMessageBox.warning(
                self, "Validation has errors!", "Please resolve before proceeding."
            )
        if self.ophyd_test_view.validation_running():
            return QMessageBox.warning(
                self, "Validation has not completed.", "Please wait for the validation to finish."
            )
        self._push_composition_to_redis()

    def _push_composition_to_redis(self):
        config = {cfg.pop("name"): cfg for cfg in self.device_table_view.table.all_configs()}
        threadpool = QThreadPool.globalInstance()
        comm = CommunicateConfigAction(self._config_helper, None, config, "set")
        threadpool.start(comm)

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
        file_path, _ = QFileDialog.getSaveFileName(
            self, caption="Save Config File", dir=config_path
        )
        if file_path:
            config = {cfg.pop("name"): cfg for cfg in self.device_table_view.get_device_config()}
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

    # TODO Bespoke Form to add a new device
    @SafeSlot()
    def _add_device_action(self):
        """Action for the 'add_device' action to add a new device."""
        dialog = PresetClassDeviceConfigDialog(parent=self)
        dialog.accepted_data.connect(self._add_to_table_from_dialog)
        dialog.open()

    @SafeSlot(dict)
    def _add_to_table_from_dialog(self, data):
        self.device_table_view.add_device_configs([data])

    @SafeSlot()
    def _remove_device_action(self):
        """Action for the 'remove_device' action to remove a device."""
        self.device_table_view.remove_selected_rows()

    @SafeSlot()
    @SafeSlot(bool)
    def _rerun_validation_action(self, connect: bool = True):
        """Action for the 'rerun_validation' action to rerun validation on selected devices."""
        configs = self.device_table_view.table.selected_configs()
        self.ophyd_test_view.change_device_configs(configs, True, connect)

    ####### Default view has to be done with setting up splitters ########
    def set_default_view(
        self, horizontal_weights: list, vertical_weights: list
    ):  # TODO separate logic for all ads based widgets
        """Apply initial weights to every horizontal and vertical splitter.

        Examples:
            horizontal_weights = [1, 3, 2, 1]
            vertical_weights   = [3, 7]  # top:bottom = 30:70
        """
        splitters_h = []
        splitters_v = []
        for splitter in self.findChildren(QSplitter):
            if splitter.orientation() == Qt.Orientation.Horizontal:
                splitters_h.append(splitter)
            elif splitter.orientation() == Qt.Orientation.Vertical:
                splitters_v.append(splitter)

        def apply_all():
            for s in splitters_h:
                set_splitter_weights(s, horizontal_weights)
            for s in splitters_v:
                set_splitter_weights(s, vertical_weights)

        QTimer.singleShot(0, apply_all)

    def set_stretch(
        self, *, horizontal=None, vertical=None
    ):  # TODO separate logic for all ads based widgets
        """Update splitter weights and re-apply to all splitters.

        Accepts either a list/tuple of weights (e.g., [1,3,2,1]) or a role dict
        for convenience: horizontal roles = {"left","center","right"},
        vertical roles = {"top","bottom"}.
        """

        def _coerce_h(x):
            if x is None:
                return None
            if isinstance(x, (list, tuple)):
                return list(map(float, x))
            if isinstance(x, dict):
                return [
                    float(x.get("left", 1)),
                    float(x.get("center", x.get("middle", 1))),
                    float(x.get("right", 1)),
                ]
            return None

        def _coerce_v(x):
            if x is None:
                return None
            if isinstance(x, (list, tuple)):
                return list(map(float, x))
            if isinstance(x, dict):
                return [float(x.get("top", 1)), float(x.get("bottom", 1))]
            return None

        h = _coerce_h(horizontal)
        v = _coerce_v(vertical)
        if h is None:
            h = [1, 1, 1]
        if v is None:
            v = [1, 1]
        self.set_default_view(h, v)

    def _get_recovery_config_path(self) -> str:
        """Get the recovery config path from the log_writer config."""
        # pylint: disable=protected-access
        log_writer_config = self.client._service_config.config.get("log_writer", {})
        writer = DeviceConfigWriter(service_config=log_writer_config)
        return os.path.abspath(os.path.expanduser(writer.get_recovery_directory()))


if __name__ == "__main__":
    import sys
    from copy import deepcopy

    from bec_lib.bec_yaml_loader import yaml_load
    from qtpy.QtWidgets import QApplication

    from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

    app = QApplication(sys.argv)
    w = QWidget()
    l = QVBoxLayout()
    w.setLayout(l)
    apply_theme("dark")
    button = DarkModeButton()
    l.addWidget(button)
    device_manager_view = DeviceManagerView()
    l.addWidget(device_manager_view)
    # config_path = "/Users/appel_c/work_psi_awi/bec_workspace/csaxs_bec/csaxs_bec/device_configs/first_light.yaml"
    # cfg = yaml_load(config_path)
    # cfg.update({"device_will_fail": {"name": "device_will_fail", "some_param": 1}})

    # # config = device_manager_view.client.device_manager._get_redis_device_config()
    # device_manager_view.device_table_view.set_device_config(cfg)
    w.show()
    w.setWindowTitle("Device Manager View")
    w.resize(1920, 1080)
    # developer_view.set_stretch(horizontal=[1, 3, 2], vertical=[5, 5]) #can be set during runtime
    sys.exit(app.exec_())
