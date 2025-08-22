"""Top Level wrapper for device_manager widget"""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy import QtCore, QtWidgets

from bec_widgets.examples.device_manager_view.device_manager_view import DeviceManagerView
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot


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
        self._overlay_widget.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1,stop:0 #ffffff, stop:1 #e0e0e0);"
        )
        self._overlay_widget.setAutoFillBackground(True)
        self._overlay_layout = QtWidgets.QVBoxLayout()
        self._overlay_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._overlay_widget.setLayout(self._overlay_layout)
        self._overlay_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding
        )
        self.button_load_current_config = QtWidgets.QPushButton("Load Current Config")
        icon = material_icon(icon_name="database", size=(24, 24), convert_to_pixmap=False)
        self.button_load_current_config.setIcon(icon)
        self._overlay_layout.addWidget(self.button_load_current_config)
        self.button_load_current_config.clicked.connect(self._load_config_clicked)
        self._overlay_widget.setVisible(True)

    @SafeSlot()
    def _load_config_clicked(self):
        """Handle click on 'Load Current Config' button."""
        config = self.client.device_manager._get_redis_device_config()
        self.device_manager_view.device_table_view.set_device_config(config)
        self.device_manager_view.ophyd_test.on_device_config_update(config)
        self.stacked_layout.setCurrentWidget(self.device_manager_view)


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    device_manager = DeviceManagerWidget()
    # config = device_manager.client.device_manager._get_redis_device_config()
    # device_manager.device_table_view.set_device_config(config)
    device_manager.show()
    device_manager.setWindowTitle("Device Manager View")
    device_manager.resize(1600, 1200)
    # developer_view.set_stretch(horizontal=[1, 3, 2], vertical=[5, 5]) #can be set during runtime
    sys.exit(app.exec_())
