"""Scan control with the modernised UX in plain QWidgets, same API as :class:`ScanControl`.

This is the QWidget twin of :class:`ScanControlQML`; both render the same
:class:`ScanFormModel` and view state so they can be compared side by side.
"""

from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox,
    QCompleter,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.utils.ux_kit import (
    Card,
    IconButton,
    SuffixLineEdit,
    TextButton,
    ToggleSwitch,
    field_qss,
    refresh_kit_theme,
    set_invalid,
)
from bec_widgets.widgets.control.scan_control.scan_control_ux_common import ScanControlPortBase


class FieldEditor(QWidget):
    """Label, editor and error line for one form field."""

    def __init__(self, field: dict, control: "ScanControlQWidget", parent: QWidget):
        super().__init__(parent)
        self.key = field["key"]
        self._control = control
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        header = QHBoxLayout()
        header.setSpacing(4)
        self.label = QLabel(field["label"], self)
        header.addWidget(self.label, 1)
        if field["tooltip"]:
            info = IconButton("info", field["tooltip"], self, size=13)
            info.setFixedSize(16, 16)
            info.setToolTip(field["tooltip"])
            header.addWidget(info)
        layout.addLayout(header)

        kind = field["kind"]
        value = field["value"]
        if kind == "bool":
            self.editor = ToggleSwitch(self)
            self.editor.setChecked(bool(value))
            self.editor.toggled.connect(lambda checked: control.set_field(self.key, checked))
        elif kind == "literal":
            self.editor = QComboBox(self)
            for option in field["options"]:
                self.editor.addItem(option or "None", option)
            index = max(0, self.editor.findData(str(value) if value is not None else ""))
            self.editor.setCurrentIndex(index)
            self.editor.activated.connect(
                lambda index: control.set_field(self.key, self.editor.itemData(index))
            )
        elif kind == "device":
            self.editor = QComboBox(self)
            self.editor.setEditable(True)
            self.editor.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            self.editor.addItems(control._device_names())  # pylint: disable=protected-access
            completer = QCompleter(self.editor.model(), self.editor)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.editor.setCompleter(completer)
            self.editor.lineEdit().setPlaceholderText("Device")
            self.editor.setCurrentText(value or "")
            self.editor.currentTextChanged.connect(lambda text: control.set_field(self.key, text))
        else:
            self.editor = SuffixLineEdit(self)
            self.editor.setText("" if value is None else str(value))
            self.editor.setPlaceholderText(field["placeholder"])
            self.editor.set_suffix(field["units"])
            if kind != "str":
                self.editor.setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            self.editor.textEdited.connect(lambda text: control.set_field(self.key, text))
            self.editor.returnPressed.connect(control.run_scan)
        self.editor.setAccessibleName(field["label"])
        if field["tooltip"]:
            self.editor.setToolTip(field["tooltip"])
        layout.addWidget(self.editor)

        self.error = QLabel(self)
        self.error.setVisible(False)
        layout.addWidget(self.error)
        self.set_error("")

    def set_error(self, message: str) -> None:
        """Show or clear the error of this field."""
        self.error.setText(message)
        self.error.setVisible(bool(message))
        set_invalid(self.editor, bool(message))

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens."""
        self.label.setStyleSheet(f"color: {tokens.fg_muted.name()}; font-size: 12px;")
        self.error.setStyleSheet(f"color: {tokens.danger.name()}; font-size: 11px;")


class RowBadge(QLabel):
    """Round row number in front of an argument row."""

    def __init__(self, number: int, parent: QWidget):
        super().__init__(str(number), parent)
        self.setFixedSize(22, 22)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens."""
        self.setStyleSheet(
            f"background: {tokens.track.name()}; color: {tokens.fg_muted.name()};"
            " border-radius: 11px; font-size: 11px; font-weight: 600;"
        )


