"""Embed ScanControl, adding scoped references and preserving JSON calling semantics."""

from __future__ import annotations

import json
from copy import deepcopy

from qtpy.QtCore import QTimer, Signal
from qtpy.QtGui import QValidator
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDoubleSpinBox,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.control.scan_control import ScanControl
from bec_widgets.widgets.control.scan_control.scan_group_box import ScanLiteralsComboBox

# Qt signal descriptors are not understood by pylint.
# pylint: disable=no-member

_MISSING = object()


class ScanInputValidator(QValidator):
    """Permit visible variables or literals accepted by the native scan input.

    Args:
        widget (QWidget): Native input supplying type, bounds and literal validation.
        variables (list[str]): Loop variables visible at this component.
        parent (QWidget): Owning input.
    """

    def __init__(self, widget: QWidget, variables: list[str], parent: QWidget) -> None:
        super().__init__(parent)
        self.widget = widget
        self.variables = {f"${name}" for name in variables}

    def validate(self, text: str, position: int) -> tuple:
        """Validate a scoped variable or defer to the scan's native literal rules.

        Args:
            text (str): Current input text.
            position (int): Cursor position.

        Returns:
            tuple: Qt validation state, unchanged text and cursor position.
        """
        if text in self.variables:
            return QValidator.State.Acceptable, text, position
        if text.startswith("$"):
            state = (
                QValidator.State.Intermediate
                if any(name.startswith(text) for name in self.variables)
                else QValidator.State.Invalid
            )
            return state, text, position
        if isinstance(self.widget, (QSpinBox, QDoubleSpinBox)):
            return self.widget.validate(text, position)
        if isinstance(self.widget, QCheckBox):
            valid = text.lower() in {"true", "false"}
        elif isinstance(self.widget, DeviceComboBox):
            valid = self.widget.validate_device(text)
        elif isinstance(self.widget, ScanLiteralsComboBox):
            valid = self.widget.findText(text) >= 0
        else:
            validator = self.widget.validator() if isinstance(self.widget, QLineEdit) else None
            if validator is not None:
                return validator.validate(text, position)
            valid = True
        return (
            (QValidator.State.Acceptable if valid else QValidator.State.Intermediate),
            text,
            position,
        )


class BoundScanInput(QLineEdit):
    """Edit a native scan value or a visible ``$variable`` in one input.

    The validator keeps the native input's literal rules and additionally permits scoped
    loop variables. Variables are serialized as JSON references, never as Python expressions.

    Args:
        widget (QWidget): Native scan input supplying literal conversion and validation.
        value (object): Loaded JSON value or a missing-value sentinel.
        variables (list[str]): Visible loop bindings.
        parent (QWidget | None): Owning scan-input tile.
    """

    changed = Signal()

    def __init__(self, widget: QWidget, value: object, variables: list[str], parent=None) -> None:
        super().__init__(parent)
        self.widget = widget
        self.variables = variables
        self.setValidator(ScanInputValidator(widget, variables, self))
        choices = [f"${name}" for name in variables]
        if isinstance(widget, QComboBox):
            choices += [widget.itemText(index) for index in range(widget.count())]
        if choices:
            self.setCompleter(QCompleter(choices, self))
        self.setToolTip(
            widget.toolTip()
            + (
                "\nAvailable variables: " + ", ".join(f"${name}" for name in variables)
                if variables
                else ""
            )
        )
        if isinstance(value, dict):
            self.setText(f"${value['ref']}" if set(value) == {"ref"} else json.dumps(value))
        else:
            if value is not _MISSING:
                if isinstance(widget, ScanLiteralsComboBox):
                    widget.setCurrentText(str(value) if value is not None else "")
                else:
                    WidgetIO.set_value(widget, value)
            self.load_native_value()
        widget.hide()
        self.textEdited.connect(lambda *_: self.changed.emit())
        self.editingFinished.connect(self.changed.emit)

    def load_native_value(self) -> None:
        """Display a literal restored by ScanControl."""
        if isinstance(self.widget, (QSpinBox, QDoubleSpinBox)):
            text = self.widget.text()
        elif isinstance(self.widget, QCheckBox):
            text = "true" if self.widget.isChecked() else "false"
        elif isinstance(self.widget, QComboBox):
            text = self.widget.currentText()
        else:
            text = self.widget.text()
        self.setText(text)

    def value(self) -> object:
        """Read a checked literal or scoped JSON reference.

        Returns:
            object: JSON-compatible scan argument.

        Raises:
            ValueError: Input is neither a valid literal nor an available variable.
        """
        text = self.text()
        if text.startswith("$"):
            name = text[1:]
            if name not in self.variables:
                raise ValueError(f"Variable {text} is not available in this step")
            return {"ref": name}
        if not self.hasAcceptableInput():
            raise ValueError(f"Invalid {self.widget.arg_name}: {text}")
        if isinstance(self.widget, (QSpinBox, QDoubleSpinBox)):
            return self.widget.valueFromText(text)
        if isinstance(self.widget, QCheckBox):
            return text.lower() == "true"
        return text


