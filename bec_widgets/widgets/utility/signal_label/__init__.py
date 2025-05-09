import sys
from typing import TYPE_CHECKING

from bec_lib.endpoints import MessageEndpoints
from bec_qthemes import material_icon
from PySide6.QtWidgets import QLineEdit
from qtpy.QtWidgets import QApplication, QHBoxLayout, QLabel, QToolButton, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.widgets.control.device_input.base_classes.device_signal_input_base import (
    DeviceSignalInputBase,
    DeviceSignalInputBaseConfig,
)

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib.device import Device


class SignalLabel(DeviceSignalInputBase, QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        config: DeviceSignalInputBaseConfig | dict | None = None,
        show_select_button: bool = True,
        show_default_units: bool = False,
        custom_label: str = "",
        custom_units: str = "",
    ):
        super().__init__(parent=parent, config=config)

        self._custom_label: str = custom_label
        self._custom_units: str = custom_units
        self._show_default_units: bool = show_default_units

        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        self._label = QLabel()
        self._label.setText("default label:")
        self._layout.addWidget(self._label)
        self._update_label()

        self._display = QLineEdit()
        self._display.setEnabled(False)
        self._layout.addWidget(self._display)

        self._select_button = QToolButton()
        self._select_button.setIcon(material_icon(icon_name="select", size=(10, 10)))
        self._show_select_button: bool = show_select_button
        self._layout.addWidget(self._select_button)

    def connect_device(self):
        endpoints_readback = MessageEndpoints.device_readback(self.config.device or "")

    @SafeProperty(bool)
    def show_select_button(self) -> bool:
        """Show the button to select the signal to display"""
        return self._show_select_button

    @show_select_button.setter
    def set_show_select_button(self, value: bool) -> None:
        self._show_select_button = value
        self._select_button.setVisible(value)

    @SafeProperty(bool)
    def show_default_units(self) -> bool:
        """Show default units obtained from the signal alongside it"""
        return self._show_default_units

    @show_default_units.setter
    def set_show_default_units(self, value: bool) -> None:
        self._show_default_units = value
        self._update_label()

    @SafeProperty(str)
    def custom_label(self) -> str:
        """Use a cusom label rather than the signal name"""
        return self._custom_label

    @custom_label.setter
    def custom_label(self, value: str) -> None:
        self._custom_label = value
        self._update_label()

    @SafeProperty(str)
    def custom_units(self) -> str:
        """Use a custom unit string"""
        return self._custom_units

    @custom_units.setter
    def custom_units(self, value: str) -> None:
        self._custom_units = value
        self._update_label()

    @SafeSlot(str)
    def set_display_value(self, value: str):
        self._display.setText(f"{value}{self._units_string}")

    @property
    def _units_string(self):
        if self.custom_units or self._show_default_units:
            return f" {self.custom_units or self._default_units}"
        return ""

    @property
    def _default_units(self) -> str:
        return ""

    @property
    def _default_label(self) -> str:
        return ""

    def _update_label(self):
        self._label.setText(self._custom_label if self._custom_label else f"{self._default_label}:")


if __name__ == "__main__":  # pragma: no cover

    app = QApplication(sys.argv)
    widget = SignalLabel(
        config={"device": "samx", "signal": "samx"}, custom_label="label: ", custom_units=" m/s/s"
    )
    widget.show()
    sys.exit(app.exec_())
