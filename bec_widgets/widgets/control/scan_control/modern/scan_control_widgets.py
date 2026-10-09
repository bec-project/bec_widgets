"""Scan control built from QWidgets with the same layout and behaviour as the QML version."""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QLocale, QSize, Qt, QTimer, Signal
from qtpy.QtGui import QDoubleValidator, QIntValidator
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QCompleter,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import rgba
from bec_widgets.widgets.control.scan_control.modern.base import ModernScanControlBase
from bec_widgets.widgets.control.scan_control.modern.form_core import FieldSpec
from bec_widgets.widgets.control.scan_control.modern.qml_support import theme_colors
from bec_widgets.widgets.utility.toggle.toggle import ToggleSwitch

WIDE_LAYOUT_WIDTH = 620


def _icon(name: str, color, filled: bool = False):
    return material_icon(name, size=(18, 18), color=color, filled=filled, convert_to_pixmap=False)


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


# ---------------------------------------------------------------------- editors


class _EditorMixin:
    """Common interface of all editors: ``edited`` signal plus value/units/error setters."""

    def set_value(self, value) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def set_units(self, units: str) -> None:
        """Units are only shown by numeric editors."""

    def set_error(self, error: str) -> None:
        """Mark the editor invalid and show the reason as tooltip."""
        invalid = bool(error)
        if self.property("invalid") != invalid:
            self.setProperty("invalid", invalid)
            _repolish(self)
        self.setToolTip(error or getattr(self, "_tooltip", ""))


class NumberEdit(_EditorMixin, QLineEdit):
    """Free-text numeric input with units inside the box and arrow-key stepping."""

    edited = Signal(object)

    def __init__(self, spec: FieldSpec | dict, parent=None):
        super().__init__(parent)
        self.setObjectName("scField")
        get = spec.get if isinstance(spec, dict) else lambda k, d=None: getattr(spec, k, d)
        self._is_int = get("kind") == "int"
        self._decimals = get("decimals", 6) or 0
        self._min = get("minimum")
        self._max = get("maximum")
        lo = -2147483647 if self._min is None else self._min
        hi = 2147483647 if self._max is None else self._max
        if self._is_int:
            validator = QIntValidator(int(lo), int(hi), self)
        else:
            validator = QDoubleValidator(lo, hi, self._decimals, self)
            validator.setNotation(QDoubleValidator.Notation.StandardNotation)
            validator.setLocale(QLocale.c())
        self.setValidator(validator)
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._tooltip = get("tooltip") or ""
        self.setToolTip(self._tooltip)
        self._unit = QLabel(self)
        self._unit.setObjectName("scMuted")
        self._unit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._value = None
        self.editingFinished.connect(self._commit)

    def _format(self, value) -> str:
        if value is None or value == "":
            return ""
        if self._is_int:
            return str(int(value))
        return f"{float(value):.{self._decimals}f}".rstrip("0").rstrip(".") or "0"

    def set_value(self, value) -> None:
        self._value = value
        if not self.hasFocus():
            self.setText(self._format(value))

    def set_units(self, units: str) -> None:
        self._unit.setText(units)
        self._unit.adjustSize()
        self.setTextMargins(0, 0, self._unit.width() + 6 if units else 0, 0)
        self._place_unit()

    def _place_unit(self) -> None:
        self._unit.move(
            self.width() - self._unit.width() - 10, (self.height() - self._unit.height()) // 2
        )

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        self._place_unit()

    def _commit(self) -> None:
        if not self.hasAcceptableInput():
            self.setText(self._format(self._value))
            return
        text = self.text()
        self.edited.emit(int(text) if self._is_int else float(text))

    def keyPressEvent(self, event):  # pylint: disable=invalid-name
        step = {Qt.Key.Key_Up: 1, Qt.Key.Key_Down: -1}.get(event.key())
        if step is None:
            super().keyPressEvent(event)
            return
        try:
            value = float(self.text() or 0)
        except ValueError:
            value = 0.0
        value += step * (1 if self._is_int else 10 ** -min(self._decimals, 2))
        if self._min is not None:
            value = max(value, self._min)
        if self._max is not None:
            value = min(value, self._max)
        self.setText(self._format(round(value, self._decimals)))
        self._commit()


