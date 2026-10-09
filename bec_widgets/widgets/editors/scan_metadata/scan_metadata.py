from __future__ import annotations

from decimal import Decimal
from types import NoneType
from typing import Any

from bec_lib.logger import bec_logger
from bec_lib.metadata_schema import get_metadata_schema_for_scan
from bec_qthemes import material_icon
from pydantic import Field
from qtpy.QtCore import Qt, Signal  # type: ignore
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.forms_from_types.pydantic_widget_form import (
    EXTRA_FIELDS_KEY,
    PydanticWidgetForm,
)

logger = bec_logger.logger


class _ValidationSummary(QWidget):  # pylint: disable=too-few-public-methods
    """Summary of the form's validation errors, hidden while the form is valid."""

    MAX_LINES = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row_layout = QHBoxLayout(self)
        row_layout.setContentsMargins(0, 4, 0, 0)
        row_layout.setSpacing(6)
        self.icon = QLabel(self)
        self.icon.setFixedSize(16, 16)
        self.text = QLabel(self)
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row_layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        row_layout.addWidget(self.text, 1)
        self.setVisible(False)

    def show_messages(self, messages: list[str]) -> None:
        """Show up to three messages, one per line, and list all of them in the tooltip.

        Args:
            messages: Human-readable error messages; an empty list hides the summary.
        """
        if not messages:
            self.setVisible(False)
            self.text.clear()
            self.setToolTip("")
            return
        color = get_accent_colors().emergency
        self.icon.setPixmap(material_icon("error", size=(16, 16), color=color))
        lines = messages[: self.MAX_LINES]
        if len(messages) > self.MAX_LINES:
            lines.append(f"+{len(messages) - self.MAX_LINES} more")
        self.text.setText("\n".join(lines))
        self.text.setStyleSheet(f"color: {color.name()};")
        self.setToolTip("\n".join(messages))
        self.setVisible(True)


