from bec_lib.endpoints import MessageEndpoints
from ophyd import Kind
from qtpy.QtCore import Slot
from qtpy.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QWidget

from bec_widgets.utils import BECConnector


class OphydSignalBox(QWidget):
    """A widget to display a signal value of an Ophyd signal."""

    def __init__(
        self,
        parent=None,
        device_name: str = None,
        signal_name: str = None,
        device_base_class: str = None,
    ):
        super().__init__(parent)
        self.layout = QHBoxLayout()
        self.device_name = device_name
        self.device_base_class = device_base_class
        self.signal_name = signal_name

        self.signal_label = None
        self.signal_value = None
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI of the signal widget."""
        self._create_signal_widget()

    def _create_signal_widget(self):
        """Create the signal widget with label and value."""
        self.signal_label = QLabel()
        self.signal_label.setText(f"{self.signal_name}")
        self.signal_value = QLineEdit()
        self.signal_value.setDisabled(True)

        self.layout.addWidget(self.signal_label)
        self.layout.addWidget(self.signal_value)
        self.setLayout(self.layout)

    @Slot(dict, dict)
    def update_readback(self, content: dict, metadata: dict):
        """Update the readback value of the signal.

        Args:
            content (dict): The content of the signal.
            metadata (dict): The metadata of the signal.
        """
        if self.device_base_class == "positioner" and self.signal_name == "readback":
            signal_key = self.device_name
        else:
            signal_key = f"{self.device_name}_{self.signal_name}"
        value = content["signals"][signal_key]["value"]
        value = f"{value:.4f}" if isinstance(value, float) else f"{value}"
        self.signal_value.setText(f"{value}")


class BECDevice(BECConnector, QWidget):

    def __init__(
        self,
        parent=None,
        client=None,
        gui_id: str | None = None,
        device_name: str = None,
        device_signals: str | list[str] = None,
    ):
        super().__init__(client=client, gui_id=gui_id)
        QWidget.__init__(self, parent=parent)

        self.device_name = device_name
        group = QGroupBox(self.device_name, self)
        self.layout = QGridLayout(group)
        self.device_signals = self.get_device_signals(device_signals)
        self.table = {}
        self._init_UI()

    def _init_UI(self):
        """Initialize the UI of the device widget."""

        for ii, signal_name in enumerate(self.device_signals):
            # pylint: disable=protected-access
            dev_info = self.client.device_manager.devices[self.device_name]._info
            kind = [
                info["kind_int"]
                for info in dev_info["signals"]
                if info["component_name"] == signal_name
            ][0]
            signal_box = OphydSignalBox(
                device_name=self.device_name,
                signal_name=signal_name,
                device_base_class=dev_info["device_base_class"],
            )
            self.table[signal_name] = signal_box
            self.layout.addWidget(signal_box, ii, 0)
            if kind == Kind.hinted.value or kind == Kind.normal.value:
                self.bec_dispatcher.connect_slot(
                    signal_box.update_readback, MessageEndpoints.device_readback(self.device_name)
                )
            elif kind == Kind.config.value:
                self.bec_dispatcher.connect_slot(
                    signal_box.update_readback,
                    MessageEndpoints.device_read_configuration(self.device_name),
                )
        # Receive first updates upon start
        self.client.device_manager.devices[self.device_name].read(cached=False)
        self.client.device_manager.devices[self.device_name].read_configuration(cached=False)

    def get_device_signals(self, device_signals: str | list | None) -> list[str]:
        """Get the signals of the device from the BEC.

        Args:
            device_name (str | list | None): The name of the device.
        """
        if device_signals is None:
            device_signals = []
            device_signals.extend(self.signals_name_from_kind(self.device_name, Kind.hinted))
            device_signals.extend(self.signals_name_from_kind(self.device_name, Kind.normal))
            device_signals.extend(self.signals_name_from_kind(self.device_name, Kind.config))
        elif isinstance(device_signals, str):
            device_signals = [device_signals]
        return device_signals

    def signals_name_from_kind(self, device_name: str, kind: Kind) -> list[str]:
        """Get the signals name from the device name and kind.

        Args:
            device_name (str): The name of the device.
            kind (Kind): The kind of the signal.
        """
        rtr = []
        # pylint: disable=protected-access
        dev_info = self.client.device_manager.devices[device_name]._info
        for info in dev_info["signals"]:
            if info["kind_int"] == kind.value:
                rtr.append(info["component_name"])
        return rtr

    @Slot(dict, dict)
    def on_device_readback(self, content: dict, metadata: dict) -> None:
        for signal_name, ophyd_signal in self.table.items():
            if signal_name in content["signals"].keys():
                value = content["signals"][signal_name]["value"]
                value = f"{value:.4f}" if isinstance(value, float) else f"{value}"
                ophyd_signal.update_readback(value)


if __name__ == "__main__":

    import qdarktheme
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    qdarktheme.setup_theme("auto")
    widget = BECDevice(device_name="eiger")
    widget.show()
    app.exec_()
