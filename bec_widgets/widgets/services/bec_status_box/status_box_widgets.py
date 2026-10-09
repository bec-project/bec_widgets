"""QWidget view of the BEC status box.

It shows the same content and interactions as the QML view (``qml/StatusBox.qml``): an overall state
header and grouped, expandable service rows. Rows are kept and updated in place when the model
changes, instead of being rebuilt.
"""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QSize, Qt, QTimer, Signal
from qtpy.QtGui import QColor, QPainter, QTransform
from qtpy.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import get_theme_name, rgba
from bec_widgets.widgets.services.bec_status_box.status_model import ServiceRow, ServiceStatusModel

_FALLBACK = {
    "BG": "#1e1f22",
    "CARD_BG": "#2b2c2f",
    "FG": "#dddddd",
    "BORDER": "#464749",
    "DISABLED_FG": "#6f6f71",
    "ACCENT_WARNING": "#eda200",
    "ACCENT_EMERGENCY": "#e0534b",
    "ACCENT_SUCCESS": "#59a869",
}


def theme_colors() -> dict[str, QColor]:
    """Return the theme colors used by the status box, with dark-theme fallbacks."""
    theme = getattr(QApplication.instance(), "theme", None)
    if theme is None:
        return {key: QColor(value) for key, value in _FALLBACK.items()}
    return {key: theme.color(key, value) for key, value in _FALLBACK.items()}


def tone_color(colors: dict[str, QColor], tone: str) -> QColor:
    """Map a tone name to a theme color."""
    return {
        "success": colors["ACCENT_SUCCESS"],
        "warning": colors["ACCENT_WARNING"],
        "emergency": colors["ACCENT_EMERGENCY"],
    }.get(tone, colors["DISABLED_FG"])


class _Dot(QWidget):
    """A small filled circle that can pulse."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._color = QColor("gray")
        self._opacity = 1.0

    def set_color(self, color: QColor) -> None:
        self._color = QColor(color)
        self.update()

    def set_opacity(self, opacity: float) -> None:
        self._opacity = opacity
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self._opacity)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        painter.drawEllipse(self.rect())


class ElidedLabel(QLabel):
    """A label that elides its text instead of growing the layout."""

    def __init__(self, parent=None, mode=Qt.TextElideMode.ElideRight):
        super().__init__(parent)
        self._mode = mode
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        rect = self.contentsRect()
        text = self.fontMetrics().elidedText(self.text(), self._mode, rect.width())
        painter.drawText(rect, int(self.alignment()), text)


class StatusHeader(QFrame):
    """Overall state of BEC: a colored dot, a headline and a detail line."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusHeader")
        self.setFixedHeight(56)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)
        self.dot = _Dot(self)
        text = QVBoxLayout()
        text.setSpacing(2)
        self.headline = ElidedLabel(self)
        self.headline.setObjectName("headline")
        self.detail = ElidedLabel(self)
        self.detail.setObjectName("detail")
        text.addStretch()
        text.addWidget(self.headline)
        text.addWidget(self.detail)
        text.addStretch()
        layout.addWidget(self.dot)
        layout.addLayout(text, 1)
        self._tone = "neutral"
        self._pulse_up = False
        self._pulse = QTimer(self)
        self._pulse.setInterval(50)
        self._pulse.timeout.connect(self._step_pulse)

    def set_summary(self, headline: str, detail: str, tone: str) -> None:
        """Show the summary of the model."""
        self.headline.setText(headline)
        self.detail.setText(detail)
        self._tone = tone
        if tone == "emergency":
            self._pulse.start()
        else:
            self._pulse.stop()
            self.dot.set_opacity(1.0)
        self.apply_theme()

    def _step_pulse(self):
        step = 0.65 / 14
        opacity = self.dot._opacity + (step if self._pulse_up else -step)
        if opacity <= 0.35 or opacity >= 1.0:
            self._pulse_up = not self._pulse_up
        self.dot.set_opacity(min(1.0, max(0.35, opacity)))

    def apply_theme(self) -> None:
        """Restyle with the current theme colors."""
        colors = theme_colors()
        accent = tone_color(colors, self._tone)
        alpha = 41 if get_theme_name() != "light" else 31
        self.dot.set_color(accent)
        self.setStyleSheet(
            f"#StatusHeader {{ background: {rgba(accent, alpha)}; border: 1px solid "
            f"{rgba(accent, 115)}; border-radius: 8px; }}"
            f"#headline {{ color: {colors['FG'].name()}; font-size: 14px; font-weight: bold; }}"
            f"#detail {{ color: {colors['DISABLED_FG'].name()}; font-size: 11px; }}"
        )

    def stop(self) -> None:
        """Stop the pulse timer."""
        self._pulse.stop()