class ScanMetadata(BECWidget, QWidget):
    """Form for the metadata of a scan, generated from the scan's pydantic metadata schema.

    Uses the metadata schema registry supplied in the plugin repo to find the pydantic model
    associated with the scan, falling back to ``BasicScanMetadata``. Free key/value pairs that
    are not part of the schema can be added in the "Additional metadata" section.

    Attributes:
        form_data_updated: Emitted with the validated metadata whenever the form is valid.
        form_data_cleared: Emitted with ``None`` whenever the form is invalid.
        validity_proc: Emitted with the validity of the form after every validation.
    """

    PLUGIN = True
    RPC = False
    ICON_NAME = "list_alt"

    form_data_updated = Signal(dict)
    form_data_cleared = Signal(NoneType)
    validity_proc = Signal(bool)

    def __init__(
        self,
        parent=None,
        client=None,
        scan_name: str | None = None,
        initial_extras: list[list[str]] | None = None,
        **kwargs,
    ):
        """Create the metadata form.

        Args:
            scan_name (str): The scan for which to generate a metadata form
            initial_extras (list[list[str]]): Initial key-value pairs of the additional
                metadata section.
        """
        super().__init__(parent=parent, client=client, **kwargs)
        self._scan_name = scan_name or ""
        self._md_schema = get_metadata_schema_for_scan(self._scan_name)
        self._hide_optional_metadata = False

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)

        self._form = PydanticWidgetForm(
            self._md_schema,
            parent=self,
            client=client,
            allow_extra_fields=True,
            extra_fields_title="Additional metadata",
            extra_fields_hint="Store extra information with the scan as key-value pairs.",
            mark_required=True,
            empty_text_as_missing=True,
        )
        self._form.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        main_layout.addWidget(self._form)
        self._summary = _ValidationSummary(self)
        main_layout.addWidget(self._summary)

        self._form.set_extra_data({str(k): v for k, v in (initial_extras or [])})
        self._update_scan_name_placeholder()
        self._form.changed.connect(self.validate_form)

    @property
    def form(self) -> PydanticWidgetForm:
        """The generated form holding the schema fields and the additional metadata."""
        return self._form

    @SafeSlot(str)
    def update_with_new_scan(self, scan_name: str):
        """Switch to the metadata schema of ``scan_name`` and validate the form.

        Values of fields shared by both schemas and the additional metadata are kept.

        Args:
            scan_name (str): Name of the newly selected scan.
        """
        self.set_schema_from_scan(scan_name)
        self.validate_form()

    def set_schema_from_scan(self, scan_name: str | None):
        """Rebuild the form for the metadata schema of ``scan_name``.

        Args:
            scan_name (str | None): Name of the scan; ``None`` selects the default schema.
        """
        self._scan_name = scan_name or ""
        schema = get_metadata_schema_for_scan(self._scan_name)
        if schema is not self._md_schema:
            self._md_schema = schema
            self._form.set_model(schema)
        self._update_scan_name_placeholder()

    @SafeProperty(bool)
    def hide_optional_metadata(self):  # type: ignore
        """Property to hide the additional metadata section."""
        return self._hide_optional_metadata

    @hide_optional_metadata.setter
    def hide_optional_metadata(self, hide: bool):
        """Setter for the hide_optional_metadata property.

        Args:
            hide(bool): Hide or show the additional metadata section.
        """
        self._hide_optional_metadata = hide
        self._form.extra_fields_section.setVisible(not hide)

    def set_field_values(self, values: dict[str, Any]):
        """Fill schema fields; keys that are not fields of the current schema are ignored.

        Args:
            values (dict): Mapping of field names to values.
        """
        self._form.set_partial_data(values)

    def set_extra_metadata(self, extras: dict[str, Any] | None):
        """Replace the additional metadata key-value pairs.

        Args:
            extras (dict | None): The new key-value pairs.
        """
        self._form.set_extra_data(extras)

    def get_form_data(self) -> dict[str, Any]:
        """Get the entered metadata as a dict, without validating it.

        An empty scan name is replaced by the name of the current scan.
        """
        return self._finalize(self._form.raw_data())

    @SafeSlot()
    def validate_form(self, *_) -> bool:
        """Validate the metadata against the schema and publish the result.

        Emits the validated metadata on ``form_data_updated`` or ``None`` on
        ``form_data_cleared``, and shows the errors below the form.

        Returns:
            bool: Whether the metadata is valid.
        """
        valid = self._form.validate()
        if valid:
            self._summary.show_messages([])
            self.form_data_updated.emit(self._finalize(self._form.get_data()))
        else:
            self._summary.show_messages(self.validation_messages())
            self.form_data_cleared.emit(None)
        self.validity_proc.emit(valid)
        return valid

    def validation_messages(self) -> list[str]:
        """Return one readable message per invalid field, in form order.

        Returns:
            list[str]: Messages such as ``"Sample Name: Field required"``.
        """
        errors = self._form.validation_errors()
        messages = []
        for name, message in errors.items():
            if name == EXTRA_FIELDS_KEY:
                messages.append(f"Additional metadata: {message}")
            elif name in self._form.widgets:
                messages.append(f"{self._form.field_label(name)}: {message}")
            else:
                messages.append(f"{name}: {message}" if name else message)
        return messages

    def _finalize(self, data: dict[str, Any]) -> dict[str, Any]:
        data = {
            key: float(value) if isinstance(value, Decimal) else value
            for key, value in data.items()
        }
        if "scan_name" in data and not data["scan_name"]:
            data["scan_name"] = self._scan_name
        return data

    def _update_scan_name_placeholder(self):
        widget = self._form.widgets.get("scan_name")
        if isinstance(widget, QLineEdit):
            widget.setPlaceholderText(self._scan_name or "Name of the selected scan")

    def cleanup(self):
        """Release the generated field widgets."""
        self._form.cleanup()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    # pylint: disable=redefined-outer-name
    # pylint: disable=protected-access
    # pylint: disable=disallowed-name

    from unittest.mock import patch

    from bec_lib.metadata_schema import BasicScanMetadata

    from bec_widgets.utils.colors import apply_theme

    class ExampleSchema1(BasicScanMetadata):
        abc: int = Field(gt=0, lt=2000, description="Heating temperature abc", title="A B C")
        foo: str = Field(max_length=12, description="Sample database code", default="DEF123")
        xyz: Decimal = Field(decimal_places=4)
        baz: bool

    class ExampleSchema2(BasicScanMetadata):
        checkbox_up_top: bool
        checkbox_again: bool = Field(
            title="Checkbox Again", description="this one defaults to True", default=True
        )
        different_items: int | None = Field(
            None, description="This is just one different item...", gt=-100, lt=0
        )
        length_limited_string: str = Field(max_length=32)
        float_with_2dp: Decimal = Field(decimal_places=2)

    class ExampleSchema3(BasicScanMetadata):
        optional_with_regex: str | None = Field(None, pattern=r"^\d+-\d+$")

    with patch(
        "bec_lib.metadata_schema._get_metadata_schema_registry",
        lambda: {"scan1": ExampleSchema1, "scan2": ExampleSchema2, "scan3": ExampleSchema3},
    ):
        app = QApplication([])
        w = QWidget()
        selection = QComboBox()
        selection.addItems(["grid_scan", "scan1", "scan2", "scan3"])

        layout = QVBoxLayout()
        w.setLayout(layout)

        scan_metadata = ScanMetadata(
            parent=w,
            scan_name="grid_scan",
            initial_extras=[["key1", "value1"], ["key2", "value2"], ["key3", "value3"]],
        )
        selection.currentTextChanged.connect(scan_metadata.update_with_new_scan)

        layout.addWidget(selection)
        layout.addWidget(scan_metadata)

        apply_theme("dark")
        window = w
        window.show()
        app.exec()