class ScanDefinitionEditor(QWidget):
    """Use ScanControl for scan selection, argument groups and device bundles.

    The scheduler permits scoped variables in the inputs and translates edits back to
    their original positional/keyword locations. Opening a node does not supply missing
    arguments or replace its JSON values with widget defaults.

    Args:
        node (dict): Scan-call component.
        variables (list[str]): Visible loop variables.
        scan_info (dict): Already subscribed scan metadata.
        client (BECClient): Existing BEC client.
        parent (QWidget | None): Owning inspector.
    """

    changed = Signal()

    def __init__(
        self, node: dict, variables: list[str], scan_info: dict, client, parent=None
    ) -> None:
        super().__init__(parent)
        self.original = deepcopy(node)
        self.variables = variables
        self.inputs = {}
        self.dirty = set()
        self._name_changed = False
        self._closed = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.control = ScanControl(
            parent=self, client=client, scan_info=scan_info, default_scan=node.get("name") or None
        )
        self.control.hide_scan_control_buttons = True
        self.control.scan_control_group.setEnabled(False)
        if self.control.arg_box is not None and node.get("positional"):
            defaults, _ = self.control.get_scan_parameters(bec_object=False)
            values = [
                defaults[index % len(defaults)] if isinstance(value, dict) else value
                for index, value in enumerate(node["positional"])
            ]
            self.control.arg_box.set_parameters(values)
        # Metadata can contain expressions; it remains in the scheduler's advanced JSON editor.
        self.control.hide_metadata = True
        layout.addWidget(self.control)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self._refresh_inputs)
        self._refresh_inputs()
        self.control.scan_selected.connect(self._selected)
        self.control.comboBox_scan_selection.activated.connect(self._confirmed)
        # ScanControl applies this result first; the wrapper then refreshes replaced inputs.
        # pylint: disable=protected-access
        self.control._last_scan_parameters_received.connect(self._restored)

    def _restored(self, generation: int, name: str, parameters: tuple[list, dict]) -> None:
        # Match ScanControl's stale-response guard before reading the restored inputs.
        # pylint: disable=protected-access
        if self._closed or generation != self.control._last_scan_fetch_generation:
            return
        if name != self.control.current_scan:
            return
        positional, keywords = parameters
        self.original = {
            "name": name,
            "positional": deepcopy(positional),
            "arguments": deepcopy(keywords),
        }
        self._name_changed = False
        self.dirty.clear()
        for binding in self.inputs.values():
            binding.load_native_value()
        self.refresh_timer.start(0)
        self.changed.emit()

    def _positional_names(self) -> list[str]:
        signature = self.control.available_scans.get(self.control.current_scan, {}).get(
            "signature", []
        )
        return [
            entry["name"]
            for entry in signature
            if entry["kind"] in {"POSITIONAL_ONLY", "POSITIONAL_OR_KEYWORD"}
        ]

    def _selected(self, _name):
        self._name_changed = True
        self.original = {"name": self.control.current_scan, "positional": [], "arguments": {}}
        self.inputs.clear()
        self.dirty.clear()
        # Native ScanControl restores its inputs after emitting scan_selected.
        self.refresh_timer.start(0)
        self.changed.emit()

    def _confirmed(self, _index):
        if not self.original.get("name"):
            self._name_changed = True
            self.changed.emit()

    def _input_changed(self, path):
        if not self.original.get("name"):
            self._name_changed = True
        self.dirty.add(path)
        self.changed.emit()

    def _refresh_inputs(self):
        if self._closed:
            return
        current = {}
        if self.control.arg_box is not None:
            for index, widget in enumerate(self.control.arg_box.widgets):
                current[("positional", index)] = widget
            box = self.control.arg_box
            if not box.property("sequence_bindings_connected"):
                box.setProperty("sequence_bindings_connected", True)
                for button in (box.button_add_bundle, box.button_remove_bundle):
                    button.clicked.connect(self._bundles_changed)
        for box in self.control.kwarg_boxes:
            for widget in box.widgets:
                name = widget.arg_name
                positional_names = self._positional_names()
                path = (
                    ("positional", positional_names.index(name))
                    if (
                        self.control.arg_box is None
                        and name in positional_names
                        and positional_names.index(name) < len(self.original.get("positional", []))
                    )
                    else ("arguments", name)
                )
                current[path] = widget
        existing = {id(binding.widget): binding for binding in self.inputs.values()}
        self.inputs = {}
        for path, widget in current.items():
            if id(widget) in existing:
                binding = existing[id(widget)]
                binding.changed.disconnect()
                binding.changed.connect(lambda path=path: self._input_changed(path))
                self.inputs[path] = binding
                continue
            values = self.original.get(path[0], {} if path[0] == "arguments" else [])
            value = (
                values.get(path[1], _MISSING)
                if isinstance(values, dict)
                else (values[path[1]] if path[1] < len(values) else _MISSING)
            )
            tile = widget.parentWidget()
            tile.layout().removeWidget(widget)
            binding = BoundScanInput(widget, value, self.variables, tile)
            tile.layout().addWidget(binding)
            binding.changed.connect(lambda path=path: self._input_changed(path))
            self.inputs[path] = binding
        self.changed.emit()

    def _bundles_changed(self, *_):
        self._name_changed = True
        self.refresh_timer.start(0)

    def values(self) -> tuple[str, list, dict]:
        """Read native edits while retaining untouched arguments and positional calls.

        Returns:
            tuple[str, list, dict]: Scan name, positional arguments and keyword arguments.
        """
        if self.refresh_timer.isActive():
            self.refresh_timer.stop()
            self._refresh_inputs()
        name = self.control.current_scan if self._name_changed else self.original.get("name", "")
        positional = deepcopy(self.original.get("positional", []))
        keywords = deepcopy(self.original.get("arguments", {}))
        if self._name_changed:
            positional, defaults = self.control.get_scan_parameters(bec_object=False)
            keywords.update({key: value for key, value in defaults.items() if key != "metadata"})
        for path, binding in self.inputs.items():
            if path not in self.dirty and not self._name_changed:
                continue
            value = binding.value()
            if path[0] == "arguments":
                keywords[path[1]] = value
            else:
                if path[1] >= len(positional):
                    native, _ = self.control.get_scan_parameters(bec_object=False)
                    positional.extend(native[len(positional) :])
                positional[path[1]] = value
        return name, positional, keywords

    def cleanup(self) -> None:
        """Release embedded ScanControl resources and pending input refreshes."""
        if self._closed:
            return
        self._closed = True
        self.refresh_timer.stop()
        self.control.cleanup()
