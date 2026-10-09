"""QWidget version of the redesigned curve settings dialog.

Layout: an X axis strip on top, the list of curves (with their fits nested below them) on the
left and an inspector for the selected curve on the right. Adding a curve is one step: "Add
curve" opens the device picker and the picked device is plotted with its first hinted signal.
All state lives in :class:`CurveDialogModel`; the QML version shows the same model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from bec_qthemes import material_icon
from qtpy.QtCore import QPointF, QRectF, QSize, Qt, Signal
from qtpy.QtGui import QColor, QFont, QIcon, QKeySequence, QLinearGradient, QPainter, QPen, QPixmap
from qtpy.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QColorDialog,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import Colors
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.quick.tokens import ThemeTokens
from bec_widgets.utils.settings_dialog import SettingWidget
from bec_widgets.utils.ux_kit import (
    Badge,
    Banner,
    Card,
    EmptyState,
    FormField,
    IconButton,
    SegmentedControl,
    TextButton,
    _ThemeFollower,
    field_qss,
    rgba,
)
from bec_widgets.widgets.control.device_input.picker.picker_qwidget import (
    DevicePicker,
    SignalPicker,
)
from bec_widgets.widgets.plots.waveform.settings.curve_dialog.curve_dialog_common import (
    open_picker_at,
    paint_curve_sample,
    paint_symbol,
    select_device,
    select_signal,
    signal_obj_name,
)
from bec_widgets.widgets.plots.waveform.settings.curve_dialog.curve_dialog_model import (
    PEN_STYLE_LABELS,
    PEN_STYLES,
    SWATCH_COUNT,
    SYMBOL_LABELS,
    SYMBOLS,
    X_MODE_HELP,
    X_MODE_LABELS,
    X_MODES,
    CurveDialogModel,
    color_hex,
)

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.widgets.plots.waveform.waveform import Waveform


def _font(widget: QWidget, px: int, weight: QFont.Weight | None = None) -> QFont:
    font = QFont(widget.font())
    font.setPixelSize(px)
    if weight is not None:
        font.setWeight(weight)
    return font


def _short_model(model: str) -> str:
    return model[:-5] if model.endswith("Model") and len(model) > 5 else model


def palette_icon(name: str, width: int = 64, height: int = 14) -> QIcon:
    """Small gradient preview of a colormap."""
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    gradient = QLinearGradient(0, 0, width, 0)
    colors = Colors.evenly_spaced_colors(colormap=name, num=8, format="HEX")
    for index, color in enumerate(colors):
        gradient.setColorAt(index / (len(colors) - 1), QColor(color))
    painter.setBrush(gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(0, 0, width, height), 3, 3)
    painter.end()
    return QIcon(pixmap)


class CurveRow(_ThemeFollower, QWidget):
    """One curve in the list: sample, name, source and status."""

    clicked = Signal(int)

    def __init__(self, row: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.row = row
        self._hover = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(48 if row["depth"] else 52)
        self.setAccessibleName(f"{row['title']}, {row['subtitle']}")
        self.setToolTip(row["error"] or "")
        self._follow_theme()

    def set_row(self, row: dict) -> None:
        """Show new display data."""
        self.row = row
        self.setToolTip(row["error"] or "")
        self.setAccessibleName(f"{row['title']}, {row['subtitle']}")
        self.update()

    def refresh_theme(self, _tokens: ThemeTokens) -> None:
        """Repaint with the new theme."""
        self.update()

    def enterEvent(self, event):  # pylint: disable=invalid-name
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # pylint: disable=invalid-name
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):  # pylint: disable=invalid-name
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.row["uid"])
        super().mousePressEvent(event)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        """Paint the control."""
        tokens = ThemeTokens.current()
        row = self.row
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(4, 2, -4, -2)
        if row["selected"]:
            painter.setPen(QPen(tokens.primary, 1.5))
            painter.setBrush(tokens.soft(tokens.primary, 0.14))
            painter.drawRoundedRect(rect, 8, 8)
        elif self._hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tokens.hover)
            painter.drawRoundedRect(rect, 8, 8)
        x = rect.left() + 10
        if row["depth"]:
            painter.setPen(QPen(tokens.separator, 1.5))
            mid = rect.center().y()
            painter.drawLine(QPointF(x + 6, rect.top() - 4), QPointF(x + 6, mid))
            painter.drawLine(QPointF(x + 6, mid), QPointF(x + 16, mid))
            x += 22
        sample = QRectF(x, rect.center().y() - 10, 40, 20)
        paint_curve_sample(
            painter,
            sample,
            row["color"],
            row["penStyle"],
            row["penWidth"],
            row["symbol"],
            row["symbolSize"],
            max_width=3,
            max_symbol=7,
            peak=row["kind"] != "custom",
        )
        x = sample.right() + 12
        right = rect.right() - 10
        # trailing status: error icon or tag
        if row["error"]:
            icon = material_icon(
                "error",
                size=(32, 32),
                color=tokens.danger_text,
                filled=True,
                convert_to_pixmap=True,
            )
            painter.drawPixmap(
                QRectF(right - 18, rect.center().y() - 9, 18, 18), icon, QRectF(icon.rect())
            )
            right -= 26
        tag = row["tag"]
        if tag == "history":
            tag = row["subtitle"].split("· ")[-1]
        if tag and tag != "fit":
            painter.setFont(_font(self, tokens.metrics["fontCaption"], QFont.Weight.DemiBold))
            width = painter.fontMetrics().horizontalAdvance(tag) + 14
            pill = QRectF(right - width, rect.center().y() - 10, width, 20)
            tone = "highlight" if row["tag"] == "custom" else "info"
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tokens.tone_tint(tone))
            painter.drawRoundedRect(pill, 10, 10)
            painter.setPen(tokens.tone_text(tone))
            painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, tag)
            right = pill.left() - 8
        title_font = _font(self, tokens.metrics["fontBody"], QFont.Weight.DemiBold)
        painter.setFont(title_font)
        painter.setPen(tokens.fg)
        width = max(10, right - x)
        title = painter.fontMetrics().elidedText(
            row["title"], Qt.TextElideMode.ElideRight, int(width)
        )
        painter.drawText(QRectF(x, rect.top() + 6, width, 20), Qt.AlignmentFlag.AlignVCenter, title)
        painter.setFont(_font(self, tokens.metrics["fontSmall"]))
        painter.setPen(tokens.danger_text if row["error"] else tokens.fg_muted)
        subtitle = row["error"] or row["subtitle"]
        subtitle = painter.fontMetrics().elidedText(
            subtitle, Qt.TextElideMode.ElideRight, int(width)
        )
        painter.drawText(
            QRectF(x, rect.bottom() - 24, width, 18), Qt.AlignmentFlag.AlignVCenter, subtitle
        )
        painter.end()


class CurveList(QScrollArea):
    """Scrollable list of :class:`CurveRow` with keyboard navigation."""

    selected = Signal(int)
    delete_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.container = QWidget()
        self.container.setObjectName("curveListContainer")
        self._layout = QVBoxLayout(self.container)
        self._layout.setContentsMargins(0, 2, 0, 2)
        self._layout.setSpacing(0)
        self._layout.addStretch(1)
        self.setWidget(self.container)
        self._rows: list[CurveRow] = []

    def set_rows(self, rows: list[dict]) -> None:
        """Show ``rows``; existing row widgets are reused."""
        while len(self._rows) > len(rows):
            widget = self._rows.pop()
            widget.setParent(None)
            widget.deleteLater()
        for index, row in enumerate(rows):
            if index < len(self._rows):
                self._rows[index].set_row(row)
                self._rows[index].setFixedHeight(48 if row["depth"] else 52)
            else:
                widget = CurveRow(row, self.container)
                widget.clicked.connect(self._on_clicked)
                self._layout.insertWidget(self._layout.count() - 1, widget)
                self._rows.append(widget)
        for widget in self._rows:
            if widget.row["selected"]:
                self.ensureWidgetVisible(widget, 0, 4)

    @property
    def rows(self) -> list[CurveRow]:
        """Row widgets in order."""
        return list(self._rows)

    def _on_clicked(self, uid: int) -> None:
        self.setFocus()
        self.selected.emit(uid)

    def _current_index(self) -> int:
        return next((i for i, w in enumerate(self._rows) if w.row["selected"]), -1)

    def keyPressEvent(self, event):  # pylint: disable=invalid-name
        index = self._current_index()
        if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up) and self._rows:
            step = 1 if event.key() == Qt.Key.Key_Down else -1
            target = max(0, min(len(self._rows) - 1, index + step))
            self.selected.emit(self._rows[target].row["uid"])
            return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and index >= 0:
            self.delete_requested.emit(self._rows[index].row["uid"])
            return
        super().keyPressEvent(event)


class SampleButton(_ThemeFollower, QAbstractButton):
    """Checkable tile showing a line style or a symbol."""

    def __init__(
        self,
        tip: str,
        pen_style: str = "solid",
        symbol: str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._pen_style = pen_style
        self._symbol = symbol
        self._color = QColor("#888888")
        self.setCheckable(True)
        self.setToolTip(tip)
        self.setAccessibleName(tip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(46 if symbol is None else 34, 30)
        self._follow_theme()

    def set_color(self, color: str) -> None:
        """Draw the sample in the curve colour."""
        self._color = QColor(color)
        self.update()

    def refresh_theme(self, _tokens: ThemeTokens) -> None:
        """Repaint with the new theme."""
        self.update()

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        """Paint the control."""
        tokens = ThemeTokens.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        border = tokens.primary if self.isChecked() else tokens.border
        if self.hasFocus():
            border = tokens.primary
        painter.setPen(QPen(border, 2 if self.isChecked() or self.hasFocus() else 1))
        painter.setBrush(tokens.soft(tokens.primary, 0.12) if self.isChecked() else tokens.field)
        painter.drawRoundedRect(rect, 6, 6)
        if self._symbol is None:
            pen = QPen(tokens.fg if not self.isChecked() else self._color, 2.2)
            pen.setStyle(
                {
                    "solid": Qt.PenStyle.SolidLine,
                    "dash": Qt.PenStyle.DashLine,
                    "dot": Qt.PenStyle.DotLine,
                    "dashdot": Qt.PenStyle.DashDotLine,
                }[self._pen_style]
            )
            painter.setPen(pen)
            painter.drawLine(
                QPointF(rect.left() + 8, rect.center().y()),
                QPointF(rect.right() - 8, rect.center().y()),
            )
        elif self._symbol == "":
            pen = QPen(tokens.fg_muted, 1.5)
            painter.setPen(pen)
            c = rect.center()
            painter.drawLine(QPointF(c.x() - 6, c.y() + 6), QPointF(c.x() + 6, c.y() - 6))
        else:
            color = self._color if self.isChecked() else tokens.fg
            painter.setPen(QPen(color, 1.2))
            painter.setBrush(color)
            paint_symbol(painter, rect.center(), self._symbol, 11)
        painter.end()


class SwatchButton(_ThemeFollower, QAbstractButton):
    """Round colour swatch; checked when it is the curve colour."""

    def __init__(self, color: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.color = color
        self.setCheckable(True)
        self.setFixedSize(26, 26)
        self.setToolTip(color)
        self.setAccessibleName(f"Colour {color}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._follow_theme()

    def refresh_theme(self, _tokens: ThemeTokens) -> None:
        """Repaint with the new theme."""
        self.update()

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        """Paint the control."""
        tokens = ThemeTokens.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        if self.isChecked() or self.hasFocus():
            painter.setPen(QPen(tokens.fg if self.isChecked() else tokens.primary, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect.adjusted(1, 1, -1, -1))
        painter.setPen(QPen(QColor(0, 0, 0, 40), 1))
        painter.setBrush(QColor(self.color))
        painter.drawEllipse(rect.adjusted(5, 5, -5, -5))
        painter.end()


class SamplePreview(QWidget):
    """Large sample of the selected curve, shown in the inspector header."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.row: dict | None = None
        self.setFixedSize(84, 44)

    def set_row(self, row: dict) -> None:
        """Show ``row``'s colour and style."""
        self.row = row
        self.update()

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        """Paint the control."""
        if self.row is None:
            return
        tokens = ThemeTokens.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(tokens.border, 1))
        painter.setBrush(tokens.field)
        painter.drawRoundedRect(rect, 8, 8)
        row = self.row
        paint_curve_sample(
            painter,
            rect.adjusted(8, 7, -8, -7),
            row["color"],
            row["penStyle"],
            row["penWidth"],
            row["symbol"],
            row["symbolSize"],
            max_width=6,
            max_symbol=12,
            peak=row["kind"] != "custom",
        )
        painter.end()


