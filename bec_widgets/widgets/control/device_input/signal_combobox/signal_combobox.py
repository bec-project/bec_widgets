from bec_lib.device import Positioner
from qtpy.QtCore import QSize, Signal
from qtpy.QtWidgets import QComboBox, QSizePolicy

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.filter_io import ComboBoxFilterHandler, FilterIO
from bec_widgets.utils.ophyd_kind_util import Kind
from bec_widgets.widgets.control.device_input.base_classes.device_signal_input_base import (
    DeviceSignalInputBase,
    DeviceSignalInputBaseConfig,
)


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

    USER_ACCESS = ["set_signal", "set_device", "signals"]

    ICON_NAME = "list_alt"
    PLUGIN = True
    RPC = True

    device_signal_changed = Signal(str)

    def __init__(
        self,
        parent=None,
        client=None,
        config: DeviceSignalInputBaseConfig | None = None,
        gui_id: str | None = None,
        device: str | None = None,
        signal_filter: str | list[str] | None = None,
        default: str | None = None,
        arg_name: str | None = None,
        **kwargs,
    ):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)
        if arg_name is not None:
            self.config.arg_name = arg_name
            self.arg_name = arg_name
        if default is not None:
            self.set_device(default)

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMinimumSize(QSize(100, 0))
        # We do not consider the config that is passed here, this produced problems
        # with QtDesigner, since config and input arguments may differ and resolve properly
        # Implementing this logic and config recoverage is postponed.
        self.currentTextChanged.connect(self.on_text_changed)
        if signal_filter is not None:
            self.set_filter(signal_filter)
        else:
            self.set_filter([Kind.hinted, Kind.normal, Kind.config])
        if device is not None:
            self.set_device(device)
        if default is not None:
            self.set_signal(default)

    @SafeSlot()
    @SafeSlot(dict, dict)
    def update_signals_from_filters(
        self, content: dict | None = None, metadata: dict | None = None
    ):
        """Update the filters for the combobox"""
        super().update_signals_from_filters(content, metadata)
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

    @SafeSlot()
    def reset_selection(self):
        """Reset the selection of the combobox."""
        self.clear()
        self.setItemText(0, "Select a device")
        self.update_signals_from_filters()
        self.device_signal_changed.emit("")

    @SafeSlot(str)
    def on_text_changed(self, text: str):
        """Slot for text changed. If a device is selected and the signal is changed and valid it emits a signal.
        For a positioner, the readback value has to be renamed to the device name.

        Args:
            text (str): Text in the combobox.
        """
        if self.validate_device(self.device) is False:
            return
        if self.validate_signal(text) is False:
            return
        self.device_signal_changed.emit(text)


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