class ServiceRowWidget(QFrame):
    """One service: status icon, name, subtitle, status chip and expandable details."""

    toggled = Signal(str)
    copy_requested = Signal(str)

    def __init__(self, row: ServiceRow, parent=None):
        super().__init__(parent)
        self.setObjectName("ServiceRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        # keep rows at their natural height so short lists do not spread out
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.row = None
        self.expanded = False
        self._hovered = False
        self._angle = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        main = QWidget(self)
        main.setFixedHeight(44)
        line = QHBoxLayout(main)
        line.setContentsMargins(8, 0, 8, 0)
        line.setSpacing(10)
        self.icon = QLabel(main)
        self.icon.setFixedSize(20, 20)
        names = QVBoxLayout()
        names.setSpacing(1)
        self.name = ElidedLabel(main)
        self.name.setObjectName("name")
        self.subtitle = ElidedLabel(main)
        self.subtitle.setObjectName("subtitle")
        names.addStretch()
        names.addWidget(self.name)
        names.addWidget(self.subtitle)
        names.addStretch()
        self.mismatch = QLabel(main)
        self.mismatch.setObjectName("mismatch")
        self.chip = QLabel(main)
        self.chip.setObjectName("chip")
        self.chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chip.setFixedHeight(20)
        self.mismatch.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mismatch.setFixedHeight(18)
        self.chevron = QLabel(main)
        self.chevron.setFixedSize(16, 16)
        line.addWidget(self.icon)
        line.addLayout(names, 1)
        line.addWidget(self.mismatch)
        line.addWidget(self.chip)
        line.addWidget(self.chevron)
        outer.addWidget(main)

        self.details = QWidget(self)
        details_layout = QHBoxLayout(self.details)
        details_layout.setContentsMargins(38, 0, 8, 8)
        self.details_grid = QGridLayout()
        self.details_grid.setHorizontalSpacing(12)
        self.details_grid.setVerticalSpacing(3)
        self.copy_button = QToolButton(self.details)
        self.copy_button.setToolTip("Copy details")
        self.copy_button.setAutoRaise(True)
        self.copy_button.setIconSize(QSize(16, 16))
        self.copy_button.clicked.connect(lambda: self.copy_requested.emit(self.row.service_name))
        self.copy_button.clicked.connect(self._show_copied)
        details_layout.addLayout(self.details_grid, 1)
        details_layout.addWidget(self.copy_button, 0, Qt.AlignmentFlag.AlignTop)
        self.details.setVisible(False)
        outer.addWidget(self.details)
        self._detail_labels: list[tuple[QLabel, QLabel]] = []
        self._copied = False
        self.set_row(row)

    def set_row(self, row: ServiceRow) -> None:
        """Update the widget for a new version of its row, restyling only when the state changed."""
        previous = getattr(self, "row", None)
        restyle = previous is None or (previous.tone, previous.icon) != (row.tone, row.icon)
        self.row = row
        self.name.setText(row.display_name)
        self.subtitle.setText(row.subtitle)
        self.subtitle.setVisible(bool(row.subtitle))
        self.chip.setText(row.status_label)
        self.mismatch.setText(f"v{row.version}")
        self.mismatch.setToolTip(f"bec_lib {row.version} differs from the other services")
        self.mismatch.setVisible(row.version_mismatch)
        if self.expanded:
            self._fill_details()
        if restyle:
            self.apply_theme()

    @property
    def busy(self) -> bool:
        """Whether the status icon spins."""
        return self.row.status == "BUSY"

    def set_expanded(self, expanded: bool) -> None:
        """Show or hide the details."""
        self.expanded = expanded
        if expanded:
            self._fill_details()
        self.details.setVisible(expanded)
        self.apply_theme()

    def _fill_details(self):
        details = self.row.details
        while len(self._detail_labels) < len(details):
            key, value = QLabel(self.details), QLabel(self.details)
            key.setObjectName("detailKey")
            value.setObjectName("detailValue")
            value.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            idx = len(self._detail_labels)
            self.details_grid.addWidget(key, idx, 0)
            self.details_grid.addWidget(value, idx, 1)
            self._detail_labels.append((key, value))
        for idx, (key, value) in enumerate(self._detail_labels):
            visible = idx < len(details)
            key.setVisible(visible)
            value.setVisible(visible)
            if visible:
                key.setText(details[idx][0])
                value.setText(details[idx][1])
        self.details_grid.setColumnStretch(1, 1)

    def _show_copied(self):
        self._copied = True
        self.copy_button.setToolTip("Copied")
        self._paint_copy_icon()
        QTimer.singleShot(1500, self._reset_copied)

    def _reset_copied(self):
        self._copied = False
        self.copy_button.setToolTip("Copy details")
        self._paint_copy_icon()

    def _paint_copy_icon(self):
        colors = theme_colors()
        self.copy_button.setIcon(
            material_icon(
                "check" if self._copied else "content_copy",
                size=(16, 16),
                color=colors["DISABLED_FG"],
                convert_to_pixmap=False,
            )
        )

    def rotate_icon(self) -> None:
        """Advance the busy spinner by one step."""
        self._angle = (self._angle + 30) % 360
        self._paint_status_icon()

    def _paint_status_icon(self):
        accent = tone_color(theme_colors(), self.row.tone)
        pixmap = material_icon(self.row.icon, size=(20, 20), color=accent, filled=True)
        if self._angle and self.busy:
            rotated = pixmap.transformed(
                QTransform().rotate(self._angle), Qt.TransformationMode.SmoothTransformation
            )
            # crop back to the original size around the center
            x = (rotated.width() - pixmap.width()) // 2
            y = (rotated.height() - pixmap.height()) // 2
            pixmap = rotated.copy(x, y, pixmap.width(), pixmap.height())
        self.icon.setPixmap(pixmap)

    def apply_theme(self) -> None:
        """Restyle with the current theme colors."""
        colors = theme_colors()
        accent = tone_color(colors, self.row.tone)
        if not self.busy:
            self._angle = 0
        self._paint_status_icon()
        self._paint_copy_icon()
        self.chevron.setPixmap(
            material_icon(
                "expand_less" if self.expanded else "expand_more",
                size=(16, 16),
                color=colors["DISABLED_FG"],
            )
        )
        highlighted = self.expanded or self._hovered
        background = colors["CARD_BG"].name() if highlighted else "transparent"
        border = colors["BORDER"].name() if self.expanded else "transparent"
        self.setStyleSheet(
            f"#ServiceRow {{ background: {background}; border: 1px solid {border};"
            f" border-radius: 6px; }}"
            f"#name {{ color: {colors['FG'].name()}; font-size: 13px; }}"
            f"#subtitle, #detailKey {{ color: {colors['DISABLED_FG'].name()}; font-size: 11px; }}"
            f"#detailValue {{ color: {colors['FG'].name()}; font-size: 11px; }}"
            f"#chip {{ color: {accent.name()}; background: {rgba(accent, 38)};"
            f" border-radius: 10px; padding: 0px 8px; font-size: 11px; font-weight: bold; }}"
            f"#mismatch {{ color: {colors['ACCENT_WARNING'].name()}; border: 1px solid"
            f" {colors['ACCENT_WARNING'].name()}; border-radius: 9px; padding: 0px 6px;"
            f" font-size: 10px; }}"
        )

    def event(self, event):
        if event.type() == event.Type.HoverEnter:
            self._hovered = True
            self.apply_theme()
        elif event.type() == event.Type.HoverLeave:
            self._hovered = False
            self.apply_theme()
        return super().event(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 44:
            self.toggled.emit(self.row.service_name)
        super().mouseReleaseEvent(event)


class StatusBoxWidgetView(QWidget):
    """QWidget view bound to a ServiceStatusModel."""

    def __init__(self, model: ServiceStatusModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.expanded_service = ""
        self.rows: dict[str, ServiceRowWidget] = {}
        self.section_labels: dict[str, QLabel] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 4)
        layout.setSpacing(4)
        self.header = StatusHeader(self)
        layout.addWidget(self.header)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget = QWidget(self.scroll)
        self.list_widget.setObjectName("serviceList")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(2)
        self.list_layout.addStretch()
        self.scroll.setWidget(self.list_widget)
        layout.addWidget(self.scroll, 1)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self._spinner = QTimer(self)
        self._spinner.setInterval(100)
        self._spinner.timeout.connect(self._spin)

        model.rowsChanged.connect(self.sync)
        model.summaryChanged.connect(self._update_summary)
        self._update_summary()
        self.sync()
        self.apply_theme()

    def _update_summary(self):
        self.header.set_summary(self.model.headline, self.model.detail, self.model.tone)

    def sync(self) -> None:
        """Bring the row widgets in line with the model, reusing existing widgets."""
        rows = self.model.rows
        names = {row.service_name for row in rows}
        for name in list(self.rows):
            if name not in names:
                widget = self.rows.pop(name)
                self.list_layout.removeWidget(widget)
                widget.deleteLater()
        if self.expanded_service not in names:
            self.expanded_service = ""

        position = 0
        current_group = None
        for row in rows:
            if row.group != current_group:
                current_group = row.group
                label = self._section_label(row.group)
                self._place(label, position)
                position += 1
            widget = self.rows.get(row.service_name)
            if widget is None:
                widget = ServiceRowWidget(row, self.list_widget)
                widget.toggled.connect(self._toggle)
                widget.copy_requested.connect(self.model.copyDetails)
                self.rows[row.service_name] = widget
            elif widget.row != row:
                widget.set_row(row)
            self._place(widget, position)
            position += 1
        groups = {row.group for row in rows}
        for group, label in self.section_labels.items():
            label.setVisible(group in groups)

        if any(widget.busy for widget in self.rows.values()):
            if not self._spinner.isActive():
                self._spinner.start()
        else:
            self._spinner.stop()

    def _place(self, widget: QWidget, position: int):
        if self.list_layout.indexOf(widget) != position:
            self.list_layout.removeWidget(widget)
            self.list_layout.insertWidget(position, widget)
        widget.setVisible(True)

    def _section_label(self, group: str) -> QLabel:
        label = self.section_labels.get(group)
        if label is None:
            label = QLabel(group.upper(), self.list_widget)
            label.setObjectName("section")
            label.setContentsMargins(4, 10, 0, 4)
            self.section_labels[group] = label
            self._style_section(label)
        return label

    def _style_section(self, label: QLabel):
        colors = theme_colors()
        label.setStyleSheet(
            f"#section {{ color: {colors['DISABLED_FG'].name()}; font-size: 10px;"
            f" font-weight: bold; letter-spacing: 0.8px; }}"
        )

    def _toggle(self, service_name: str):
        previous = self.rows.get(self.expanded_service)
        if previous is not None:
            previous.set_expanded(False)
        if self.expanded_service == service_name:
            self.expanded_service = ""
            return
        self.expanded_service = service_name
        self.rows[service_name].set_expanded(True)

    def _spin(self):
        for widget in self.rows.values():
            if widget.busy:
                widget.rotate_icon()

    def apply_theme(self) -> None:
        """Restyle all parts with the current theme colors."""
        colors = theme_colors()
        self.setStyleSheet(f"StatusBoxWidgetView {{ background: {colors['BG'].name()}; }}")
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; } #serviceList { background: transparent; }"
        )
        self.header.apply_theme()
        for label in self.section_labels.values():
            self._style_section(label)
        for widget in self.rows.values():
            widget.apply_theme()

    def cleanup(self) -> None:
        """Stop the timers."""
        self._spinner.stop()
        self.header.stop()