class ValueSlider(QWidget):
    """Slider with its value shown next to it."""

    value_changed = Signal(int)

    def __init__(self, minimum: int, maximum: int, value: int, unit: str, tip: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(value)
        self.slider.setAccessibleName(tip)
        self.slider.setToolTip(tip)
        self.label = QLabel(f"{value} {unit}", self)
        self.label.setObjectName("sliderValue")
        self.label.setMinimumWidth(38)
        self._unit = unit
        self.slider.valueChanged.connect(self._on_value)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.label)

    def _on_value(self, value: int) -> None:
        self.label.setText(f"{value} {self._unit}")
        self.value_changed.emit(value)


class CurveSettingsQWidget(_ThemeFollower, SettingWidget):
    """Curve settings of a :class:`Waveform`: X axis, curves, fits and their look.

    Args:
        parent(QWidget | None): Parent widget.
        target_widget(Waveform): The waveform to edit.
    """

    def __init__(self, parent=None, target_widget: Waveform | None = None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.setProperty("skip_settings", True)
        self.setObjectName("curveSettings")
        self.target_widget = target_widget
        self.model = CurveDialogModel(target_widget, parent=self)
        self._inspector_refreshers: list[Callable[[], None]] = []
        self._inspector_uid: int | None = -1
        self._cleaned = False
        self.scan_combo: QComboBox | None = None

        # pickers of the curve inspector and of "Add curve" (whose combobox stays hidden)
        self.device_picker = DevicePicker(parent=self, client=self.model.client)
        self.device_picker.setEditable(True)
        self.device_picker.picker_controller.picked.connect(self._on_device_picked)
        self.signal_picker = SignalPicker(parent=self, client=self.model.client)
        self.signal_picker.include_config_signals = False
        self.signal_picker.setEditable(True)
        self.signal_picker.picker_controller.picked.connect(self._on_signal_picked)
        self.add_picker = DevicePicker(parent=self, client=self.model.client)
        self.add_picker.setEditable(True)
        self.add_picker.hide()
        self.add_picker.picker_controller.picked.connect(self._on_add_picked)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(10)
        root.addWidget(self._build_x_axis())
        body = QHBoxLayout()
        body.setSpacing(10)
        body.addWidget(self._build_list(), 0)
        body.addWidget(self._build_inspector(), 1)
        root.addLayout(body, 1)

        self.model.rows_changed.connect(self._refresh_list)
        self.model.selection_changed.connect(self._rebuild_inspector)
        self.model.draft_changed.connect(self._on_draft_changed)
        self.model.x_axis_changed.connect(self._refresh_x_axis)
        self.model.palette_changed.connect(self._refresh_palette)

        QShortcut(QKeySequence.StandardKey.New, self, activated=self.open_add_picker)

        self.refresh_theme(ThemeTokens.current())
        self._refresh_x_axis()
        self._refresh_palette()
        self._refresh_list()
        self._rebuild_inspector()
        self._follow_theme()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Default size of the dialog content."""
        return QSize(940, 600)

    # ---- X axis ------------------------------------------------------------------------------

    def _build_x_axis(self) -> QWidget:
        self.x_card = Card("X axis", title_style="caption", padding=12)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.x_mode_control = SegmentedControl([X_MODE_LABELS[m] for m in X_MODES])
        self.x_mode_control.setAccessibleName("X axis mode")
        self.x_mode_control.activated.connect(lambda i: self.model.set_x_mode(X_MODES[i]))
        row.addWidget(self.x_mode_control)
        self.x_device_picker = DevicePicker(parent=self.x_card, client=self.model.client)
        self.x_device_picker.setEditable(True)
        self.x_device_picker.setMinimumWidth(170)
        self.x_device_picker.picker_controller.picked.connect(self.model.set_x_device)
        self.x_signal_picker = SignalPicker(parent=self.x_card, client=self.model.client)
        self.x_signal_picker.include_config_signals = False
        self.x_signal_picker.setEditable(True)
        self.x_signal_picker.setMinimumWidth(170)
        self.x_signal_picker.picker_controller.picked.connect(
            lambda text: self.model.set_x_signal(signal_obj_name(self.x_signal_picker, text))
        )
        row.addWidget(self.x_device_picker, 1)
        row.addWidget(self.x_signal_picker, 1)
        self.x_help = QLabel(self.x_card)
        self.x_help.setObjectName("helper")
        self.x_help.setWordWrap(True)
        row.addWidget(self.x_help, 2)
        self.x_card.body.addLayout(row)
        return self.x_card

    def _refresh_x_axis(self) -> None:
        mode = self.model.x_mode
        self.x_mode_control.set_current_index(X_MODES.index(mode))
        device_mode = mode == "device"
        self.x_device_picker.setVisible(device_mode)
        self.x_signal_picker.setVisible(device_mode)
        error = self.model.x_axis_error()
        self.x_help.setText(error or X_MODE_HELP[mode])
        self.x_help.setProperty("error", bool(error))
        self.x_help.style().unpolish(self.x_help)
        self.x_help.style().polish(self.x_help)
        if device_mode:
            select_device(self.x_device_picker, self.model.x_device)
            select_signal(self.x_signal_picker, self.model.x_device, self.model.x_signal)
        self._refresh_problems()

    # ---- curve list --------------------------------------------------------------------------

    def _build_list(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setFixedWidth(330)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        header = QHBoxLayout()
        header.setSpacing(6)
        title = QLabel("Curves", panel)
        title.setObjectName("panelTitle")
        self.count_badge = Badge(count=0, tone="neutral", parent=panel)
        header.addWidget(title)
        header.addWidget(self.count_badge)
        header.addStretch(1)
        self.palette_combo = QComboBox(panel)
        self.palette_combo.setToolTip(
            "Palette for curve colours. Choosing one recolours every curve."
        )
        self.palette_combo.setAccessibleName("Colour palette")
        self.palette_combo.setIconSize(QSize(44, 12))
        self.palette_combo.activated.connect(
            lambda i: self.model.set_palette(self.palette_combo.itemText(i))
        )
        header.addWidget(self.palette_combo)
        self.recolor_button = IconButton(
            "format_color_fill", "Recolour all curves from the palette", panel, compact=True
        )
        # clicked passes `checked`, which recolor_all would take as `emit`
        self.recolor_button.clicked.connect(
            lambda: self.model.recolor_all()
        )  # pylint: disable=unnecessary-lambda
        header.addWidget(self.recolor_button)
        layout.addLayout(header)
        self.add_button = TextButton("Add curve", "primary", "add", panel)
        self.add_button.setToolTip("Pick a device to plot (Ctrl+N)")
        self.add_button.clicked.connect(self.open_add_picker)
        layout.addWidget(self.add_button)
        self.curve_list = CurveList(panel)
        self.curve_list.selected.connect(self.model.select)
        self.curve_list.delete_requested.connect(self.model.remove)
        layout.addWidget(self.curve_list, 1)
        self.problem_banner = Banner("warning", "", "", panel)
        self.problem_banner.hide()
        layout.addWidget(self.problem_banner)
        return panel

    def _refresh_palette(self) -> None:
        self.palette_combo.blockSignals(True)
        self.palette_combo.clear()
        for name in self.model.palettes():
            self.palette_combo.addItem(palette_icon(name), name)
        self.palette_combo.setCurrentText(self.model.palette)
        self.palette_combo.blockSignals(False)

    def _refresh_list(self) -> None:
        rows = self.model.rows()
        self.curve_list.set_rows(rows)
        self.count_badge.set_count(sum(1 for r in rows if r["depth"] == 0))
        self._refresh_problems()

    def _refresh_problems(self) -> None:
        problems = self.model.problems()
        if not problems:
            self.problem_banner.hide()
            return
        title = (
            "1 problem to fix before applying"
            if len(problems) == 1
            else f"{len(problems)} problems to fix before applying"
        )
        self.problem_banner.set_message(title, "\n".join(problems[:3]))
        self.problem_banner.show()

    @SafeSlot()
    def open_add_picker(self) -> None:
        """Open the device picker under "Add curve"; picking a device adds its curve."""
        open_picker_at(self.add_picker, self.add_button)

    @SafeSlot(str)
    def _on_add_picked(self, device: str) -> None:
        self.model.add_curve(device)

    # ---- inspector ---------------------------------------------------------------------------
    # One page per kind of curve is built once; selecting a curve only re-binds the values.
    # Building widgets under the dialog's style sheet costs ~25 ms per page, re-binding ~2 ms.

    def _build_inspector(self) -> QWidget:
        self.inspector_scroll = QScrollArea()
        self.inspector_scroll.setObjectName("inspector")
        self.inspector_scroll.setWidgetResizable(True)
        self.inspector_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.inspector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.inspector_stack = QStackedWidget()
        self.inspector_stack.setObjectName("inspectorPage")
        self.inspector_scroll.setWidget(self.inspector_stack)
        self._pages: dict[str, tuple[QWidget, list[Callable[[], None]]]] = {}
        return self.inspector_scroll

    def _page(self, kind: str) -> tuple[QWidget, list[Callable[[], None]]]:
        if kind in self._pages:
            return self._pages[kind]
        page = QWidget()
        page.setObjectName("inspectorPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(10)
        refreshers: list[Callable[[], None]] = []
        if kind == "empty":
            empty = EmptyState(
                "show_chart",
                "No curves yet",
                "Add a device to plot it against the X axis. Fits and colours are set per curve.",
                page,
                action_text="Add curve",
                action_icon="add",
            )
            empty.action_triggered.connect(self.open_add_picker)
            layout.addStretch(1)
            layout.addWidget(empty, 0, Qt.AlignmentFlag.AlignCenter)
            layout.addStretch(2)
        else:
            layout.addWidget(self._header(kind, refreshers))
            if kind == "device":
                layout.addWidget(self._data_card(refreshers))
                layout.addWidget(self._fits_card(refreshers))
            elif kind == "dap":
                layout.addWidget(self._fit_card(refreshers))
            else:
                layout.addWidget(
                    Banner(
                        "info",
                        "Curve sent from the command line",
                        "Its data came from plot(x=..., y=...), so only its look can be changed "
                        "here. Remove it from the command line.",
                        page,
                    )
                )
                layout.addWidget(self._fits_card(refreshers))
            layout.addWidget(self._style_card(refreshers))
            layout.addStretch(1)
        self.inspector_stack.addWidget(page)
        self._pages[kind] = (page, refreshers)
        return self._pages[kind]

    def _rebuild_inspector(self) -> None:
        draft = self.model.selected
        self._inspector_uid = draft.uid if draft else None
        page, refreshers = self._page(draft.kind if draft else "empty")
        self._inspector_refreshers = refreshers
        for refresh in refreshers:
            refresh()
        self.inspector_stack.setCurrentWidget(page)
        self.inspector_scroll.verticalScrollBar().setValue(0)

    def _on_draft_changed(self, uid: int) -> None:
        if uid == self._inspector_uid:
            for refresh in self._inspector_refreshers:
                refresh()

    def _uid(self) -> int:
        return self.model.selected_uid if self.model.selected_uid is not None else -1

    def _caption(self, text: str, parent: QWidget) -> QLabel:
        label = QLabel(text, parent)
        label.setObjectName("rowLabel")
        return label

    def _header(self, kind: str, refreshers: list) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(12)
        preview = SamplePreview(box)
        layout.addWidget(preview)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        title = QLabel(box)
        title.setObjectName("inspectorTitle")
        subtitle = QLabel(box)
        subtitle.setObjectName("helper")
        texts.addWidget(title)
        texts.addWidget(subtitle)
        layout.addLayout(texts, 1)
        if kind != "dap":
            add_fit = TextButton("Add fit", "neutral", "add", box, compact=True)
            add_fit.setToolTip("Fit a model to this curve")
            add_fit.clicked.connect(lambda: self.model.add_fit(self._uid()))
            layout.addWidget(add_fit)
        if kind != "custom":
            remove = IconButton(
                "delete",
                "Remove fit" if kind == "dap" else "Remove curve and its fits",
                box,
                danger=True,
            )
            remove.clicked.connect(lambda: self.model.remove(self._uid()))
            layout.addWidget(remove)

        def refresh():
            row = self.model.row(self.model.selected)
            preview.set_row(row)
            title.setText(row["title"])
            subtitle.setText(row["subtitle"])

        refreshers.append(refresh)
        return box

    def _data_card(self, refreshers: list) -> QWidget:
        card = Card("Data", title_style="caption", padding=12)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        self.device_picker.setParent(card)
        self.signal_picker.setParent(card)
        device_field = FormField("Device", self.device_picker, card, required=True)
        signal_field = FormField("Signal", self.signal_picker, card, required=True)
        self.device_picker.show()
        self.signal_picker.show()
        scan_combo = QComboBox(card)
        scan_combo.setAccessibleName("Data from")
        scan_combo.activated.connect(
            lambda i: self.model.set_scan(self._uid(), scan_combo.itemData(i))
        )
        scan_field = FormField(
            "Data from",
            scan_combo,
            card,
            helper="Live follows the running scan; an earlier scan shows its stored data.",
        )
        grid.addWidget(device_field, 0, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(signal_field, 0, 1, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(scan_field, 1, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        card.body.addLayout(grid)
        self.scan_combo = scan_combo

        def refresh():
            draft = self.model.selected
            select_device(self.device_picker, draft.device)
            select_signal(self.signal_picker, draft.device, draft.signal)
            scan_combo.blockSignals(True)
            scan_combo.clear()
            for text, scan_id in self.model.scans():
                scan_combo.addItem(text, scan_id)
            index = scan_combo.findData(draft.config.scan_id) if draft.config.scan_id else 0
            if index < 0:
                scan_combo.addItem(
                    f"Scan #{draft.config.scan_number} (missing)", draft.config.scan_id
                )
                index = scan_combo.count() - 1
            scan_combo.setCurrentIndex(index)
            scan_combo.blockSignals(False)
            error = self.model.validate().get(draft.uid, "")
            device_field.set_error(error if "evice" in error else "")
            signal_field.set_error(error if "ignal" in error else "")
            scan_field.set_error(error if "scan" in error else "")

        refreshers.append(refresh)
        return card

    def _fits_card(self, refreshers: list) -> QWidget:
        card = Card("Fits", title_style="caption", padding=12)
        none_label = QLabel(
            "No fits. Add one to fit a model such as a Gaussian to this curve.", card
        )
        none_label.setObjectName("helper")
        none_label.setWordWrap(True)
        card.body.addWidget(none_label)
        holder = QWidget(card)
        rows = QVBoxLayout(holder)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(2)
        card.body.addWidget(holder)
        buttons: list[TextButton] = []

        def refresh():
            fits = self.model.children(self._uid())
            none_label.setVisible(not fits)
            while len(buttons) < len(fits):
                button = TextButton("", "ghost", "", holder, compact=True)
                button.setIconSize(QSize(32, 14))
                button.setToolTip("Edit this fit")
                button.clicked.connect(
                    lambda _=False, b=button: self.model.select(b.property("uid"))
                )
                rows.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)
                buttons.append(button)
            for index, button in enumerate(buttons):
                button.setVisible(index < len(fits))
                if index < len(fits):
                    row = self.model.row(fits[index])
                    button.setText(row["title"])
                    button.setIcon(self._sample_icon(row))
                    button.setProperty("uid", fits[index].uid)

        refreshers.append(refresh)
        return card

    def _sample_icon(self, row: dict) -> QIcon:
        pixmap = QPixmap(64, 28)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        paint_curve_sample(painter, QRectF(0, 0, 64, 28), row["color"], row["penStyle"], 4, "", 1)
        painter.end()
        return QIcon(pixmap)

    def _fit_card(self, refreshers: list) -> QWidget:
        card = Card("Fit", title_style="caption", padding=12)
        model_combo = QComboBox(card)
        model_combo.setAccessibleName("Fit model")
        model_combo.textActivated.connect(
            lambda text: self.model.set_primary_model(self._uid(), text)
        )
        model_field = FormField("Model", model_combo, card, required=True)
        card.body.addWidget(model_field)
        card.body.addWidget(self._caption("Combine with", card))
        chips = QWidget(card)
        flow = QGridLayout(chips)
        flow.setContentsMargins(0, 0, 0, 0)
        flow.setHorizontalSpacing(6)
        flow.setVerticalSpacing(6)
        flow.setColumnStretch(4, 1)
        card.body.addWidget(chips)
        chip_buttons: dict[str, QPushButton] = {}
        helper = QLabel(card)
        helper.setObjectName("helper")
        helper.setWordWrap(True)
        card.body.addWidget(helper)
        go = TextButton("", "ghost", "arrow_back", card, compact=True)
        go.setToolTip("Select the fitted curve")
        go.clicked.connect(lambda: self.model.select(self.model.selected.parent_uid))
        line = QHBoxLayout()
        line.addWidget(go)
        line.addStretch(1)
        card.body.addLayout(line)

        def refresh():
            draft = self.model.selected
            available = self.model.available_models() or list(draft.models)
            if draft.models[0] not in available:
                available = [draft.models[0]] + available
            model_combo.blockSignals(True)
            if [model_combo.itemText(i) for i in range(model_combo.count())] != available:
                model_combo.clear()
                model_combo.addItems(available)
            model_combo.setCurrentText(draft.models[0])
            model_combo.blockSignals(False)
            for model in available:
                if model in chip_buttons:
                    continue
                chip = QPushButton(_short_model(model), chips)
                chip.setObjectName("chip")
                chip.setCheckable(True)
                chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                chip.setCursor(Qt.CursorShape.PointingHandCursor)
                chip.setToolTip(f"Add {model} to a composite fit")
                chip.setAccessibleName(f"Add {model} to a composite fit")
                chip.clicked.connect(
                    lambda _=False, m=model: self.model.toggle_extra_model(self._uid(), m)
                )
                chip_buttons[model] = chip
            others = [m for m in available if m != draft.models[0]]
            for model, chip in chip_buttons.items():
                flow.removeWidget(chip)
                chip.setVisible(model in others)
                chip.setChecked(model in draft.models[1:])
            for index, model in enumerate(others):
                flow.addWidget(chip_buttons[model], index // 4, index % 4)
            if len(draft.models) > 1:
                helper.setText(f"Composite fit: the sum of {' + '.join(draft.models)}.")
            else:
                helper.setText("Select more models to fit their sum (a composite fit).")
            model_field.set_error(self.model.validate().get(draft.uid, ""))
            parent = self.model.draft(draft.parent_uid)
            go.setVisible(parent is not None)
            if parent is not None:
                go.setText(f"Fits {self.model.row(parent)['title']}")

        refreshers.append(refresh)
        return card

    def _style_card(self, refreshers: list) -> QWidget:
        card = Card("Appearance", title_style="caption", padding=12)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)

        # colour
        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(2)
        swatches: list[SwatchButton] = []
        swatch_group = QButtonGroup(card)
        for _ in range(SWATCH_COUNT):
            swatch = SwatchButton("#888888", card)
            swatch.clicked.connect(
                lambda _=False, s=swatch: self.model.set_style(self._uid(), "color", s.color)
            )
            swatch_row.addWidget(swatch)
            swatch_group.addButton(swatch)
            swatches.append(swatch)
        custom = TextButton("Custom…", "ghost", "colorize", card, compact=True)
        custom.setToolTip("Pick any colour")
        custom.clicked.connect(lambda: self._pick_custom_color(self._uid()))
        swatch_row.addSpacing(6)
        swatch_row.addWidget(custom)
        swatch_row.addStretch(1)
        grid.addWidget(self._caption("Colour", card), 0, 0)
        grid.addLayout(swatch_row, 0, 1)

        # line style and width
        line_row = QHBoxLayout()
        line_row.setSpacing(4)
        line_buttons = {}
        line_group = QButtonGroup(card)
        for style in PEN_STYLES:
            button = SampleButton(f"{PEN_STYLE_LABELS[style]} line", pen_style=style, parent=card)
            button.clicked.connect(
                lambda _=False, s=style: self.model.set_style(self._uid(), "pen_style", s)
            )
            line_row.addWidget(button)
            line_group.addButton(button)
            line_buttons[style] = button
        line_row.addSpacing(14)
        width = ValueSlider(1, 10, 1, "px", "Line width", card)
        width.value_changed.connect(lambda v: self.model.set_style(self._uid(), "pen_width", v))
        line_row.addWidget(width, 1)
        grid.addWidget(self._caption("Line", card), 1, 0)
        grid.addLayout(line_row, 1, 1)

        # symbol and size
        symbol_row = QHBoxLayout()
        symbol_row.setSpacing(4)
        symbol_buttons = {}
        symbol_group = QButtonGroup(card)
        for symbol in SYMBOLS:
            button = SampleButton(SYMBOL_LABELS[symbol], symbol=symbol, parent=card)
            button.clicked.connect(
                lambda _=False, s=symbol: self.model.set_style(self._uid(), "symbol", s)
            )
            symbol_row.addWidget(button)
            symbol_group.addButton(button)
            symbol_buttons[symbol] = button
        symbol_row.addSpacing(14)
        size = ValueSlider(1, 20, 1, "px", "Symbol size", card)
        size.value_changed.connect(lambda v: self.model.set_style(self._uid(), "symbol_size", v))
        symbol_row.addWidget(size, 1)
        grid.addWidget(self._caption("Symbol", card), 2, 0)
        grid.addLayout(symbol_row, 2, 1)
        grid.setColumnStretch(1, 1)
        card.body.addLayout(grid)

        def refresh():
            config = self.model.selected.config
            color = color_hex(config.color)
            swatch_group.setExclusive(False)
            for swatch, swatch_color in zip(swatches, self.model.swatches(color)):
                swatch.color = swatch_color
                swatch.setToolTip(swatch_color)
                swatch.setAccessibleName(f"Colour {swatch_color}")
                swatch.setChecked(swatch_color.lower() == color.lower())
                swatch.update()
            swatch_group.setExclusive(True)
            for style, button in line_buttons.items():
                button.set_color(color)
                button.setChecked(style == (config.pen_style or "solid"))
            for symbol, button in symbol_buttons.items():
                button.set_color(color)
                button.setChecked(symbol == (config.symbol or ""))
            for slider, value, top in (
                (width, int(config.pen_width or 1), 10),
                (size, int(config.symbol_size or 1), 20),
            ):
                slider.slider.blockSignals(True)
                slider.slider.setMaximum(max(top, value))
                slider.slider.setValue(value)
                slider.slider.blockSignals(False)
                slider.label.setText(f"{value} px")
            size.setEnabled(bool(config.symbol))

        refreshers.append(refresh)
        return card

    @SafeSlot(int)
    def _pick_custom_color(self, uid: int) -> None:
        draft = self.model.draft(uid)
        if draft is None:
            return
        color = QColorDialog.getColor(QColor(color_hex(draft.config.color)), self, "Curve colour")
        if color.isValid():
            self.model.set_style(uid, "color", color.name())

    # ---- picker callbacks --------------------------------------------------------------------

    @SafeSlot(str)
    def _on_device_picked(self, device: str) -> None:
        uid = self._inspector_uid
        if uid is None:
            return
        self.model.set_device(uid, device)
        draft = self.model.draft(uid)
        if draft is not None:
            select_signal(self.signal_picker, draft.device, draft.signal)

    @SafeSlot(str)
    def _on_signal_picked(self, text: str) -> None:
        uid = self._inspector_uid
        if uid is None:
            return
        self.model.set_signal(uid, signal_obj_name(self.signal_picker, text))

    # ---- theme -------------------------------------------------------------------------------

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens to the parts that are not kit controls."""
        small = tokens.metrics["fontSmall"]
        self.setStyleSheet(field_qss(tokens) + f"""
            QWidget#curveSettings {{ background: {tokens.bg.name()}; }}
            QFrame#panel {{ background: {tokens.card.name()}; border: 1px solid {tokens.border.name()};
                border-radius: {tokens.metrics["radiusLarge"]}px; }}
            QWidget#curveListContainer, QWidget#inspectorPage {{ background: transparent; }}
            QScrollArea {{ background: transparent; border: none; }}
            QScrollArea > QWidget > QWidget {{ background: transparent; }}
            QLabel {{ background: transparent; color: {tokens.fg.name()}; }}
            QLabel#panelTitle {{ font-size: {tokens.metrics["fontTitle"]}px; font-weight: 600; }}
            QLabel#inspectorTitle {{ font-size: {tokens.metrics["fontTitle"]}px; font-weight: 600; }}
            QLabel#helper {{ color: {tokens.fg_muted.name()}; font-size: {small}px; }}
            QLabel#helper[error="true"] {{ color: {tokens.danger_text.name()}; }}
            QLabel#rowLabel {{ color: {tokens.fg_muted.name()}; font-size: {small}px; font-weight: 500; }}
            QLabel#sliderValue {{ color: {tokens.fg_muted.name()}; font-size: {small}px; }}
            QPushButton#chip {{ background: {tokens.field.name()}; color: {tokens.fg.name()};
                border: 1px solid {tokens.border.name()}; border-radius: 13px; padding: 3px 12px;
                font-size: {small}px; min-height: 18px; }}
            QPushButton#chip:hover {{ border-color: {tokens.fg_subtle.name()}; }}
            QPushButton#chip:checked {{ background: {rgba(tokens.primary, 0.16)};
                border-color: {tokens.primary.name()}; color: {tokens.fg.name()}; font-weight: 600; }}
            QPushButton#chip:disabled {{ color: {tokens.fg_subtle.name()}; border-style: dashed; }}
            QSlider::groove:horizontal {{ height: 4px; background: {tokens.track.name()}; border-radius: 2px; }}
            QSlider::sub-page:horizontal {{ background: {tokens.primary.name()}; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: {tokens.card.name()}; border: 2px solid {tokens.primary.name()};
                width: 12px; height: 12px; margin: -6px 0; border-radius: 8px; }}
            QSlider::handle:horizontal:disabled {{ border-color: {tokens.fg_subtle.name()}; }}
            QSlider::sub-page:horizontal:disabled {{ background: {tokens.fg_subtle.name()}; }}
            """)
        if hasattr(self, "curve_list"):
            self.curve_list.viewport().update()

    # ---- SettingWidget API -------------------------------------------------------------------

    @SafeSlot(popup_error=True)
    def accept_changes(self):
        """Apply the staged curves, X axis and palette to the waveform."""
        self.model.apply()

    @SafeSlot()
    def refresh(self):
        """Reload from the waveform, e.g. after it was changed over RPC."""
        self.model.load_from_waveform()

    def cleanup(self):
        """Close the pickers and their popups."""
        if self._cleaned:
            return
        self._cleaned = True
        for picker in (
            self.device_picker,
            self.signal_picker,
            self.add_picker,
            self.x_device_picker,
            self.x_signal_picker,
        ):
            picker.close()
            picker.deleteLater()