class ScanControlQWidget(ScanControlPortBase):
    """Scan control with the modernised UX in plain QWidgets."""

    def _init_view(self) -> None:
        self.editors: dict[str, FieldEditor] = {}
        self.group_cards: list[Card] = []
        self._picker_typing = False
        self._built_columns = (0, 0)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # scan picker
        self.header = QWidget(self)
        header_layout = QVBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)
        picker_row = QHBoxLayout()
        picker_row.setSpacing(4)
        self.scan_picker = QComboBox(self.header)
        self.scan_picker.setEditable(True)
        self.scan_picker.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.scan_picker.setAccessibleName("Scan")
        self.scan_picker.lineEdit().setPlaceholderText("Search scans")
        completer = QCompleter(self.scan_picker.model(), self.scan_picker)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.scan_picker.setCompleter(completer)
        self.scan_picker.activated.connect(
            lambda index: self.on_scan_selection_changed(self.scan_picker.itemText(index))
        )
        self.scan_picker.lineEdit().editingFinished.connect(self._confirm_typed_scan)
        self.scan_picker.lineEdit().textEdited.connect(self._on_scan_typed)
        self.info_button = IconButton("info", "Scan documentation", self.header)
        self.info_button.clicked.connect(self.show_selected_scan_info)
        self.filter_button = IconButton(
            "filter_list", "Choose scans shown in the list", self.header
        )
        self.filter_button.clicked.connect(self.show_scan_selector_settings)
        self.restore_button = IconButton(
            "history", "Restore the parameters of the last run of this scan", self.header
        )
        self.restore_button.clicked.connect(self.request_last_executed_scan_parameters)
        picker_row.addWidget(self.scan_picker, 1)
        picker_row.addWidget(self.info_button)
        picker_row.addWidget(self.filter_button)
        picker_row.addWidget(self.restore_button)
        header_layout.addLayout(picker_row)
        self.summary_label = QLabel(self.header)
        self.summary_label.setWordWrap(True)
        header_layout.addWidget(self.summary_label)
        root.addWidget(self.header)

        # groups
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.groups_widget = QWidget(self.scroll)
        self.groups_layout = QVBoxLayout(self.groups_widget)
        self.groups_layout.setContentsMargins(0, 0, 0, 0)
        self.groups_layout.setSpacing(8)
        self.groups_layout.addStretch(1)
        self.scroll.setWidget(self.groups_widget)
        root.addWidget(self.scroll, 1)
        self.empty_label = QLabel(self.groups_widget)
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.groups_layout.insertWidget(0, self.empty_label)

        # footer
        self.footer = Card(parent=self, padding=8)
        self.footer.body.setSpacing(6)
        self.hint_label = QLabel(self.footer)
        self.footer.body.addWidget(self.hint_label)
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self.metadata_button = TextButton("Metadata", "neutral", "check_circle", self.footer)
        self.metadata_button.clicked.connect(self.show_metadata_dialog)
        self.start_button = TextButton("Start", "success", "play_arrow", self.footer)
        self.start_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.start_button.clicked.connect(self.run_scan)
        self.stop_button = TextButton("Stop", "danger", "stop", self.footer)
        self.stop_button.clicked.connect(self.stop_scan)
        buttons.addWidget(self.metadata_button)
        buttons.addWidget(self.start_button, 1)
        buttons.addWidget(self.stop_button)
        self.footer.body.addLayout(buttons)
        root.addWidget(self.footer)
        self._metadata_icon_valid: bool | None = None
        self._apply_styles(ThemeTokens())

    # ---- scan picker -------------------------------------------------------------------

    def _on_scan_typed(self, text: str) -> None:
        self._picker_typing = True
        set_invalid(self.scan_picker, bool(text) and not self.is_valid_scan(text))

    def _confirm_typed_scan(self) -> None:
        self._picker_typing = False
        text = self.scan_picker.currentText()
        if self.is_valid_scan(text):
            self.on_scan_selection_changed(text)
        self.scan_picker.setCurrentText(self._selected_scan)
        set_invalid(self.scan_picker, False)

    # ---- layout --------------------------------------------------------------------------

    def _columns(self) -> tuple[int, int]:
        """Columns for argument rows and for keyword fields at the current width."""
        width = self.scroll.viewport().width()
        return max(1, (width - 80) // 75), max(1, (width - 30) // 170)

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        if hasattr(self, "footer") and self._columns() != self._built_columns:
            self._rebuild_groups()
            self._sync_view(False)

    # ---- rendering ---------------------------------------------------------------------

    def _apply_styles(self, tokens: ThemeTokens) -> None:
        self.setStyleSheet(field_qss(tokens))
        self.summary_label.setStyleSheet(f"color: {tokens.fg_muted.name()}; font-size: 12px;")
        self.empty_label.setStyleSheet(f"color: {tokens.fg_muted.name()}; font-size: 13px;")
        self.scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self.groups_widget.setStyleSheet("background: transparent;")
        self._hint_tokens = tokens

    def _rebuild_groups(self) -> None:
        for card in self.group_cards:
            self.groups_layout.removeWidget(card)
            card.hide()
            # Detach right away so the old cards stop taking part in style polishing
            # before the deferred delete runs.
            card.setParent(None)
            card.deleteLater()
        self.group_cards = []
        self.editors = {}
        self._built_columns = self._columns()
        state = self.view_state()
        for group in self.form.groups():
            card = Card(group["title"], self.groups_widget)
            if group["kind"] == "args":
                count = len(group["rows"])
                card.set_title(group["title"], f"{count} row{'s' if count != 1 else ''}")
                add = TextButton("Add row", "ghost", "add", card)
                add.setEnabled(group["canAdd"])
                add.setVisible(state["showRowButtons"])
                add.clicked.connect(self.add_row)
                card.add_header_widget(add)
                for index, row in enumerate(group["rows"]):
                    card.body.addLayout(self._build_row(index, row, group["canRemove"], card))
                card.setVisible(state["showArgs"])
            else:
                grid = QGridLayout()
                grid.setHorizontalSpacing(10)
                grid.setVerticalSpacing(8)
                columns = self._built_columns[1]
                for index, field in enumerate(group["fields"]):
                    editor = FieldEditor(field, self, card)
                    self.editors[field["key"]] = editor
                    grid.addWidget(
                        editor, index // columns, index % columns, Qt.AlignmentFlag.AlignTop
                    )
                for column in range(columns):
                    grid.setColumnStretch(column, 1)
                card.body.addLayout(grid)
                card.setVisible(state["showKwargs"])
            self.groups_layout.insertWidget(self.groups_layout.count() - 1, card)
            self.group_cards.append(card)
        # The root style sheet already cascades to the new cards; only the kit controls need
        # their tokens. Re-setting the root style sheet here repolished the whole tree on
        # every scan switch.
        self._hint_tokens = refresh_kit_theme(self.groups_widget)

    def _build_row(self, index: int, row: list[dict], can_remove: bool, card: Card) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(8)
        badge = RowBadge(index + 1, card)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        badge.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(badge, Qt.AlignmentFlag.AlignTop)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        columns = max(1, min(len(row), self._built_columns[0]))
        for position, field in enumerate(row):
            editor = FieldEditor(field, self, card)
            self.editors[field["key"]] = editor
            grid.addWidget(
                editor, position // columns, position % columns, Qt.AlignmentFlag.AlignTop
            )
        for column in range(columns):
            grid.setColumnStretch(column, 1)
        layout.addLayout(grid, 1)
        remove = IconButton("close", f"Remove row {index + 1}", card)
        remove.setEnabled(can_remove)
        remove.setVisible(not self._hide_add_remove_buttons)
        remove.clicked.connect(lambda _checked=False, i=index: self.remove_row(i))
        layout.addWidget(remove, 0, Qt.AlignmentFlag.AlignTop)
        return layout

    def _sync_view(self, structure: bool) -> None:
        if not hasattr(self, "footer"):
            return
        state = self.view_state()
        if structure:
            names = state["scans"]
            if [self.scan_picker.itemText(i) for i in range(self.scan_picker.count())] != names:
                self.scan_picker.blockSignals(True)
                self.scan_picker.clear()
                self.scan_picker.addItems(names)
                for index, name in enumerate(names):
                    self.scan_picker.setItemData(
                        index, self.scan_tooltip(name), Qt.ItemDataRole.ToolTipRole
                    )
                self.scan_picker.blockSignals(False)
            self._rebuild_groups()
        if not self._picker_typing:
            self.scan_picker.setCurrentText(state["current"])
        self.scan_picker.setToolTip(self.scan_tooltip(state["current"]) if state["current"] else "")
        self.header.setVisible(state["showSelector"])
        self.filter_button.setVisible(state["showFilter"])
        self.info_button.setEnabled(bool(state["current"]))
        self.restore_button.setEnabled(bool(state["current"]) and not state["restoreBusy"])
        self.summary_label.setText(state["summary"])
        self.summary_label.setVisible(bool(state["summary"]))
        if state["current"]:
            self.empty_label.hide()
        else:
            self.empty_label.setText(
                "No scans are available. Check the scan filter or the BEC server."
                if not state["scans"]
                else "Choose a scan to set its parameters."
            )
            self.empty_label.show()

        for key, editor in self.editors.items():
            editor.set_error(state["errors"].get(key, ""))

        tokens = ThemeTokens()
        self.hint_label.setText(state["hint"])
        self.hint_label.setVisible(bool(state["hint"]))
        hint_color = tokens.danger if state["metadataValid"] else tokens.warning
        self.hint_label.setStyleSheet(f"color: {hint_color.name()}; font-size: 12px;")
        self.footer.setVisible(state["showButtons"] or state["showMetadata"])
        self.metadata_button.setVisible(state["showMetadata"])
        if self._metadata_icon_valid != state["metadataValid"]:
            self._metadata_icon_valid = state["metadataValid"]
            # pylint: disable=protected-access
            self.metadata_button._icon_name = "check_circle" if state["metadataValid"] else "error"
            self.metadata_button.refresh_theme(tokens)
            self.metadata_button.setToolTip(
                "Metadata is complete" if state["metadataValid"] else "Metadata needs attention"
            )
        self.start_button.setVisible(state["showButtons"])
        self.stop_button.setVisible(state["showButtons"])
        self.start_button.setText(state["startLabel"])
        self.start_button.setEnabled(state["canStart"])
        self.stop_button.setText(state["stopLabel"])

    def apply_theme(self, theme: str):
        super().apply_theme(theme)
        if hasattr(self, "footer"):
            tokens = refresh_kit_theme(self)
            self._apply_styles(tokens)
            self._sync_view(False)


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    widget = ScanControlQWidget()
    widget.show()
    sys.exit(app.exec())