class TextEdit(_EditorMixin, QLineEdit):
    """Plain text input."""

    edited = Signal(object)

    def __init__(self, tooltip: str = "", placeholder: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("scField")
        self._tooltip = tooltip
        self.setToolTip(tooltip)
        self.setPlaceholderText(placeholder)
        self.editingFinished.connect(lambda: self.edited.emit(self.text()))

    def set_value(self, value) -> None:
        if not self.hasFocus():
            self.setText("" if value is None else str(value))


class DeviceEdit(_EditorMixin, QComboBox):
    """Editable device picker with substring completion."""

    edited = Signal(object)

    def __init__(self, tooltip: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("scField")
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.lineEdit().setPlaceholderText("Device")
        completer = QCompleter(self.model(), self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.setCompleter(completer)
        self._tooltip = tooltip
        self.setToolTip(tooltip)
        self._value = ""
        self.activated.connect(lambda _i: self._commit())
        self.lineEdit().editingFinished.connect(self._commit)

    def set_devices(self, devices: list[str]) -> None:
        """Replace the offered devices, keeping the typed text."""
        if [self.itemText(i) for i in range(self.count())] == devices:
            return
        text = self.currentText()
        self.blockSignals(True)
        self.clear()
        self.addItems(devices)
        self.setCurrentIndex(-1)
        self.setEditText(text)
        self.blockSignals(False)

    def set_value(self, value) -> None:
        self._value = value or ""
        if not self.lineEdit().hasFocus():
            self.setEditText(self._value)

    def set_error(self, error: str) -> None:
        # An empty field is explained in the footer; only flag a wrong name in red.
        super().set_error(error if self._value else "")

    def _commit(self) -> None:
        if self.currentText() != self._value:
            self.edited.emit(self.currentText())


class ChoiceEdit(_EditorMixin, QComboBox):
    """Drop-down for ``Literal`` arguments; an empty choice is shown as "None"."""

    edited = Signal(object)

    def __init__(self, choices: list[str], tooltip: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("scField")
        for choice in choices:
            self.addItem(choice or "None", choice)
        self._tooltip = tooltip
        self.setToolTip(tooltip)
        self.activated.connect(lambda i: self.edited.emit(self.itemData(i)))

    def set_value(self, value) -> None:
        index = self.findData("" if value is None else str(value))
        self.setCurrentIndex(max(index, 0))


class BoolEdit(_EditorMixin, QWidget):
    """Toggle switch with an On/Off caption."""

    edited = Signal(object)

    def __init__(self, tooltip: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.toggle = ToggleSwitch(self, checked=False)
        self.toggle.setFixedSize(38, 22)
        self.caption = QLabel("Off", self)
        self.caption.setObjectName("scMuted")
        layout.addWidget(self.toggle)
        layout.addWidget(self.caption)
        layout.addStretch(1)
        self.setToolTip(tooltip)
        self.toggle.stateChanged.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        self.caption.setText("On" if checked else "Off")
        self.edited.emit(checked)

    def set_value(self, value) -> None:
        self.toggle.blockSignals(True)
        self.toggle.setChecked(bool(value))
        self.toggle.blockSignals(False)
        self.caption.setText("On" if value else "Off")


def make_editor(spec: FieldSpec, parent: QWidget) -> QWidget:
    """Create the editor for one scan field."""
    if spec.kind == "device":
        return DeviceEdit(spec.tooltip, parent)
    if spec.kind in ("int", "float"):
        return NumberEdit(spec, parent)
    if spec.kind == "bool":
        return BoolEdit(spec.tooltip, parent)
    if spec.kind == "choice":
        return ChoiceEdit(spec.choices, spec.tooltip, parent)
    return TextEdit(spec.tooltip, parent=parent)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.deleteLater()
        elif item.layout() is not None:
            _clear_layout(item.layout())


# ---------------------------------------------------------------------- building blocks


class Card(QFrame):
    """Titled section; optionally collapsible by clicking its header."""

    def __init__(self, title: str = "", collapsible: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("scCard")
        self._collapsible = collapsible
        self._expanded = True
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)
        header = QHBoxLayout()
        header.setSpacing(6)
        self.chevron = QLabel(self)
        self.chevron.setVisible(collapsible)
        self.title = QLabel(title.upper(), self)
        self.title.setObjectName("scCardTitle")
        self.subtitle = QLabel(self)
        self.subtitle.setObjectName("scMuted")
        self.subtitle.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.trailing = QHBoxLayout()
        header.addWidget(self.chevron)
        header.addWidget(self.title)
        header.addWidget(self.subtitle, 1)
        header.addLayout(self.trailing)
        outer.addLayout(header)
        self.body_widget = QWidget(self)
        self.body = QVBoxLayout(self.body_widget)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(8)
        outer.addWidget(self.body_widget)
        if collapsible:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.body_widget.setCursor(Qt.CursorShape.ArrowCursor)

    def set_title(self, title: str) -> None:
        """Set the header text."""
        self.title.setText(title.upper())

    def set_expanded(self, expanded: bool) -> None:
        """Show or hide the body."""
        self._expanded = expanded
        self.body_widget.setVisible(expanded)
        self.update_chevron()

    def update_chevron(self) -> None:
        """Redraw the chevron in the current theme colour."""
        _, colors = theme_colors()
        muted = _muted(colors)
        name = "expand_more" if self._expanded else "chevron_right"
        self.chevron.setPixmap(_icon(name, muted).pixmap(18, 18))

    def mousePressEvent(self, event):  # pylint: disable=invalid-name
        if self._collapsible and event.position().y() < 40:
            self.set_expanded(not self._expanded)
            return
        super().mousePressEvent(event)


def _muted(colors):
    fg, card = colors["FG"], colors["CARD_BG"]
    return _mix_hex(fg, card, 0.4)


def _hover(colors):
    fg, card = colors["FG"], colors["CARD_BG"]
    return _mix_hex(card, fg, 0.08)


def _mix_hex(a, b, t: float) -> str:
    r, g, bl = (round(x + (y - x) * t) for x, y in zip(a.getRgb()[:3], b.getRgb()[:3]))
    return f"#{r:02x}{g:02x}{bl:02x}"


def _icon_button(parent, tip: str) -> QToolButton:
    button = QToolButton(parent)
    button.setObjectName("scIcon")
    button.setToolTip(tip)
    button.setAccessibleName(tip)
    button.setIconSize(QSize(18, 18))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def _button(text: str, name: str, parent) -> QPushButton:
    button = QPushButton(text, parent)
    button.setObjectName(name)
    button.setIconSize(QSize(18, 18))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


# ---------------------------------------------------------------------- the widget


class ScanControlModern(ModernScanControlBase):
    """Widget to submit new scans to the queue, built from QWidgets."""

    # The view is created in _build_view, which ModernScanControlBase.__init__ calls.
    # pylint: disable=attribute-defined-outside-init,too-many-instance-attributes

    ICON_NAME = "tune"

    def _build_view(self) -> None:  # pylint: disable=too-many-statements
        self.setObjectName("scRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._wide = False
        self._arg_editors: list[dict[str, QWidget]] = []
        self._kwarg_editors: dict[str, QWidget] = {}
        self._meta_editors: dict[str, QWidget] = {}
        self._expert_shown: dict[str, bool] = {}
        self._notice_timer = QTimer(self)
        self._notice_timer.setSingleShot(True)
        self._notice_timer.setInterval(4000)
        self._notice_timer.timeout.connect(self._refresh_status)
        self._notice_text = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("scScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("scContent")
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(10, 12, 10, 12)
        self.content_layout.setSpacing(10)
        self.empty_label = QLabel(
            "No scans available. Check the scan filter or the BEC server.", content
        )
        self.empty_label.setObjectName("scMuted")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.empty_label)
        self.arg_card = Card(parent=content)
        self.arg_grid = QGridLayout()
        self.arg_grid.setHorizontalSpacing(6)
        self.arg_grid.setVerticalSpacing(8)
        self.arg_card.body.addLayout(self.arg_grid)
        self.add_row_button = _button("Add row", "scGhost", self.arg_card)
        self.add_row_button.clicked.connect(self.form.add_row)
        self.arg_card.body.addWidget(self.add_row_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.content_layout.addWidget(self.arg_card)
        self.groups_layout = QVBoxLayout()
        self.groups_layout.setSpacing(10)
        self.content_layout.addLayout(self.groups_layout)
        self.content_layout.addWidget(self._build_metadata_card(content))
        self.content_layout.addStretch(1)
        self.scroll.setWidget(content)
        root.addWidget(self.scroll, 1)
        root.addWidget(self._build_footer())

        self.form.rebuilt.connect(self._rebuild_form)
        self.form.values_changed.connect(self._refresh_values)
        self.metadata.rebuilt.connect(self._rebuild_metadata)
        self.metadata.values_changed.connect(self._refresh_metadata)
        self.status_changed.connect(self._refresh_status)
        self.notice.connect(self._show_notice)
        self.setMinimumSize(360, 420)
        self.apply_theme("")

    def _build_header(self) -> QWidget:
        self.header = QFrame(self)
        self.header.setObjectName("scHeader")
        layout = QVBoxLayout(self.header)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.scan_picker = QComboBox(self.header)
        self.scan_picker.setObjectName("scPicker")
        self.scan_picker.setEditable(True)
        self.scan_picker.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.scan_picker.setAccessibleName("Scan")
        self.scan_picker.lineEdit().setPlaceholderText("Search scans")
        self._search_action = self.scan_picker.lineEdit().addAction(
            _icon("search", "#888888"), QLineEdit.ActionPosition.LeadingPosition
        )
        completer = QCompleter(self.scan_picker.model(), self.scan_picker)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.scan_picker.setCompleter(completer)
        self.scan_picker.activated.connect(lambda _i: self._confirm_scan())
        self.scan_picker.lineEdit().editingFinished.connect(self._confirm_scan)
        self.scan_picker.lineEdit().textEdited.connect(self._on_scan_typed)
        self.info_button = _icon_button(self.header, "Documentation of this scan")
        self.info_button.clicked.connect(self.show_selected_scan_info)
        self.filter_button = _icon_button(self.header, "Choose which scans are listed")
        self.filter_button.clicked.connect(self.show_scan_selector_settings)
        row.addWidget(self.scan_picker, 1)
        row.addWidget(self.info_button)
        row.addWidget(self.filter_button)
        layout.addLayout(row)
        self.summary_label = QLabel(self.header)
        self.summary_label.setObjectName("scMuted")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        return self.header

    def _build_metadata_card(self, parent) -> QWidget:
        self.meta_card = Card("Metadata", collapsible=True, parent=parent)
        self.meta_badge = QLabel(self.meta_card)
        self.meta_badge.setObjectName("scBadge")
        self.meta_card.trailing.addWidget(self.meta_badge)
        self.meta_grid = QGridLayout()
        self.meta_grid.setHorizontalSpacing(10)
        self.meta_grid.setVerticalSpacing(8)
        self.meta_card.body.addLayout(self.meta_grid)
        self.extras_widget = QWidget(self.meta_card)
        extras_layout = QVBoxLayout(self.extras_widget)
        extras_layout.setContentsMargins(0, 4, 0, 0)
        extras_layout.setSpacing(6)
        title = QLabel("Additional entries", self.extras_widget)
        title.setObjectName("scMuted")
        extras_layout.addWidget(title)
        self.extras_rows = QVBoxLayout()
        self.extras_rows.setSpacing(6)
        extras_layout.addLayout(self.extras_rows)
        self.add_extra_button = _button("Add entry", "scGhost", self.extras_widget)
        self.add_extra_button.clicked.connect(
            lambda: self.metadata.set_extras(self.metadata.extras + [["", ""]])
        )
        extras_layout.addWidget(self.add_extra_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.meta_card.body.addWidget(self.extras_widget)
        self.meta_card.set_expanded(False)
        return self.meta_card

    def _build_footer(self) -> QWidget:
        self.footer = QFrame(self)
        self.footer.setObjectName("scFooter")
        layout = QVBoxLayout(self.footer)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        message = QHBoxLayout()
        message.setSpacing(6)
        self.message_icon = QLabel(self.footer)
        self.message_label = QLabel(self.footer)
        self.message_label.setObjectName("scMessage")
        self.message_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        message.addWidget(self.message_icon)
        message.addWidget(self.message_label, 1)
        layout.addLayout(message)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.restore_button = _button("Restore last", "scGhost", self.footer)
        self.restore_button.setToolTip("Fill in the parameters of the last run of this scan")
        self.restore_button.clicked.connect(self.request_last_executed_scan_parameters)
        self.stop_button = _button("Stop", "scStop", self.footer)
        self.stop_button.clicked.connect(self.stop_scan)
        self.start_button = _button("Start", "scPrimary", self.footer)
        self.start_button.clicked.connect(self.run_scan)
        self.start_button.setMaximumWidth(220)
        buttons.addWidget(self.restore_button)
        buttons.addStretch(1)
        buttons.addWidget(self.stop_button)
        buttons.addWidget(self.start_button)
        layout.addLayout(buttons)
        return self.footer

    # ------------------------------------------------------------------ scan picker

    def _on_scan_typed(self, text: str) -> None:
        self._set_invalid(self.scan_picker, bool(text) and not self.is_valid_scan(text))

    def _confirm_scan(self) -> None:
        text = self.scan_picker.currentText()
        if self.is_valid_scan(text):
            self.set_current_scan(text)
        self._sync_picker()

    def _sync_picker(self) -> None:
        items = [self.scan_picker.itemText(i) for i in range(self.scan_picker.count())]
        self.scan_picker.blockSignals(True)
        if items != self.visible_scans:
            self.scan_picker.clear()
            self.scan_picker.addItems(self.visible_scans)
        self.scan_picker.setCurrentIndex(self.scan_picker.findText(self.current_scan))
        self.scan_picker.setEditText(self.current_scan)
        self.scan_picker.blockSignals(False)
        self._set_invalid(self.scan_picker, False)

    @staticmethod
    def _set_invalid(widget: QWidget, invalid: bool) -> None:
        if widget.property("invalid") != invalid:
            widget.setProperty("invalid", invalid)
            _repolish(widget)

    # ------------------------------------------------------------------ form

    def _rebuild_form(self) -> None:
        spec = self.form.spec
        self.summary_label.setText(spec.summary)
        self.summary_label.setVisible(bool(spec.summary))

        _clear_layout(self.arg_grid)
        self._arg_editors = []
        self.arg_card.set_title(spec.arg_title)
        rows = len(self.form.arg_rows)
        self.arg_card.subtitle.setText(f"{rows} rows" if rows > 1 else "")
        for column, field in enumerate(spec.arg_fields, start=1):
            heading = QLabel(field.label, self.arg_card)
            heading.setObjectName("scMuted")
            self.arg_grid.addWidget(heading, 0, column)
            self.arg_grid.setColumnStretch(column, 14 if field.kind == "device" else 9)
        self.arg_grid.setColumnMinimumWidth(0, 22)
        for row in range(rows):
            number = QLabel(str(row + 1), self.arg_card)
            number.setObjectName("scMuted")
            number.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.arg_grid.addWidget(number, row + 1, 0)
            editors = {}
            for column, field in enumerate(spec.arg_fields, start=1):
                editor = make_editor(field, self.arg_card)
                editor.edited.connect(
                    lambda value, r=row, n=field.name: self.form.set_arg_value(r, n, value)
                )
                self.arg_grid.addWidget(editor, row + 1, column)
                editors[field.name] = editor
            remove = _icon_button(self.arg_card, f"Remove row {row + 1}")
            remove.setIcon(_icon("close", self._colors["muted"]))
            remove.clicked.connect(lambda _=False, r=row: self.form.remove_row(r))
            remove.setProperty("remove_row", True)
            policy = remove.sizePolicy()
            policy.setRetainSizeWhenHidden(True)
            remove.setSizePolicy(policy)
            self.arg_grid.addWidget(remove, row + 1, len(spec.arg_fields) + 1)
            self._arg_editors.append(editors)

        self._rebuild_groups()
        self._refresh_values()
        self._refresh_status()

    def _rebuild_groups(self) -> None:
        _clear_layout(self.groups_layout)
        self._kwarg_editors = {}
        columns = 2 if self._wide else 1
        for group in self.form.spec.groups:
            card = Card(group.name, parent=self.scroll.widget())
            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(8)
            show_expert = self._expert_shown.get(group.name, False)
            fields = [f for f in group.fields if not f.expert or show_expert]
            for index, field in enumerate(fields):
                row, column = divmod(index, columns)
                label = QLabel(field.label, card)
                label.setToolTip(field.tooltip or field.label)
                label.setFixedWidth(120)
                editor = make_editor(field, card)
                editor.edited.connect(
                    lambda value, n=field.name: self.form.set_kwarg_value(n, value)
                )
                grid.addWidget(label, row, column * 2)
                grid.addWidget(editor, row, column * 2 + 1)
                grid.setColumnStretch(column * 2 + 1, 1)
                self._kwarg_editors[field.name] = editor
            card.body.addLayout(grid)
            expert_count = sum(f.expert for f in group.fields)
            if expert_count:
                toggle = _button(
                    f"{'Hide' if show_expert else 'Show'} advanced ({expert_count})",
                    "scGhost",
                    card,
                )
                toggle.setIcon(
                    _icon("expand_less" if show_expert else "expand_more", self._colors["fg"])
                )
                toggle.clicked.connect(lambda _=False, g=group.name: self._toggle_expert(g))
                card.body.addWidget(toggle, 0, Qt.AlignmentFlag.AlignLeft)
            card.setVisible(not self.hide_kwarg_boxes)
            self.groups_layout.addWidget(card)

    def _toggle_expert(self, group: str) -> None:
        self._expert_shown[group] = not self._expert_shown.get(group, False)
        self._rebuild_groups()
        self._refresh_values()

    def _refresh_values(self) -> None:
        form = self.form
        for row, editors in enumerate(self._arg_editors):
            if row >= len(form.arg_rows):
                break
            values = form.arg_rows[row]
            for field in form.spec.arg_fields:
                editor = editors[field.name]
                if isinstance(editor, DeviceEdit):
                    editor.set_devices(form.device_names)
                editor.set_value(values.get(field.name))
                editor.set_units(form.units_for(field, row))
                editor.set_error(form.field_error(field, values.get(field.name)))
        for field in form.spec.kwarg_fields:
            editor = self._kwarg_editors.get(field.name)
            if editor is None:
                continue
            if isinstance(editor, DeviceEdit):
                editor.set_devices(form.device_names)
            editor.set_value(form.kwargs.get(field.name))
            editor.set_units(form.units_for(field))
            editor.set_error(form.field_error(field, form.kwargs.get(field.name)))

    # ------------------------------------------------------------------ metadata

    def _rebuild_metadata(self) -> None:
        _clear_layout(self.meta_grid)
        self._meta_editors = {}
        for index, field in enumerate(self.metadata.fields):
            label = QLabel(field.label + (" *" if field.required else ""), self.meta_card)
            label.setToolTip(field.description or field.label)
            label.setFixedWidth(120)
            if field.kind in ("int", "float"):
                editor = NumberEdit({"kind": field.kind, "decimals": 6}, self.meta_card)
            elif field.kind == "bool":
                editor = BoolEdit(field.description, self.meta_card)
            else:
                editor = TextEdit(
                    field.description, field.placeholder(self.metadata.scan_name), self.meta_card
                )
            editor.edited.connect(lambda value, n=field.name: self.metadata.set_value(n, value))
            self.meta_grid.addWidget(label, index, 0)
            self.meta_grid.addWidget(editor, index, 1)
            self._meta_editors[field.name] = editor
        self._refresh_metadata()

    def _refresh_metadata(self) -> None:
        meta = self.metadata
        for name, editor in self._meta_editors.items():
            editor.set_value(meta.values.get(name))
            editor.set_error(meta.errors.get(name, ""))
        if len(meta.extras) != self.extras_rows.count():
            self._rebuild_extras()
        for index, (key, value) in enumerate(meta.extras):
            row = self.extras_rows.itemAt(index).widget()
            row.key_edit.set_value(key)
            row.value_edit.set_value(value)
        errors = len(meta.errors)
        self.meta_badge.setText(f"{errors} to fix" if errors else "")
        self.meta_badge.setVisible(bool(errors))
        self.meta_card.subtitle.setText("" if errors else (meta.summary() or "optional"))
        if errors:
            self.meta_card.set_expanded(True)

    def _rebuild_extras(self) -> None:
        _clear_layout(self.extras_rows)
        for index in range(len(self.metadata.extras)):
            row = QWidget(self.extras_widget)
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)
            row.key_edit = TextEdit(placeholder="Key", parent=row)
            row.value_edit = TextEdit(placeholder="Value", parent=row)
            remove = _icon_button(row, "Remove entry")
            remove.setIcon(_icon("close", self._colors["muted"]))
            row.key_edit.edited.connect(lambda v, i=index: self._set_extra(i, 0, v))
            row.value_edit.edited.connect(lambda v, i=index: self._set_extra(i, 1, v))
            remove.clicked.connect(lambda _=False, i=index: self._remove_extra(i))
            layout.addWidget(row.key_edit, 1)
            layout.addWidget(row.value_edit, 1)
            layout.addWidget(remove)
            self.extras_rows.addWidget(row)

    def _set_extra(self, index: int, column: int, value: str) -> None:
        extras = [list(pair) for pair in self.metadata.extras]
        extras[index][column] = value
        self.metadata.set_extras(extras)

    def _remove_extra(self, index: int) -> None:
        extras = [list(pair) for pair in self.metadata.extras]
        del extras[index]
        self.metadata.set_extras(extras)

    # ------------------------------------------------------------------ status

    def _show_notice(self, text: str) -> None:
        self._notice_text = text
        self._notice_timer.start()
        self._refresh_status()

    def _refresh_status(self) -> None:
        if not self._notice_timer.isActive():
            self._notice_text = ""
        problems = self.problems()
        if self.scan_picker.lineEdit().hasFocus() is False:
            self._sync_picker()
        self.header.setVisible(not self.hide_scan_selection_combobox)
        self.filter_button.setVisible(not self.hide_scan_selector_settings_button)
        self.info_button.setEnabled(bool(self.current_scan))
        self.empty_label.setVisible(not self.visible_scans)
        self.arg_card.setVisible(bool(self.form.spec.arg_fields) and not self.hide_arg_box)
        for index in range(self.groups_layout.count()):
            self.groups_layout.itemAt(index).widget().setVisible(not self.hide_kwarg_boxes)
        self.meta_card.setVisible(not self.hide_metadata and bool(self.current_scan))
        self.extras_widget.setVisible(not self.hide_optional_metadata)
        self.footer.setVisible(not self.hide_scan_control_buttons)

        editing = not self.hide_add_remove_buttons
        self.add_row_button.setVisible(editing and self.form.can_add_row())
        for index in range(self.arg_grid.count()):
            widget = self.arg_grid.itemAt(index).widget()
            if widget is not None and widget.property("remove_row"):
                # Keep the column while rows cannot be removed, so the fields do not jump.
                widget.setVisible(editing and self.form.can_remove_row())

        show_problem = not self._notice_text and bool(problems)
        if show_problem:
            more = f"  (+{len(problems) - 1} more)" if len(problems) > 1 else ""
            text, icon, color = problems[0] + more, "error", self._colors["warning"]
        else:
            text, icon, color = self._notice_text, "check_circle", self._colors["success"]
        self.message_label.setText(text)
        self.message_icon.setPixmap(_icon(icon, color, filled=True).pixmap(16, 16))
        self.message_icon.setVisible(bool(text))
        self.message_label.setVisible(bool(text))

        self.restore_button.setText("Restoring…" if self.is_restoring else "Restore last")
        self.restore_button.setEnabled(not self.is_restoring and bool(self.current_scan))
        armed = self.stop_armed
        self.stop_button.setText("Halt now" if armed else "Stop")
        if self.stop_button.property("armed") != armed:
            self.stop_button.setProperty("armed", armed)
            _repolish(self.stop_button)
        self.stop_button.setIcon(
            _icon("stop", self._colors["onPrimary"] if armed else self._colors["danger"], True)
        )
        metrics = self.start_button.fontMetrics()
        self.start_button.setText(
            metrics.elidedText(f"Start {self.current_scan}", Qt.TextElideMode.ElideRight, 170)
        )
        self.start_button.setEnabled(not problems)

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        super().resizeEvent(event)
        wide = self.width() > WIDE_LAYOUT_WIDTH
        if wide != self._wide:
            self._wide = wide
            self._rebuild_groups()
            self._refresh_values()

    # ------------------------------------------------------------------ theme

    def apply_theme(self, theme: str):
        """Restyle the widget from the active BEC theme colours."""
        _, colors = theme_colors()
        c = {k: v.name() for k, v in colors.items()}
        self._colors = {
            "fg": c["FG"],
            "muted": _muted(colors),
            "warning": c["ACCENT_WARNING"],
            "success": c["ACCENT_SUCCESS"],
            "danger": c["ACCENT_EMERGENCY"],
            "onPrimary": c["ON_PRIMARY"],
        }
        hover = _hover(colors)
        muted = self._colors["muted"]
        # pylint: disable=line-too-long
        self.setStyleSheet(f"""
            #scRoot, #scContent {{ background: {c['BG']}; }}
            #scScroll {{ background: {c['BG']}; border: none; }}
            #scHeader {{ background: {c['CARD_BG']}; border-bottom: 1px solid {c['BORDER']}; }}
            #scFooter {{ background: {c['CARD_BG']}; border-top: 1px solid {c['BORDER']}; }}
            #scCard {{ background: {c['CARD_BG']}; border: 1px solid {c['BORDER']}; border-radius: 10px; }}
            #scCard QLabel, #scHeader QLabel, #scFooter QLabel {{ color: {c['FG']}; background: transparent; }}
            QLabel#scCardTitle {{ color: {muted}; font-size: 11px; font-weight: 700; letter-spacing: 0.8px; }}
            QLabel#scMuted {{ color: {muted}; font-size: 12px; }}
            QLabel#scMessage {{ font-size: 12px; }}
            QLabel#scBadge {{ color: {c['ACCENT_EMERGENCY']}; background: {rgba(c['ACCENT_EMERGENCY'], 46)};
                border-radius: 9px; padding: 1px 7px; font-size: 11px; font-weight: 600; }}
            #scField, QComboBox#scPicker {{ background: {c['FIELD_BG']}; color: {c['FG']};
                border: 1px solid {c['BORDER']}; border-radius: 6px; padding: 4px 8px; min-height: 22px; }}
            QComboBox#scPicker {{ font-size: 15px; font-weight: 600; min-height: 26px; }}
            #scField:focus, QComboBox#scPicker:focus {{ border: 1.5px solid {c['PRIMARY']}; }}
            #scField[invalid="true"], QComboBox#scPicker[invalid="true"] {{
                border: 1.5px solid {c['ACCENT_EMERGENCY']}; }}
            QComboBox#scField QLineEdit, QComboBox#scPicker QLineEdit {{ background: transparent; border: none; padding: 0; }}
            QComboBox#scField::drop-down, QComboBox#scPicker::drop-down {{ border: none; width: 20px; }}
            QToolButton#scIcon {{ border: none; border-radius: 6px; padding: 6px; background: transparent; }}
            QToolButton#scIcon:hover {{ background: {hover}; }}
            QPushButton#scGhost {{ background: transparent; color: {c['FG']}; border: none;
                border-radius: 7px; padding: 7px 12px; font-weight: 600; text-align: left; }}
            QPushButton#scGhost:hover {{ background: {hover}; }}
            QPushButton#scGhost:disabled {{ color: {muted}; }}
            QPushButton#scPrimary {{ background: {c['PRIMARY']}; color: {c['ON_PRIMARY']}; border: none;
                border-radius: 7px; padding: 7px 14px; font-weight: 600; }}
            QPushButton#scPrimary:hover {{ background: {colors['PRIMARY'].lighter(110).name()}; }}
            QPushButton#scPrimary:disabled {{ background: {rgba(c['PRIMARY'], 100)};
                color: {rgba(c['ON_PRIMARY'], 170)}; }}
            QPushButton#scStop {{ background: transparent; color: {c['ACCENT_EMERGENCY']};
                border: 1px solid {c['ACCENT_EMERGENCY']}; border-radius: 7px; padding: 7px 14px; font-weight: 600; }}
            QPushButton#scStop:hover {{ background: {hover}; }}
            QPushButton#scStop[armed="true"] {{ background: {c['ACCENT_EMERGENCY']}; color: {c['ON_PRIMARY']}; }}
            """)
        self._search_action.setIcon(_icon("search", muted))
        self.info_button.setIcon(_icon("info", c["FG"]))
        self.filter_button.setIcon(_icon("filter_list", c["FG"]))
        self.add_row_button.setIcon(_icon("add", c["FG"]))
        self.add_extra_button.setIcon(_icon("add", c["FG"]))
        self.restore_button.setIcon(_icon("history", c["FG"]))
        self.start_button.setIcon(_icon("play_arrow", c["ON_PRIMARY"], filled=True))
        self.meta_card.update_chevron()
        if hasattr(self, "arg_grid"):
            self._rebuild_form()
            self._rebuild_metadata()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    demo = ScanControlModern()
    demo.resize(520, 760)
    demo.show()
    sys.exit(app.exec())
