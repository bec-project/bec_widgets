from qtpy.QtCore import QSize
from qtpy.QtWidgets import QComboBox, QSizePolicy

from bec_widgets.utils.filter_io import ComboBoxFilterHandler, FilterIO
from bec_widgets.widgets.base_classes.device_signal_input_base import DeviceSignalInputBase


class SignalComboBox(DeviceSignalInputBase, QComboBox):
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

    ICON_NAME = "list_alt"

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
        QComboBox.__init__(self, parent=parent)
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

    def update_signals_from_filters(self):
        """Update the filters for the combobox"""
        super().update_signals_from_filters()
        # pylint: disable=protected-access
        if FilterIO._find_handler(self) is ComboBoxFilterHandler:
            if len(self._config_signals) > 0:
                self.insertItem(
                    len(self._hinted_signals) + len(self._normal_signals), "Config Signals"
                )
                self.model().item(len(self._hinted_signals) + len(self._normal_signals)).setEnabled(
                    False
                )
            if len(self._normal_signals) > 0:
                self.insertItem(len(self._hinted_signals), "Normal Signals")
                self.model().item(len(self._hinted_signals)).setEnabled(False)
            if len(self._hinted_signals) > 0:
                self.insertItem(0, "Hinted Signals")
                self.model().item(0).setEnabled(False)


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
    box = SignalComboBox(device="samx")
    layout.addWidget(box)
    widget.show()
    app.exec_()
