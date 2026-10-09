"""Helpers shared by the QWidget and QML curve dialogs: picker anchoring, curve samples and the
choice between the dialog versions."""

from __future__ import annotations

import math
import os
from typing import TYPE_CHECKING

from qtpy.QtCore import QPointF, QRectF, Qt
from qtpy.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from qtpy.QtWidgets import QWidget

from bec_widgets.widgets.control.device_input.picker.picker_model import recent_picks

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.widgets.control.device_input.picker.picker_common import PickerPopupMixin
    from bec_widgets.widgets.plots.waveform.waveform import Waveform

ENV_VAR = "BEC_CURVE_DIALOG"
PEN_STYLE_MAP = {
    "solid": Qt.PenStyle.SolidLine,
    "dash": Qt.PenStyle.DashLine,
    "dot": Qt.PenStyle.DotLine,
    "dashdot": Qt.PenStyle.DashDotLine,
}


def open_picker_at(picker: PickerPopupMixin, anchor: QWidget, query: str = "") -> None:
    """Open the searchable popup of ``picker`` under ``anchor`` instead of under the picker.

    Lets a button (or a field drawn by QML) open a device or signal picker whose combobox is
    hidden; the pick arrives through ``picker.picker_controller.picked``.
    """
    # pylint: disable=protected-access
    picker._picker_text_before = picker.currentText()
    picker.picker_controller.open(
        picker._picker_entries(), picker.currentText(), query, recent_picks(picker.RECENT_KIND)
    )
    picker.picker_popup.show_below(anchor)


def signal_obj_name(picker, text: str) -> str:
    """Object name of the signal shown as ``text`` in a signal picker."""
    index = picker.findText(text)
    if index >= 0:
        data = picker.itemData(index)
        if isinstance(data, dict) and data.get("obj_name"):
            return data["obj_name"]
    return text


def select_signal(picker, device: str, signal: str) -> None:
    """Show ``signal`` (object name) of ``device`` in a signal picker without emitting."""
    picker.blockSignals(True)
    try:
        picker.set_device(device or None)
        if not signal or not picker.set_to_obj_name(signal):
            picker.setCurrentText(signal or "")
    finally:
        picker.blockSignals(False)


def select_device(picker, device: str) -> None:
    """Show ``device`` in a device picker without emitting."""
    picker.blockSignals(True)
    try:
        index = picker.findText(device or "")
        if index >= 0:
            picker.setCurrentIndex(index)
        else:
            picker.setCurrentText(device or "")
    finally:
        picker.blockSignals(False)


def paint_symbol(painter: QPainter, center: QPointF, symbol: str, size: float) -> None:
    """Draw a pyqtgraph-style symbol with the painter's current pen and brush."""
    half = size / 2
    x, y = center.x(), center.y()
    if symbol == "o":
        painter.drawEllipse(center, half, half)
    elif symbol == "s":
        painter.drawRect(QRectF(x - half, y - half, size, size))
    elif symbol == "t":
        painter.drawPolygon(
            QPolygonF(
                [QPointF(x - half, y - half), QPointF(x + half, y - half), QPointF(x, y + half)]
            )
        )
    elif symbol == "d":
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(x, y - half),
                    QPointF(x + half, y),
                    QPointF(x, y + half),
                    QPointF(x - half, y),
                ]
            )
        )
    elif symbol == "star":
        points = []
        for i in range(10):
            radius = half if i % 2 == 0 else half * 0.45
            angle = -math.pi / 2 + i * math.pi / 5
            points.append(QPointF(x + radius * math.cos(angle), y + radius * math.sin(angle)))
        painter.drawPolygon(QPolygonF(points))
    elif symbol in ("+", "x"):
        pen = QPen(painter.pen())
        pen.setColor(painter.brush().color())
        pen.setWidthF(max(1.5, size / 4))
        painter.save()
        painter.setPen(pen)
        if symbol == "+":
            painter.drawLine(QPointF(x - half, y), QPointF(x + half, y))
            painter.drawLine(QPointF(x, y - half), QPointF(x, y + half))
        else:
            painter.drawLine(QPointF(x - half, y - half), QPointF(x + half, y + half))
            painter.drawLine(QPointF(x - half, y + half), QPointF(x + half, y - half))
        painter.restore()


def paint_curve_sample(
    painter: QPainter,
    rect: QRectF,
    color: str | QColor,
    pen_style: str = "solid",
    pen_width: float = 2,
    symbol: str = "",
    symbol_size: float = 6,
    max_width: float = 4,
    max_symbol: float = 9,
    peak: bool = True,
) -> None:
    """Draw a small sample of a curve: a peak (or a flat line) with symbols on three points."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(color)
    pen = QPen(color, min(max(1.0, float(pen_width)), max_width))
    pen.setStyle(PEN_STYLE_MAP.get(pen_style, Qt.PenStyle.SolidLine))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    margin = min(max_symbol, symbol_size) / 2 + 1 if symbol else 2
    left, right = rect.left() + margin, rect.right() - margin
    top, bottom = rect.top() + margin, rect.bottom() - margin
    path = QPainterPath()
    steps = 40
    points = []
    for i in range(steps + 1):
        t = i / steps
        x = left + t * (right - left)
        h = math.exp(-((t - 0.5) ** 2) / 0.03) if peak else 0.5
        y = bottom - h * (bottom - top)
        points.append(QPointF(x, y))
    path.moveTo(points[0])
    for point in points[1:]:
        path.lineTo(point)
    painter.drawPath(path)
    if symbol:
        painter.setPen(QPen(color.darker(130), 1))
        painter.setBrush(color)
        size = min(max(3.0, float(symbol_size)), max_symbol)
        for index in (steps // 5, steps // 2, steps - steps // 5):
            paint_symbol(painter, points[index], symbol, size)
    painter.restore()


def curve_dialog_variant() -> str:
    """Which curve dialog the waveform opens: ``legacy`` (default), ``qwidget`` or ``qml``."""
    value = os.environ.get(ENV_VAR, "").strip().lower()
    return value if value in ("qwidget", "qml") else "legacy"


def create_curve_setting(waveform: Waveform, variant: str | None = None):
    """Create the curve settings widget chosen by ``BEC_CURVE_DIALOG`` (or ``variant``)."""
    variant = variant or curve_dialog_variant()
    if variant == "qwidget":
        from bec_widgets.widgets.plots.waveform.settings.curve_dialog.curve_dialog_qwidget import (
            CurveSettingsQWidget,
        )

        return CurveSettingsQWidget(parent=waveform, target_widget=waveform)
    if variant == "qml":
        from bec_widgets.widgets.plots.waveform.settings.curve_dialog.curve_dialog_qml import (
            CurveSettingsQml,
        )

        return CurveSettingsQml(parent=waveform, target_widget=waveform)
    from bec_widgets.widgets.plots.waveform.settings.curve_settings.curve_setting import (
        CurveSetting,
    )

    return CurveSetting(parent=waveform, target_widget=waveform)
