"""Component field editors with explicit literal and scoped-variable inputs."""

from __future__ import annotations

import json

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.widgets.control.scan_control.scan_info_adapter import ScanInfoAdapter

from .presentation import LABELS, Section
from .scan_editor import ScanDefinitionEditor

# Qt signal descriptors are not understood by pylint.
# pylint: disable=no-member


class ValueInput(QWidget):
    """Edit a JSON value or an explicit loop-variable reference.

    Args:
        value (object): Initial JSON value.
        variables (list[str]): Visible loop variable names.
        parent (QWidget | None): Owning widget.
    """

    changed = Signal()

    def __init__(self, value: object, variables: list[str], parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.mode = QComboBox(self)
        self.mode.addItem("Value", None)
        for name in variables:
            self.mode.addItem(f"Variable: {name}", name)
        self.allow_encoding = True
        self.encoding = QComboBox(self)
        for label, kind in (
            ("Text", "text"),
            ("Number", "number"),
            ("Boolean", "boolean"),
            ("JSON", "json"),
        ):
            self.encoding.addItem(label, kind)
        kind = (
            "text"
            if isinstance(value, str)
            else (
                "boolean"
                if isinstance(value, bool)
                else "number" if isinstance(value, (int, float)) else "json"
            )
        )
        self.encoding.setCurrentIndex(self.encoding.findData(kind))
        self.value_edit = QLineEdit(
            value if kind == "text" else json.dumps(value, ensure_ascii=False, allow_nan=False),
            self,
        )
        self.value_edit.setPlaceholderText('e.g. 1.0, "Circ+", [1, 2], {"type": "status_field", …}')
        layout.addWidget(self.mode)
        layout.addWidget(self.value_edit, 1)
        layout.addWidget(self.encoding)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.mode.currentIndexChanged.connect(lambda *_: self.changed.emit())
        self.encoding.currentIndexChanged.connect(lambda *_: self.changed.emit())
        self.value_edit.editingFinished.connect(self.changed.emit)
        if isinstance(value, dict) and set(value) == {"ref"}:
            index = self.mode.findData(value["ref"])
            if index >= 0:
                self.mode.setCurrentIndex(index)

    def _mode_changed(self) -> None:
        self.value_edit.setVisible(self.mode.currentData() is None)
        self.encoding.setVisible(self.mode.currentData() is None and self.allow_encoding)

    def value(self) -> object:
        """Read the explicit reference or parsed literal/expression.

        Returns:
            object: JSON value for the backend.
        """
        name = self.mode.currentData()
        if name is not None:
            return {"ref": name}
        text = self.value_edit.text()
        kind = self.encoding.currentData()
        if kind == "text":
            return text
        value = json.loads(text)
        if kind == "number" and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise ValueError("Enter a number, or change the input type.")
        if kind == "boolean" and not isinstance(value, bool):
            raise ValueError("Enter true or false.")
        return value


class ValuesInput(QWidget):
    """Edit ordered loop values as individual typed inputs.

    Args:
        values (list): Initial loop values.
        variables (list[str]): Visible outer loop bindings.
        parent (QWidget | None): Owning widget.
    """

    changed = Signal()

    def __init__(self, values: list, variables: list[str], parent=None) -> None:
        super().__init__(parent)
        self.variables = variables
        self.rows = []
        self.rows_layout = QVBoxLayout(self)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.add_button = QPushButton("+ Add value", self)
        self.add_button.clicked.connect(lambda: self._add(""))
        self.rows_layout.addWidget(self.add_button)
        for value in values:
            self._add(value)

    def _add(self, value):
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        editor = ValueInput(value, self.variables, row)
        remove = QPushButton("×", row)
        remove.setFixedWidth(28)
        layout.addWidget(editor, 1)
        layout.addWidget(remove)
        self.rows_layout.insertWidget(len(self.rows), row)
        self.rows.append((row, editor))
        remove.clicked.connect(lambda: self._remove(row, editor))
        editor.changed.connect(self.changed.emit)
        self.changed.emit()

    def _remove(self, row, editor):
        self.rows.remove((row, editor))
        self.rows_layout.removeWidget(row)
        row.deleteLater()
        self.changed.emit()

    def value(self) -> list:
        """Read loop values in displayed order.

        Returns:
            list: JSON loop values.
        """
        return [editor.value() for _, editor in self.rows]


class ComponentInspector(QWidget):
    """Show the backend's component documentation and editable fields.

    Args:
        parent (QWidget | None): Owning widget.
        client (BECClient | None): Shared BEC client for the embedded ScanControl.
    """

    changed = Signal()

    def __init__(self, parent=None, client=None) -> None:
        super().__init__(parent)
        self.client = client
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        self.breadcrumb = QLabel(self)
        self.help = QLabel(self)
        self.help.setWordWrap(True)
        self.scope = QLabel(self)
        self.scope.setWordWrap(True)
        self.breadcrumb.setObjectName("breadcrumb")
        self.help.setObjectName("stepHeading")
        self.scope.setObjectName("scopeChip")
        layout.addWidget(self.breadcrumb)
        layout.addWidget(self.help)
        layout.addWidget(self.scope)
        for label in (self.help, self.scope, self.breadcrumb):
            label.setTextFormat(Qt.PlainText)
        self.form = QFormLayout()
        self.form.setVerticalSpacing(14)
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout.addLayout(self.form)
        self.metadata = QPlainTextEdit(self)
        self.metadata.setReadOnly(True)
        self.metadata.setMaximumHeight(200)
        self.metadata.setPlaceholderText("Advertised scan signature and documentation")
        self.documentation = Section("Component documentation", self.metadata, self)
        layout.addWidget(self.documentation)
        layout.addStretch()
        self.fields = {}
        self.node = {}
        self.scan_arguments = None
        self.raw_arguments = None

    # The inspector receives independently owned editor metadata.
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def display(
        self,
        node: dict,
        schema: dict,
        variables: list[str],
        scans: dict,
        devices: list[str],
        breadcrumb: str,
    ) -> None:
        """Populate fields using component schema and subscribed scan metadata.

        Args:
            node (dict): Selected component.
            schema (dict): Component JSON schema.
            variables (list[str]): Visible loop bindings.
            scans (dict): Advertised scan metadata.
            devices (list[str]): Available device names; dotted signal names remain editable.
            breadcrumb (str): Selected component's nesting path.
        """
        self.cleanup()
        self.node = node
        self.scan_arguments = None
        self.raw_arguments = None
        self.fields = {}
        while self.form.rowCount():
            self.form.removeRow(0)
        self.breadcrumb.setText(breadcrumb)
        self.help.setText(LABELS[node["type"]])
        self.help.setToolTip(schema.get("description", "").split("Args:")[0].strip())
        self.scope.setText(
            "Available in this step   " + "   ".join(f"${name}" for name in variables)
        )
        self.scope.setVisible(bool(variables))
        advanced = QWidget(self)
        advanced_form = QFormLayout(advanced)
        advanced_form.setContentsMargins(0, 8, 0, 8)
        for name, field in schema["properties"].items():
            if name in {"type", "children", "body"}:
                continue
            value = node.get(name, field.get("default"))
            editor = self._field_editor(name, value, variables, scans, devices)
            editor.setToolTip(field.get("description", ""))
            self.fields[name] = editor
            label = {
                "id": "Step name",
                "name": "Scan type",
                "device": "Target",
                "value": "Set to",
                "variable": "Variable name",
                "count": "Repeat group",
                "wait": "",
                "bind_status": "Status name",
            }.get(name, name.replace("_", " ").capitalize())
            target_form = (
                advanced_form
                if name in {"bind_status", "arguments", "positional"}
                or (name == "name" and node["type"] == "scan_call")
                else self.form
            )
            target_form.addRow(label, editor)
        self.documentation.setVisible(node["type"] == "scan_call")
        if node["type"] == "scan_call":
            self._scan_editor(node, variables, scans, advanced_form)
        self.form.addRow(Section("Advanced settings", advanced, self))
        for editor in self.fields.values():
            self._connect_editor(editor)
        if self.scan_arguments is not None:
            self.scan_arguments.changed.connect(self.changed.emit)

    def _field_editor(self, name, value, variables, scans, devices):
        if name == "count":
            editor = QSpinBox(self)
            editor.setRange(1, 2_147_483_647)
            editor.setValue(value)
            editor.setSuffix(" times")
        elif name == "wait":
            editor = QCheckBox("Wait for completion", self)
            editor.setChecked(value)
        elif name in {"name", "device"}:
            editor = QComboBox(self)
            editor.setEditable(True)
            editor.addItems(sorted(scans) if name == "name" else devices)
            editor.setCurrentText(value or "")
        elif name in {"id", "variable", "bind_status"}:
            editor = QLineEdit(value or "", self)
        elif name == "values":
            editor = ValuesInput(value, variables, self)
        else:
            editor = ValueInput(value, variables, self)
        return editor

    def _scan_editor(self, node, variables, scans, advanced_form):
        self.fields["name"].currentTextChanged.connect(
            lambda name: self._scan_metadata(scans.get(name, {}))
        )
        self._scan_metadata(scans.get(node["name"], {}))
        if (
            isinstance(node.get("arguments"), dict)
            and not any(key in node["arguments"] for key in ("ref", "param", "type"))
            and bool(scans)
            and (not node["name"] or node["name"] in scans)
        ):
            self.scan_arguments = ScanDefinitionEditor(node, variables, scans, self.client, self)
            self.form.addRow(self.scan_arguments)
            for name in ("arguments", "positional"):
                self.fields[name].setToolTip(
                    "Raw JSON inputs, including metadata and structured expressions."
                )
            self.raw_arguments = QCheckBox("Edit arguments as raw JSON", self)
            advanced_form.addRow(self.raw_arguments)
            self.raw_arguments.toggled.connect(self._argument_mode)
            self._argument_mode(False)
            self.fields["name"].currentTextChanged.connect(
                lambda _: self.raw_arguments.setChecked(True)
            )

    def _connect_editor(self, editor):
        if isinstance(editor, (ValueInput, ValuesInput)):
            editor.changed.connect(self.changed.emit)
        elif isinstance(editor, QLineEdit):
            editor.editingFinished.connect(self.changed.emit)
        elif isinstance(editor, QComboBox):
            if editor.isEditable():
                editor.lineEdit().editingFinished.connect(self.changed.emit)
            editor.activated.connect(lambda *_: self.changed.emit())
        elif isinstance(editor, QSpinBox):
            editor.editingFinished.connect(self.changed.emit)
        elif isinstance(editor, QCheckBox):
            editor.toggled.connect(lambda *_: self.changed.emit())

    def cleanup(self) -> None:
        """Release the embedded scan editor before changing the selected component."""
        if self.scan_arguments is not None:
            self.scan_arguments.cleanup()

    def _scan_metadata(self, info: dict) -> None:
        lines = [info.get("doc", ""), "", "Advertised inputs:"]
        for entry in info.get("signature", []):
            annotation, _ = ScanInfoAdapter.parse_annotation(entry.get("annotation"))
            default = entry.get("default", "_empty")
            requirement = "required" if default == "_empty" else f"default: {default!r}"
            lines.append(f"{entry['name']} ({annotation}; {entry['kind']}; {requirement})")
        self.metadata.setPlainText("\n".join(lines))

    def _argument_mode(self, raw: bool) -> None:
        self.scan_arguments.setEnabled(not raw)
        for name in ("name", "arguments", "positional"):
            self.fields[name].setEnabled(raw)

    def values(self) -> dict:
        """Read component fields without modifying nested children.

        Returns:
            dict: Edited component preserving its body or children.
        """
        node = self.node.copy()
        for name, editor in self.fields.items():
            if (
                name in {"name", "arguments", "positional"}
                and self.scan_arguments is not None
                and not self.raw_arguments.isChecked()
            ):
                continue
            if isinstance(editor, (ValueInput, ValuesInput)):
                value = editor.value()
            elif isinstance(editor, QComboBox):
                value = editor.currentText()
            elif isinstance(editor, QSpinBox):
                value = editor.value()
            elif isinstance(editor, QCheckBox):
                value = editor.isChecked()
            else:
                value = editor.text()
            node[name] = None if name == "bind_status" and not value else value
        if self.scan_arguments is not None and not self.raw_arguments.isChecked():
            node["name"], node["positional"], node["arguments"] = self.scan_arguments.values()
        return node
