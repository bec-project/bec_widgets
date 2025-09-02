from __future__ import annotations

import os
from typing import TYPE_CHECKING, List

import PySide6QtAds as QtAds
import yaml
from bec_lib.bec_yaml_loader import yaml_load
from bec_lib.file_utils import DeviceConfigWriter
from bec_lib.logger import bec_logger
from bec_lib.plugin_helper import plugin_package_name, plugin_repo_path
from bec_qthemes import apply_theme
from PySide6QtAds import CDockManager, CDockWidget
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import QFileDialog, QMessageBox, QSplitter, QVBoxLayout, QWidget

from bec_widgets import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area import AdvancedDockArea
from bec_widgets.widgets.control.device_manager.components import (
    DeviceTableView,
    DMConfigView,
    DMOphydTest,
    DocstringView,
)
from bec_widgets.widgets.control.device_manager.components.available_device_resources.available_device_resources import (
    AvailableDeviceResources,
)

if TYPE_CHECKING:
    from bec_lib.client import BECClient

logger = bec_logger.logger


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
            splitter.width() if splitter.orientation() == Qt.Horizontal else splitter.height()
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


class DeviceManagerView(BECWidget, QWidget):

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent=parent, client=None, *args, **kwargs)

        # Top-level layout hosting a toolbar and the dock manager
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)
        self.dock_manager = CDockManager(self)
        self._root_layout.addWidget(self.dock_manager)

        # Available Resources Widget
        self.available_devices = AvailableDeviceResources(self)
        self.available_devices_dock = QtAds.CDockWidget("Available Devices", self)
        self.available_devices_dock.setWidget(self.available_devices)

        # Device Table View widget
        self.device_table_view = DeviceTableView(self)
        self.device_table_view_dock = QtAds.CDockWidget("Device Table", self)
        self.device_table_view_dock.setWidget(self.device_table_view)

        # Device Config View widget
        self.dm_config_view = DMConfigView(self)
        self.dm_config_view_dock = QtAds.CDockWidget("Device Config View", self)
        self.dm_config_view_dock.setWidget(self.dm_config_view)

        # Docstring View
        self.dm_docs_view = DocstringView(self)
        self.dm_docs_view_dock = QtAds.CDockWidget("Docstring View", self)
        self.dm_docs_view_dock.setWidget(self.dm_docs_view)

        # Ophyd Test view
        self.ophyd_test_view = DMOphydTest(self)
        self.ophyd_test_dock_view = QtAds.CDockWidget("Ophyd Test View", self)
        self.ophyd_test_dock_view.setWidget(self.ophyd_test_view)

        # Arrange widgets within the QtAds dock manager

        # Central widget area
        self.central_dock_area = self.dock_manager.setCentralWidget(self.device_table_view_dock)
        self.dock_manager.addDockWidget(
            QtAds.DockWidgetArea.BottomDockWidgetArea,
            self.dm_docs_view_dock,
            self.central_dock_area,
        )

        # Left Area
        self.left_dock_area = self.dock_manager.addDockWidget(
            QtAds.DockWidgetArea.LeftDockWidgetArea, self.available_devices_dock
        )
        self.dock_manager.addDockWidget(
            QtAds.DockWidgetArea.BottomDockWidgetArea, self.dm_config_view_dock, self.left_dock_area
        )

        # Right area
        self.dock_manager.addDockWidget(
            QtAds.DockWidgetArea.RightDockWidgetArea, self.ophyd_test_dock_view
        )

        for dock in self.dock_manager.dockWidgets():
            # dock.setFeature(CDockWidget.DockWidgetDeleteOnClose, True)#TODO implement according to MonacoDock or AdvancedDockArea
            # dock.setFeature(CDockWidget.CustomCloseHandling, True) #TODO same
            dock.setFeature(CDockWidget.DockWidgetClosable, False)
            dock.setFeature(CDockWidget.DockWidgetFloatable, False)
            dock.setFeature(CDockWidget.DockWidgetMovable, False)

        # Fetch all dock areas of the dock widgets (on our case always one dock area)
        for dock in self.dock_manager.dockWidgets():
            area = dock.dockAreaWidget()
            area.titleBar().setVisible(False)

        # Apply stretch after the layout is done
        self.set_default_view([2, 8, 2], [3, 1])
        # self.set_default_view([2, 8, 2], [2, 2, 4])

        # Connect slots
        self.device_table_view.selected_device.connect(self.dm_config_view.on_select_config)
        self.device_table_view.selected_device.connect(self.dm_docs_view.on_select_config)
        self.ophyd_test_view.device_validated.connect(
            self.device_table_view.update_device_validation
        )
        self.device_table_view.device_configs_added.connect(self.ophyd_test_view.add_device_configs)
        self.device_table_view.device_configs_added.connect(
            self.available_devices.update_devices_state_name_outside
        )

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

        # Add load config from plugin dir
        self.toolbar.add_bundle(io_bundle)

        load = MaterialIconAction(
            icon_name="file_open", parent=self, tooltip="Load configuration file from disk"
        )
        self.toolbar.components.add_safe("load", load)
        load.action.triggered.connect(self._load_file_action)
        io_bundle.add_action("load")

        # Add safe to disk
        safe_to_disk = MaterialIconAction(
            icon_name="file_save", parent=self, tooltip="Save config to disk"
        )
        self.toolbar.components.add_safe("safe_to_disk", safe_to_disk)
        safe_to_disk.action.triggered.connect(self._safe_to_disk_action)
        io_bundle.add_action("safe_to_disk")

        # Add load config from redis
        load_redis = MaterialIconAction(
            icon_name="cached", parent=self, tooltip="Load current config from Redis"
        )
        load_redis.action.triggered.connect(self._load_redis_action)
        self.toolbar.components.add_safe("load_redis", load_redis)
        io_bundle.add_action("load_redis")

        # Update config action
        update_config_redis = MaterialIconAction(
            icon_name="cloud_upload", parent=self, tooltip="Update current config in Redis"
        )
        update_config_redis.action.triggered.connect(self._update_redis_action)
        self.toolbar.components.add_safe("update_config_redis", update_config_redis)
        io_bundle.add_action("update_config_redis")

    # Table actions

    def _add_table_actions(self) -> None:
        table_bundle = ToolbarBundle("Table", self.toolbar.components)

        # Add load config from plugin dir
        self.toolbar.add_bundle(table_bundle)

        # Reset composed view
        reset_composed = MaterialIconAction(
            icon_name="delete_sweep", parent=self, tooltip="Reset current composed config view"
        )
        reset_composed.action.triggered.connect(self._reset_composed_view)
        self.toolbar.components.add_safe("reset_composed", reset_composed)
        table_bundle.add_action("reset_composed")

        # Add device
        add_device = MaterialIconAction(icon_name="add", parent=self, tooltip="Add new device")
        add_device.action.triggered.connect(self._add_device_action)
        self.toolbar.components.add_safe("add_device", add_device)
        table_bundle.add_action("add_device")

        # Remove device
        remove_device = MaterialIconAction(icon_name="remove", parent=self, tooltip="Remove device")
        remove_device.action.triggered.connect(self._remove_device_action)
        self.toolbar.components.add_safe("remove_device", remove_device)
        table_bundle.add_action("remove_device")

        # Rerun validation
        rerun_validation = MaterialIconAction(
            icon_name="checklist", parent=self, tooltip="Run device validation on selected devices"
        )
        rerun_validation.action.triggered.connect(self._rerun_validation_action)
        self.toolbar.components.add_safe("rerun_validation", rerun_validation)
        table_bundle.add_action("rerun_validation")

        # Most likly, no actions on available devices
        # Actions (vielleicht bundle fuer available devices )
        # - reset composed view
        # - add new device (EpicsMotor, EpicsMotorECMC, EpicsSignal, CustomDevice)
        # - remove device
        # - rerun validation (with/without connect)

    # IO actions

    @SafeSlot()
    def _load_file_action(self):
        """Action for the 'load' action to load a config from disk for the io_bundle of the toolbar."""
        # Check if plugin repo is installed...
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
        if file_path:
            try:
                config = yaml_load(file_path)
            except Exception as e:
                logger.error(f"Failed to load config from file {file_path}. Error: {e}")
                return
            self.device_table_view.set_device_config(
                config
            )  # TODO ADD QDialog with 'replace', 'add' & 'cancel'

    # TODO would we ever like to add the current config to an existing composition
    @SafeSlot()
    def _load_redis_action(self):
        """Action for the 'load_redis' action to load the current config from Redis for the io_bundle of the toolbar."""
        reply = QMessageBox.question(
            self,
            "Load currently active config",
            "Do you really want to flush the current config and reload?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            cfg = {}
            config_list = self.client.device_manager._get_redis_device_config()
            for item in config_list:
                k = item["name"]
                item.pop("name")
                cfg[k] = item
            self.device_table_view.set_device_config(cfg)
        else:
            return

    @SafeSlot()
    def _safe_to_disk_action(self):
        """Action for the 'safe_to_disk' action to save the current config to disk."""
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
            config = self.device_table_view.get_device_config()
            with open(file_path, "w") as file:
                file.write(yaml.dump(config))

    # TODO add here logic, should be asyncronous, but probably block UI, and show a loading spinner. If failed, it should report..
    @SafeSlot()
    def _update_redis_action(self):
        """Action for the 'update_redis' action to update the current config in Redis."""
        config = self.device_table_view.get_device_config()
        reply = QMessageBox.question(
            self,
            "Not implemented yet",
            "This feature has not been implemented yet, will be coming soon...!!",
            QMessageBox.Cancel,
            QMessageBox.Cancel,
        )

    # Table actions

    @SafeSlot()
    def _reset_composed_view(self):
        """Action for the 'reset_composed_view' action to reset the composed view."""
        reply = QMessageBox.question(
            self,
            "Clear View",
            "You are about to clear the current composed config view, please confirm...",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.device_table_view.clear_device_configs()

    # TODO Here we would like to implement a custom popup view, that allows to add new devices
    # We want to have a combobox to choose from EpicsMotor, EpicsMotorECMC, EpicsSignal, EpicsSignalRO, and maybe EpicsSignalWithRBV and custom Device
    # For all default Epics devices, we would like to preselect relevant fields, and prompt them with the proper deviceConfig args already, i.e. 'prefix', 'read_pv', 'write_pv' etc..
    # For custom Device, they should receive all options. It might be cool to get a side panel with docstring view of the class upon inspecting it to make it easier in case deviceConfig entries are required..
    @SafeSlot()
    def _add_device_action(self):
        """Action for the 'add_device' action to add a new device."""
        # Implement the logic to add a new device
        reply = QMessageBox.question(
            self,
            "Not implemented yet",
            "This feature has not been implemented yet, will be coming soon...!!",
            QMessageBox.Cancel,
            QMessageBox.Cancel,
        )

    # TODO fix the device table remove actions. This is currently not working properly...
    @SafeSlot()
    def _remove_device_action(self):
        """Action for the 'remove_device' action to remove a device."""
        reply = QMessageBox.question(
            self,
            "Not implemented yet",
            "This feature has not been implemented yet, will be coming soon...!!",
            QMessageBox.Cancel,
            QMessageBox.Cancel,
        )

    # TODO implement proper logic for validation. We should also carefully review how these jobs update the table, and how we can cancel pending validations
    # in case they are no longer relevant. We might want to 'block' the interactivity on the items for which validation runs with 'connect'!
    @SafeSlot()
    def _rerun_validation_action(self):
        """Action for the 'rerun_validation' action to rerun validation on selected devices."""
        # Implement the logic to rerun validation on selected devices
        reply = QMessageBox.question(
            self,
            "Not implemented yet",
            "This feature has not been implemented yet, will be coming soon...!!",
            QMessageBox.Cancel,
            QMessageBox.Cancel,
        )

    ####### Default view has to be done with setting up splitters ########
    def set_default_view(self, horizontal_weights: list, vertical_weights: list):
        """Apply initial weights to every horizontal and vertical splitter.

        Examples:
            horizontal_weights = [1, 3, 2, 1]
            vertical_weights   = [3, 7]  # top:bottom = 30:70
        """
        splitters_h = []
        splitters_v = []
        for splitter in self.findChildren(QSplitter):
            if splitter.orientation() == Qt.Horizontal:
                splitters_h.append(splitter)
            elif splitter.orientation() == Qt.Vertical:
                splitters_v.append(splitter)

        def apply_all():
            for s in splitters_h:
                set_splitter_weights(s, horizontal_weights)
            for s in splitters_v:
                set_splitter_weights(s, vertical_weights)

        QTimer.singleShot(0, apply_all)

    def set_stretch(self, *, horizontal=None, vertical=None):
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
        log_writer_config: BECClient = self.client._service_config.config.get("log_writer", {})
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
