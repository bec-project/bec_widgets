from qtpy.QtCore import QSize, Slot
from qtpy.QtGui import QPainter, QPaintEvent, QPen
from qtpy.QtWidgets import QCompleter, QLineEdit, QSizePolicy

from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.widgets.base_classes.device_signal_input_base import DeviceSignalInputBase


class SignalLineEdit(DeviceSignalInputBase, QLineEdit):
    """
    Line edit widget for device input with autocomplete for device names.

    Args:
        parent: Parent widget.
        client: BEC client object.
        config: Device input configuration.
        gui_id: GUI ID.
        device_filter: Device filter, name of the device class from BECDeviceFilter and BECReadoutPriority. Check DeviceInputBase for more details.
        default: Default device name.
        arg_name: Argument name, can be used for the other widgets which has to call some other function in bec using correct argument names.
    """

    ICON_NAME = "vital_signs"

    def __init__(
        self,
        parent=None,
        client=None,
        config: DeviceSignalInputBase = None,
        gui_id: str | None = None,
        device: str | None = None,
        signal_filter: str | list[str] | None = None,
        default: str | None = None,
        arg_name: str | None = None,
    ):
        super().__init__(client=client, config=config, gui_id=gui_id)
        QLineEdit.__init__(self, parent=parent)
        self._is_valid_input = False
        self._accent_colors = get_accent_colors()
        self.completer = QCompleter(self)
        self.setCompleter(self.completer)
        if arg_name is not None:
            self.config.arg_name = arg_name
            self.arg_name = arg_name
        if default is not None:
            self.set_device(default)

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMinimumSize(QSize(100, 0))
        signal_filter = signal_filter if not None else self.config.signal_filter
        if signal_filter is not None:
            self.set_filter(signal_filter)
        device = device if not None else self.config.device
        if device is not None:
            self.set_device(device)
        default = default if not None else self.config.default
        if default is not None:
            self.set_signal(default)
        self.textChanged.connect(self.check_validity)

    def get_current_device(self) -> object:
        """
        Get the current device object based on the current value.

        Returns:
            object: Device object, can be device of type Device, Positioner, Signal or ComputedSignal.
        """
        dev_name = self.text()
        return self.get_device_object(dev_name)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Extend the paint event to set the border color based on the validity of the input.

        Args:
            event (PySide6.QtGui.QPaintEvent) : Paint event.
        """
        super().paintEvent(event)
        painter = QPainter(self)
        pen = QPen()
        pen.setWidth(2)

        if self._is_valid_input is False and self.isEnabled() is True:
            pen.setColor(self._accent_colors.emergency)
            painter.setPen(pen)
            painter.drawRect(self.rect().adjusted(1, 1, -1, -1))

    @Slot(str)
    def check_validity(self, input_text: str) -> None:
        """
        Check if the current value is a valid device name.
        """
        # i
        if self.validate_signal(input_text) is True:
            self._is_valid_input = True
        else:
            self._is_valid_input = False
        self.update()


if __name__ == "__main__":  # pragma: no cover
    # pylint: disable=import-outside-toplevel
    from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

    from bec_widgets.utils.colors import set_theme

    app = QApplication([])
    set_theme("dark")
    widget = QWidget()
    widget.setFixedSize(200, 200)
    layout = QVBoxLayout()
    widget.setLayout(layout)
    layout.addWidget(SignalLineEdit(device="samx"))
    widget.show()
    app.exec_()
