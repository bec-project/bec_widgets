"""Module for displaying scan history devices in a viewer widget."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bec_lib.logger import bec_logger
from bec_lib.messages import ScanHistoryMessage
from bec_qthemes import material_icon
from qtpy import QtCore, QtWidgets

from bec_widgets.utils.bec_widget import BECWidget, ConnectionConfig
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeSlot

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib.messages import _StoredDataInfo

logger = bec_logger.logger


class SignalModel(QtCore.QAbstractListModel):
    """Custom model for displaying scan history signals in a combo box."""

    def __init__(self, parent=None, signals: dict[str, _StoredDataInfo] = None):
        super().__init__(parent)
        if signals is None:
            signals = {}
        self._signals: list[tuple[str, _StoredDataInfo]] = sorted(
            signals.items(), key=lambda x: -x[1].shape[0]
        )

    @property
    def signals(self) -> list[tuple[str, _StoredDataInfo]]:
        """Return the list of devices."""
        return self._signals

    @signals.setter
    def signals(self, value: dict[str, _StoredDataInfo]):
        self.beginResetModel()
        self._signals = sorted(value.items(), key=lambda x: -x[1].shape[0])
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._signals)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        name, info = self.signals[index.row()]
        if role == QtCore.Qt.DisplayRole:
            return f"{name} {info.shape}"  # fallback display
        elif role == QtCore.Qt.UserRole:
            return name
        elif role == QtCore.Qt.UserRole + 1:
            return info.shape
        return None


# Custom delegate for better formatting
class SignalDelegate(QtWidgets.QStyledItemDelegate):
    """Custom delegate for displaying device names and points in the combo box."""

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

    request_history_plot = QtCore.Signal(str, str, str)  # (scan_id, device_name, signal_name)

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
        self._last_device_name: str | None = None
        self._last_signal_name: str | None = None
        # Init layout
        layout = QtWidgets.QVBoxLayout(self)
        self.setLayout(layout)
        # Init widgets
        self.device_combo = QtWidgets.QComboBox(parent=self)
        self.signal_combo = QtWidgets.QComboBox(parent=self)
        colors = get_accent_colors()
        self.request_plotting_button = QtWidgets.QPushButton(
            material_icon("play_arrow", size=(24, 24), color=colors.success),
            "Request Plotting",
            self,
        )
        self.signal_model = SignalModel(parent=self.signal_combo)
        self.signal_combo.setModel(self.signal_model)
        self.signal_combo.setItemDelegate(SignalDelegate())
        self._init_layout()
        # Connect signals
        self.request_plotting_button.clicked.connect(self._on_request_plotting_clicked)
        self.device_combo.currentTextChanged.connect(self._signal_combo_update)

    def _init_layout(self):
        """Initialize the layout for the device viewer."""
        main_layout = self.layout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        # horzizontal layout for device combo and signal combo boxes
        widget = QtWidgets.QWidget(self)
        hor_layout = QtWidgets.QHBoxLayout()
        hor_layout.setContentsMargins(0, 0, 0, 0)
        hor_layout.setSpacing(0)
        widget.setLayout(hor_layout)
        hor_layout.addWidget(self.device_combo)
        hor_layout.addWidget(self.signal_combo)
        main_layout.addWidget(widget)
        main_layout.addWidget(self.request_plotting_button)

    @SafeSlot(dict, dict)
    def update_devices_from_scan_history(self, msg: dict, metadata: dict | None = None) -> None:
        """Update the device combo box with the scan history message.

        Args:
            msg (ScanHistoryMessage): The scan history message containing device data.
        """
        msg = ScanHistoryMessage(**msg)
        if metadata is not None:
            msg.metadata = metadata
        # Keep track of current device name
        self._last_device_name = self.device_combo.currentText()

        current_signal_index = self.signal_combo.currentIndex()
        self._last_signal_name = self.signal_combo.model().data(
            self.signal_combo.model().index(current_signal_index, 0), QtCore.Qt.UserRole
        )
        # Update the scan history message
        self.scan_history_msg = msg
        self.device_combo.clear()
        self.device_combo.addItems(msg.stored_data_info.keys())
        index = self.device_combo.findData(self._last_device_name, role=QtCore.Qt.DisplayRole)
        if index != -1:
            self.device_combo.setCurrentIndex(index)

    @SafeSlot(str)
    def _signal_combo_update(self, device_name: str) -> None:
        """Update the signal combo box based on the selected device."""
        if not self.scan_history_msg:
            logger.info("No scan history message available to update signals.")
            return
        if not device_name:
            return
        signal_data = self.scan_history_msg.stored_data_info.get(device_name, None)
        if signal_data is None:
            logger.info(f"No signal data found for device {device_name}.")
            return
        self.signal_model.signals = signal_data
        if self._last_signal_name is not None:
            # Try to restore the last selected signal
            index = self.signal_combo.findData(self._last_signal_name, role=QtCore.Qt.UserRole)
            if index != -1:
                self.signal_combo.setCurrentIndex(index)

    @SafeSlot()
    def clear_view(self) -> None:
        """Clear the device combo box."""
        self.scan_history_msg = None
        self.signal_model.signals = {}
        self.device_combo.clear()

    @SafeSlot()
    def _on_request_plotting_clicked(self):
        """Handle the request plotting button click."""
        if self.scan_history_msg is None:
            logger.info("No scan history message available for plotting.")
            return
        device_name = self.device_combo.currentText()

        signal_index = self.signal_combo.currentIndex()
        signal_name = self.signal_combo.model().data(
            self.device_combo.model().index(signal_index, 0), QtCore.Qt.UserRole
        )
        logger.info(
            f"Requesting plotting clicked: Scan ID:{self.scan_history_msg.scan_id}, device name: {device_name} with signal name: {signal_name}."
        )
        self.request_history_plot.emit(self.scan_history_msg.scan_id, device_name, signal_name)


if __name__ == "__main__":  # pragma: no cover
    import sys

    app = QtWidgets.QApplication(sys.argv)

    main_window = QtWidgets.QMainWindow()
    central_widget = QtWidgets.QWidget()
    main_window.setCentralWidget(central_widget)
    ly = QtWidgets.QVBoxLayout(central_widget)
    ly.setContentsMargins(0, 0, 0, 0)

    viewer = ScanHistoryDeviceViewer()
    ly.addWidget(viewer)
    main_window.show()
    app.exec_()
    app.exec_()
