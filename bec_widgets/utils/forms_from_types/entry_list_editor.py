"""Row-based editor for lists of values or key/value pairs, used by generated forms."""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import Qt, Signal  # type: ignore
from qtpy.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class _EntryRow(QWidget):
    """One editable row: an optional key field, a value field and a remove button."""

    def __init__(
        self, parent: QWidget, *, key_value: bool, key_placeholder: str, value_placeholder: str
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.key_edit: QLineEdit | None = None
        if key_value:
            self.key_edit = QLineEdit(self)
            self.key_edit.setPlaceholderText(key_placeholder)
            layout.addWidget(self.key_edit, 2)
        self.value_edit = QLineEdit(self)
        self.value_edit.setPlaceholderText(value_placeholder)
        layout.addWidget(self.value_edit, 3)
        self.remove_button = QToolButton(self)
        self.remove_button.setAutoRaise(True)
        self.remove_button.setIcon(material_icon("close", size=(16, 16), convert_to_pixmap=False))
        self.remove_button.setToolTip("Remove this entry")
        self.remove_button.setAccessibleName("Remove entry")
        layout.addWidget(self.remove_button, 0)

    def key(self) -> str:
        """Return the stripped key, or an empty string in plain-value mode."""
        return self.key_edit.text().strip() if self.key_edit is not None else ""

    def value(self) -> str:
        """Return the value text as typed."""
        return self.value_edit.text()

    def is_blank(self) -> bool:
        """Return whether both the key and the value are empty."""
        return not self.key() and not self.value().strip()


class EntryListEditor(QWidget):
    """Edit a list of strings or a mapping of string keys to string values, one row per entry.

    Blank rows are ignored when reading the value, so users can add a row and leave it empty
    without making the surrounding form invalid.

    Attributes:
        changed: Emitted whenever an entry is added, removed or edited.
    """

    changed = Signal()

    def __init__(  # pylint: disable=too-many-arguments
        self,
        parent: QWidget | None = None,
        *,
        key_value: bool = True,
        key_placeholder: str = "Key",
        value_placeholder: str = "Value",
        add_text: str = "Add entry",
        empty_text: str = "",
    ) -> None:
        """Create the editor.

        Args:
            parent: Optional parent widget.
            key_value: Edit key/value pairs when ``True``, plain values when ``False``.
            key_placeholder: Placeholder text of the key fields.
            value_placeholder: Placeholder text of the value fields.
            add_text: Text of the button that appends a row.
            empty_text: Muted hint shown while there are no rows; hidden when empty.
        """
        super().__init__(parent)
        self._key_value = key_value
        self._key_placeholder = key_placeholder
        self._value_placeholder = value_placeholder
        self._rows: list[_EntryRow] = []
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._rows_layout = QVBoxLayout()
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(6)
        layout.addLayout(self._rows_layout)

        self._empty_label = QLabel(empty_text, self)
        self._empty_label.setWordWrap(True)
        self._empty_label.setEnabled(False)  # muted text in every theme
        self._empty_label.setVisible(bool(empty_text))
        layout.addWidget(self._empty_label)

        self.add_button = QToolButton(self)
        self.add_button.setText(add_text)
        self.add_button.setIcon(material_icon("add", size=(16, 16), convert_to_pixmap=False))
        self.add_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.add_button.setAutoRaise(True)
        self.add_button.clicked.connect(self._add_and_focus)
        layout.addWidget(self.add_button, 0, Qt.AlignmentFlag.AlignLeft)

    @property
    def key_value(self) -> bool:
        """Return whether rows edit key/value pairs (``True``) or plain values (``False``)."""
        return self._key_value

    def rows(self) -> list[_EntryRow]:
        """Return the row widgets, in display order."""
        return list(self._rows)

    def row_count(self) -> int:
        """Return the number of rows, blank ones included."""
        return len(self._rows)

    def add_entry(self, key: str = "", value: str = "") -> _EntryRow:
        """Append a row.

        Args:
            key: Initial key; ignored in plain-value mode.
            value: Initial value.

        Returns:
            The new row widget.
        """
        row = _EntryRow(
            self,
            key_value=self._key_value,
            key_placeholder=self._key_placeholder,
            value_placeholder=self._value_placeholder,
        )
        if row.key_edit is not None:
            row.key_edit.setText(str(key))
            row.key_edit.textChanged.connect(self._emit_changed)
        row.value_edit.setText("" if value is None else str(value))
        row.value_edit.textChanged.connect(self._emit_changed)
        row.remove_button.clicked.connect(lambda _=False, r=row: self._remove_row(r))
        self._rows.append(row)
        self._rows_layout.addWidget(row)
        self._update_empty_state()
        self.changed.emit()
        return row

    def remove_entry(self, index: int) -> None:
        """Remove the row at ``index``.

        Args:
            index: Row index in display order.
        """
        self._remove_row(self._rows[index])

    def clear(self) -> None:
        """Remove all rows."""
        for row in list(self._rows):
            self._remove_row(row, notify=False)
        self.changed.emit()

    def entries(self) -> list[tuple[str, str]]:
        """Return the non-blank rows as ``(key, value)`` tuples; keys are empty in value mode."""
        return [(row.key(), row.value()) for row in self._rows if not row.is_blank()]

    def value(self) -> dict[str, str] | list[str]:
        """Return the content: a dict in key/value mode, a list of values otherwise."""
        if self._key_value:
            return dict(self.entries())
        return [value for _key, value in self.entries()]

    def set_value(self, value) -> None:
        """Replace all rows with ``value``.

        Args:
            value: A mapping in key/value mode, an iterable of values otherwise. ``None``
                clears the editor.
        """
        for row in list(self._rows):
            self._remove_row(row, notify=False)
        if value:
            items = value.items() if self._key_value else (("", v) for v in value)
            for key, item_value in items:
                self.add_entry(key, item_value)
        self._update_empty_state()
        self.changed.emit()

    def set_row_error(self, row: _EntryRow, message: str | None) -> None:
        """Mark a row's key field (or value field in value mode) as invalid.

        Args:
            row: Row widget returned by :meth:`rows`.
            message: Error text shown as tooltip, or ``None`` to clear the error.
        """
        target = row.key_edit if row.key_edit is not None else row.value_edit
        target.setProperty("state", "error" if message else "")
        target.setToolTip(message or "")
        target.style().unpolish(target)
        target.style().polish(target)

    def _add_and_focus(self, *_args) -> None:
        row = self.add_entry()
        (row.key_edit or row.value_edit).setFocus()

    def _remove_row(self, row: _EntryRow, notify: bool = True) -> None:
        self._rows.remove(row)
        self._rows_layout.removeWidget(row)
        row.setParent(None)
        row.deleteLater()
        self._update_empty_state()
        if notify:
            self.changed.emit()

    def _update_empty_state(self) -> None:
        self._empty_label.setVisible(bool(self._empty_label.text()) and not self._rows)

    def _emit_changed(self, *_args) -> None:
        self.changed.emit()


class ExtraFieldsSection(QWidget):
    """Titled key/value editor for fields that are not part of the model.

    Used by ``PydanticWidgetForm`` for models that accept extra fields
    (``model_config = ConfigDict(extra="allow")``).
    """

    def __init__(self, parent: QWidget | None = None, *, title: str, empty_text: str) -> None:
        """Create the section.

        Args:
            parent: Optional parent widget.
            title: Section heading.
            empty_text: Hint shown while there are no extra fields.
        """
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(4)
        self.title_label = QLabel(title, self)
        font = self.title_label.font()
        font.setBold(True)
        self.title_label.setFont(font)
        layout.addWidget(self.title_label)
        self.editor = EntryListEditor(
            self,
            key_value=True,
            key_placeholder="Key",
            value_placeholder="Value",
            add_text="Add field",
            empty_text=empty_text,
        )
        layout.addWidget(self.editor)

    def row_errors(self, reserved_keys: set[str]) -> dict[int, str]:
        """Return error messages of invalid rows, keyed by row index.

        Args:
            reserved_keys: Keys that are taken by the form's own fields.

        Returns:
            Messages for rows with a value but no key, a reserved key or a repeated key.
        """
        errors: dict[int, str] = {}
        seen: set[str] = set()
        for index, row in enumerate(self.editor.rows()):
            if row.is_blank():
                continue
            key = row.key()
            if not key:
                errors[index] = "Enter a key for the value."
            elif key in reserved_keys:
                errors[index] = f"'{key}' is already a field of this form."
            elif key in seen:
                errors[index] = f"Key '{key}' is used more than once."
            seen.add(key)
        return errors

    def show_row_errors(self, reserved_keys: set[str]) -> None:
        """Highlight the invalid rows and clear the highlight of valid ones.

        Args:
            reserved_keys: Keys that are taken by the form's own fields.
        """
        errors = self.row_errors(reserved_keys)
        for index, row in enumerate(self.editor.rows()):
            self.editor.set_row_error(row, errors.get(index))
