from __future__ import annotations

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.messages import ScanHistoryMessage
from bec_qthemes import material_icon
from qtpy import QtCore, QtGui, QtWidgets

from bec_widgets.utils.bec_widget import BECWidget, ConnectionConfig
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot

logger = bec_logger.logger


# TODO check cleanup
# Custom model
class DeviceModel(QtCore.QAbstractListModel):
    def __init__(self, devices=None):
        super().__init__()
        if devices is None:
            devices = {}
        self._devices = sorted(devices.items(), key=lambda x: -x[1])

    @property
    def devices(self):
        """Return the list of devices."""
        return self._devices

    @devices.setter
    def devices(self, value: dict[str, int]):
        self.beginResetModel()
        self._devices = sorted(value.items(), key=lambda x: -x[1])
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.devices)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        name, num_points = self.devices[index.row()]
        if role == QtCore.Qt.DisplayRole:
            return f"{name} ({num_points})"  # fallback display
        elif role == QtCore.Qt.UserRole:
            return name
        elif role == QtCore.Qt.UserRole + 1:
            return num_points
        return None


# Custom delegate for better formatting
class DeviceDelegate(QtWidgets.QStyledItemDelegate):
    def paint(self, painter, option, index):
        name = index.data(QtCore.Qt.UserRole)
        points = index.data(QtCore.Qt.UserRole + 1)

        painter.save()
        painter.drawText(
            option.rect.adjusted(5, 0, -5, 0), QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, name
        )
        painter.drawText(
            option.rect.adjusted(5, 0, -5, 0),
            QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight,
            str(points),
        )
        painter.restore()

    def sizeHint(self, option, index):
        return QtCore.QSize(200, 24)


class ScanHistoryDeviceViewer(BECWidget, QtWidgets.QWidget):
    """ScanHistoryTree is a widget that displays the scan history in a tree format."""

    RPC = False
    PLUGIN = False

    request_history_plot = QtCore.Signal(str, dict)  # (str, ScanHistoryMessage.model_dump())

    def __init__(
        self,
        parent: QtWidgets.QWidget = None,
        client=None,
        config: ConnectionConfig = None,
        gui_id: str = None,
        theme_update: bool = True,
        **kwargs,
    ):
        super().__init__(
            parent=parent,
            client=client,
            config=config,
            gui_id=gui_id,
            theme_update=theme_update,
            **kwargs,
        )
        # Current scan history message
        self.scan_history_msg: ScanHistoryMessage | None = None
        self._selected_device: str = ""
        # Init layout
        layout = QtWidgets.QHBoxLayout(self)
        self.setLayout(layout)
        # Init ComboBox
        self.device_combo = QtWidgets.QComboBox(self)
        colors = get_accent_colors()
        self.request_plotting_button = QtWidgets.QPushButton(
            material_icon("play_arrow", size=(24, 24), color=colors.success),
            "Request Plotting",
            self,
        )
        self.device_model = DeviceModel({})
        self.device_combo.setModel(self.device_model)
        layout.addWidget(self.device_combo)
        layout.addWidget(self.request_plotting_button)
        self.device_combo.setItemDelegate(DeviceDelegate())
        # Connect signals
        self.request_plotting_button.clicked.connect(self._on_request_plotting_clicked)

    @SafeProperty(str)
    def device(self) -> str:
        """Get the currently selected device name."""
        return self._selected_device

    @device.setter
    def device(self, value: str):
        """Set the currently selected device name."""
        if not isinstance(value, str):
            logger.info(f"Device name must be a string {value}.")
        if value not in self.scan_history_msg.device_data_info:
            logger.info(f"Device name must in the list of selected devices {value}.")
        self._selected_device = value

    @SafeSlot()
    def update_devices_from_scan_history(self, msg: ScanHistoryMessage) -> None:
        """Update the device combo box with the scan history message."""
        if not isinstance(msg, ScanHistoryMessage):
            logger.info(f"Received message of type {type(msg)} instead of ScanHistoryMessage.")
            return
        self.scan_history_msg = msg
        self.device_model.devices = msg.device_data_info

    @SafeSlot()
    def clear_view(self, msg: ScanHistoryMessage | None = None) -> None:
        """Clear the device combo box."""
        self.scan_history_msg = None
        self.device_model.devices = {}
        self.device_combo.clear()

    @SafeSlot()
    def _on_request_plotting_clicked(self):
        """Handle the request plotting button click."""
        if self.scan_history_msg is None:
            logger.info("No scan history message available for plotting.")
            return
        current_index = self.device_combo.currentIndex()
        device_name = self.device_combo.model().data(
            self.device_combo.model().index(current_index, 0), QtCore.Qt.UserRole
        )
        logger.info(
            f"Requesting plotting for device: {device_name} with {self.scan_history_msg} points."
        )
        self.request_history_plot.emit((device_name, self.scan_history_msg))


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    viewer = ScanHistoryDeviceViewer()
    viewer.show()
    sys.exit(app.exec_())
