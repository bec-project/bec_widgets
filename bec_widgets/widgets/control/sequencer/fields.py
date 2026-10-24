"""Input fields shared by the sequencer editors."""

from __future__ import annotations

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QComboBox, QLineEdit, QWidget

from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.control.sequencer import model
from bec_widgets.widgets.control.sequencer.style import theme


def parse_number(text: str):
    """Parse a typed number; an empty text is None and anything else stays text.

    Args:
        text (str): Typed text.

    Returns:
        int | float | str | None: The value.
    """
    text = text.strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return text
    return int(number) if number.is_integer() and "." not in text and "e" not in text else number


def parse_values(text: str) -> list:
    """Parse ``1, -1, 2.5`` (or one value per line) into numbers, keeping words as text."""
    values = []
    for part in text.replace("\n", ",").replace(";", ",").split(","):
        value = parse_number(part)
        if value is not None:
            values.append(value)
    return values


def values_text(values: list) -> str:
    """Inverse of ``parse_values``."""
    return ", ".join(model.format_value(v) for v in values)


class NumberEdit(QLineEdit):
    """A number field that can also be empty ("not entered yet").

    ``edited`` is emitted whenever the user changes the text.
    """

    edited = Signal()

    def __init__(self, parent: QWidget | None = None, placeholder: str = "number"):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.textEdited.connect(self._on_edited)
        self._style(True)

    def value(self):
        """The number, None when empty, or the text when it is not a number."""
        return parse_number(self.text())

    def set_value(self, value) -> None:
        """Show a value (None clears the field)."""
        self.setText("" if value is None or model.is_ref(value) else model.format_value(value))
        self._style(True)

    def _on_edited(self, text: str) -> None:
        value = parse_number(text)
        self._style(value is None or not isinstance(value, str))
        self.edited.emit()

    def _style(self, valid: bool) -> None:
        red = theme("ACCENT_EMERGENCY", "#e0534b").name()
        self.setStyleSheet("" if valid else f"QLineEdit {{ border: 1px solid {red}; }}")


class ValuesEdit(QLineEdit):
    """A comma separated list of values, e.g. ``1, -1, 2.5``."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setPlaceholderText("e.g. 1, -1, 2.5")

    def values(self) -> list:
        """The parsed values."""
        return parse_values(self.text())

    def set_values(self, values: list) -> None:
        """Show values."""
        self.setText(values_text(values or []))


class DevicePicker(DeviceComboBox):
    """Device combo box that only turns red for a name that is not a device.

    An empty picker is not an error here: the editor says which step still needs a motor.
    """

    def _update_validity_style(self, is_valid: bool) -> None:
        super()._update_validity_style(is_valid or not self.currentText().strip())


def device_picker(
    parent: QWidget | None, client, placeholder: str = "Choose a motor", settable: bool = False
) -> DevicePicker:
    """A device combo box listing the motors (and, optionally, settable signals).

    Args:
        parent (QWidget | None): Parent widget.
        client: BEC client.
        placeholder (str): Text shown while nothing is chosen.
        settable (bool): Also list signals that can be written, e.g. a temperature setpoint.

    Returns:
        DevicePicker: The picker, empty until the user chooses.
    """
    picker = DevicePicker(
        parent,
        client=client,
        device_filter=["Positioner"],
        autocomplete=True,
        include_signals_with_write_access=settable,
    )
    picker.set_first_element_as_empty = True
    picker.setCurrentText("")
    picker.lineEdit().setPlaceholderText(placeholder)
    picker.setMinimumContentsLength(10)
    return picker


class ScanPicker(QComboBox):
    """Choose one of the beamline's scans by its readable name.

    Args:
        entries (dict): Advertised scans by name.
        parent (QWidget | None): Parent widget.
    """

    scan_chosen = Signal(str)

    def __init__(self, entries: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.setPlaceholderText("Choose a scan…")
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        for name, info in entries.items():
            self.addItem(model.scan_title(name), name)
            doc = (info.get("doc") or "").strip().splitlines()
            if doc:
                self.setItemData(self.count() - 1, doc[0], Qt.ItemDataRole.ToolTipRole)
        self.setCurrentIndex(-1)
        self.activated.connect(lambda _index: self.scan_chosen.emit(self.scan()))

    def scan(self) -> str:
        """Name of the chosen scan, or an empty string."""
        return self.currentData() or ""

    def set_scan(self, name: str) -> None:
        """Show a scan; an unknown name is listed so it is not lost."""
        if name and self.findData(name) < 0:
            self.addItem(model.scan_title(name), name)
        self.setCurrentIndex(self.findData(name) if name else -1)
