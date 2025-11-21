"""Top Level wrapper for device_manager widget"""

from __future__ import annotations

import os

from bec_lib.bec_yaml_loader import yaml_load
from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy import QtCore, QtWidgets
from qtpy.QtGui import QIcon

from bec_widgets.applications.views.device_manager_view.device_manager_view import DeviceManagerView
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot

logger = bec_logger.logger


class DeviceManagerWidget(BECWidget, QtWidgets.QWidget):

    def __init__(self, parent=None, client=None):
        super().__init__(client=client, parent=parent)
        self.stacked_layout = QtWidgets.QStackedLayout()
        self.stacked_layout.setContentsMargins(0, 0, 0, 0)
        self.stacked_layout.setSpacing(0)
        self.stacked_layout.setStackingMode(QtWidgets.QStackedLayout.StackAll)
        self.setLayout(self.stacked_layout)

        # Add device manager view
        self.device_manager_view = DeviceManagerView()
        self.stacked_layout.addWidget(self.device_manager_view)

        # Add overlay widget
        self._overlay_widget = QtWidgets.QWidget(self)
        self._customize_overlay()
        self.stacked_layout.addWidget(self._overlay_widget)
        self.stacked_layout.setCurrentWidget(self._overlay_widget)

    def _customize_overlay(self):
        self._overlay_widget.setAutoFillBackground(True)
        self._overlay_layout = QtWidgets.QVBoxLayout()
        self._overlay_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._overlay_widget.setLayout(self._overlay_layout)
        self._overlay_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding
        )
        # Load current config
        self.button_load_current_config = QtWidgets.QPushButton("Load Current Config")
        icon = material_icon(icon_name="database", size=(24, 24), icon_type=QIcon)
        self.button_load_current_config.setIcon(icon)
        self._overlay_layout.addWidget(self.button_load_current_config)
        self.button_load_current_config.clicked.connect(self._load_config_clicked)
        # Load config from disk
        self.button_load_config_from_file = QtWidgets.QPushButton("Load Config From File")
        icon = material_icon(icon_name="folder", size=(24, 24), icon_type=QIcon)
        self.button_load_config_from_file.setIcon(icon)
        self._overlay_layout.addWidget(self.button_load_config_from_file)
        self.button_load_config_from_file.clicked.connect(self._load_config_from_file_clicked)
        self._overlay_widget.setVisible(True)

    def _load_config_from_file_clicked(self):
        """Handle click on 'Load Config From File' button."""
        start_dir = os.path.expanduser("~")
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, caption="Select Config File", dir=start_dir
        )
        if file_path:
            self._load_config_from_file(file_path)

    def _load_config_from_file(self, file_path: str):
        try:
            config = yaml_load(file_path)
        except Exception as e:
            logger.error(f"Failed to load config from file {file_path}. Error: {e}")
            return
        config_list = []
        for name, cfg in config.items():
            config_list.append(cfg)
            config_list[-1]["name"] = name
        self.device_manager_view.device_table_view.set_device_config(config_list)
        # self.device_manager_view.ophyd_test.on_device_config_update(config)
        self.stacked_layout.setCurrentWidget(self.device_manager_view)

    @SafeSlot()
    def _load_config_clicked(self):
        """Handle click on 'Load Current Config' button."""
        config = self.client.device_manager._get_redis_device_config()
        self.device_manager_view.device_table_view.set_device_config(config)
        self.stacked_layout.setCurrentWidget(self.device_manager_view)


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    from bec_widgets.utils.colors import apply_theme

    apply_theme("light")

    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    widget.setLayout(layout)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    device_manager = DeviceManagerWidget()
    # config = device_manager.client.device_manager._get_redis_device_config()
    # device_manager.device_table_view.set_device_config(config)
    layout.addWidget(device_manager)
    from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

    dark_mode_button = DarkModeButton()
    layout.addWidget(dark_mode_button)
    widget.show()
    device_manager.setWindowTitle("Device Manager View")
    device_manager.resize(1600, 1200)
    # developer_view.set_stretch(horizontal=[1, 3, 2], vertical=[5, 5]) #can be set during runtime
    sys.exit(app.exec_())
