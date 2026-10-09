"""Small themed QWidget controls used by the QWidget twins of the QML widget ports.

They mirror the ``BecUi`` QML controls in ``bec_widgets/utils/quick/qml`` so that the QML and
QWidget versions of a widget look and behave the same and can be compared side by side. Colours
come from the same :class:`~bec_widgets.utils.quick.host.ThemeTokens`.
"""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt
from qtpy.QtGui import QColor, QFont, QPainter
from qtpy.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.quick.host import ThemeTokens


def rgba(color: QColor, alpha: float) -> str:
    """Return a QSS ``rgba()`` string for ``color`` with alpha in 0..1."""
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {int(alpha * 255)})"


def refresh_kit_theme(root: QWidget) -> ThemeTokens:
    """Re-theme every kit control below ``root`` and return the current tokens."""
    tokens = ThemeTokens()
    for widget in [root, *root.findChildren(QWidget)]:
        refresh = getattr(widget, "refresh_theme", None)
        if callable(refresh) and widget is not root:
            refresh(tokens)
    return tokens


def field_qss(tokens: ThemeTokens) -> str:
    """Stylesheet for inputs inside kit cards; ``invalid=true`` marks a field with an error."""
    return f"""
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
            background: {tokens.field.name()};
            color: {tokens.fg.name()};
            border: 1px solid {tokens.border.name()};
            border-radius: 6px;
            padding: 0px 8px;
            min-height: 30px;
            font-size: 13px;
            selection-background-color: {tokens.primary.name()};
        }}
        QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
            border-color: {tokens.fg_subtle.name()};
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 2px solid {tokens.primary.name()};
            padding: 0px 7px;
        }}
        QLineEdit[invalid="true"], QComboBox[invalid="true"] {{
            border: 2px solid {tokens.danger.name()};
            padding: 0px 7px;
        }}
        QLineEdit:disabled, QComboBox:disabled {{ color: {tokens.fg_subtle.name()}; }}
        QComboBox::drop-down {{ border: none; width: 22px; }}
    """


def set_invalid(widget: QWidget, invalid: bool) -> None:
    """Toggle the ``invalid`` style of a field styled with :func:`field_qss`."""
    if bool(widget.property("invalid")) == invalid:
        return
    widget.setProperty("invalid", invalid)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class IconButton(QToolButton):
    """Flat square icon button with hover feedback, matching ``BecUi.IconButton``."""

    def __init__(self, icon_name: str, tip: str = "", parent: QWidget | None = None, size=18):
        super().__init__(parent)
        self._icon_name = icon_name
        self._icon_size = size
        self.setToolTip(tip)
        self.setAccessibleName(tip)
        self.setAutoRaise(True)
        self.setFixedSize(30, 30)
        self.setIconSize(QSize(size, size))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_theme(ThemeTokens())

    def set_icon_name(self, icon_name: str) -> None:
        """Change the Material icon."""
        self._icon_name = icon_name
        self.refresh_theme(ThemeTokens())

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens."""
        color = tokens.primary if self.isChecked() else tokens.fg_muted
        self.setIcon(
            material_icon(self._icon_name, size=(48, 48), color=color, convert_to_pixmap=False)
        )
        self.setStyleSheet(
            f"QToolButton {{ border: none; border-radius: 6px; background: transparent; }}"
            f"QToolButton:hover, QToolButton:checked {{ background: {tokens.hover.name()}; }}"
            f"QToolButton:pressed {{ background: {tokens.pressed.name()}; }}"
        )


class TextButton(QPushButton):
    """Labelled button; variant is ``primary``, ``danger``, ``success``, ``neutral`` or ``ghost``."""

    def __init__(
        self,
        text: str,
        variant: str = "neutral",
        icon_name: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(text, parent)
        self._variant = variant
        self._icon_name = icon_name
        self.setMinimumHeight(32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_theme(ThemeTokens())

    def set_variant(self, variant: str) -> None:
        """Switch the colour variant."""
        self._variant = variant
        self.refresh_theme(ThemeTokens())

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens."""
        base = {"primary": tokens.primary, "danger": tokens.danger, "success": tokens.success}.get(
            self._variant
        )
        if base is not None:
            label = QColor("white")
            qss = (
                f"QPushButton {{ background: {base.name()}; color: white; border: none;"
                f" border-radius: 6px; padding: 0 12px; font-size: 13px; font-weight: 600; }}"
                f"QPushButton:hover {{ background: {base.lighter(110).name()}; }}"
                f"QPushButton:pressed {{ background: {base.darker(125).name()}; }}"
                f"QPushButton:disabled {{ background: {rgba(base, 0.45)};"
                f" color: {rgba(label, 0.7)}; }}"
            )
        else:
            label = tokens.fg
            border = tokens.border.name() if self._variant == "neutral" else "transparent"
            qss = (
                f"QPushButton {{ background: transparent; color: {tokens.fg.name()};"
                f" border: 1px solid {border}; border-radius: 6px; padding: 0 12px;"
                f" font-size: 13px; font-weight: 500; }}"
                f"QPushButton:hover {{ background: {tokens.hover.name()}; }}"
                f"QPushButton:pressed {{ background: {tokens.pressed.name()}; }}"
                f"QPushButton:disabled {{ color: {tokens.fg_subtle.name()}; }}"
            )
        self.setStyleSheet(qss)
        if self._icon_name:
            self.setIcon(
                material_icon(self._icon_name, size=(32, 32), color=label, convert_to_pixmap=False)
            )
            self.setIconSize(QSize(16, 16))


class StatusPill(QWidget):
    """Rounded status chip with a coloured dot, matching ``BecUi.StatusPill``."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._text = ""
        self._tone = QColor("#808080")
        self._dot_opacity = 1.0
        self._pulse = QPropertyAnimation(self, b"dot_opacity", self)
        self._pulse.setDuration(1100)
        self._pulse.setKeyValueAt(0.0, 1.0)
        self._pulse.setKeyValueAt(0.5, 0.25)
        self._pulse.setKeyValueAt(1.0, 1.0)
        self._pulse.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._pulse.setLoopCount(-1)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        font = self.font()
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.DemiBold)
        self.setFont(font)

    def set_status(self, text: str, tone: QColor, pulse: bool = False) -> None:
        """Set label, colour and whether the dot pulses."""
        self._text = text
        self._tone = QColor(tone)
        if pulse and self._pulse.state() != QPropertyAnimation.State.Running:
            self._pulse.start()
        elif not pulse:
            self._pulse.stop()
            self._dot_opacity = 1.0
        self.setToolTip(text)
        self.updateGeometry()
        self.update()

    @property
    def text(self) -> str:
        """Current label."""
        return self._text

    @property
    def pulsing(self) -> bool:
        """Whether the dot animation runs."""
        return self._pulse.state() == QPropertyAnimation.State.Running

    def _get_dot_opacity(self) -> float:
        return self._dot_opacity

    def _set_dot_opacity(self, value: float) -> None:
        self._dot_opacity = value
        self.update()

    dot_opacity = Property(float, _get_dot_opacity, _set_dot_opacity)

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        return QSize(self.fontMetrics().horizontalAdvance(self._text) + 26, 22)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        background = QColor(self._tone)
        background.setAlphaF(0.16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        dot = QColor(self._tone)
        dot.setAlphaF(self._dot_opacity)
        painter.setBrush(dot)
        painter.drawEllipse(QRectF(9, rect.height() / 2 - 3.5, 7, 7))
        painter.setPen(self._tone)
        painter.drawText(rect.adjusted(22, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, self._text)
        painter.end()

    def cleanup(self) -> None:
        """Stop the pulse animation."""
        self._pulse.stop()


class Card(QFrame):
    """Rounded surface with an optional title row, matching ``BecUi.Card``."""

    def __init__(self, title: str = "", parent: QWidget | None = None, padding: int = 12):
        super().__init__(parent)
        self.setObjectName("uxCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(padding, padding, padding, padding)
        outer.setSpacing(10)
        self.header = QHBoxLayout()
        self.header.setSpacing(8)
        self.title_label = QLabel(title, self)
        self.subtitle_label = QLabel("", self)
        self.subtitle_label.setVisible(False)
        self.header.addWidget(self.title_label)
        self.header.addWidget(self.subtitle_label, 1)
        self.header_extras = QHBoxLayout()
        self.header_extras.setSpacing(4)
        self.header.addLayout(self.header_extras)
        outer.addLayout(self.header)
        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        outer.addLayout(self.body)
        self._has_title = bool(title)
        self._update_header_visibility()
        self.refresh_theme(ThemeTokens())

    def set_title(self, title: str, subtitle: str = "") -> None:
        """Set the title and an optional muted subtitle."""
        self._has_title = bool(title)
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)
        self.subtitle_label.setVisible(bool(subtitle))
        self._update_header_visibility()

    def add_header_widget(self, widget: QWidget) -> None:
        """Add a widget to the right end of the title row."""
        self.header_extras.addWidget(widget)
        self._has_title = True
        self._update_header_visibility()

    def _update_header_visibility(self) -> None:
        self.title_label.setVisible(bool(self.title_label.text()))

    def refresh_theme(self, tokens: ThemeTokens) -> None:
        """Apply the theme tokens."""
        self.setStyleSheet(
            f"QFrame#uxCard {{ background: {tokens.card.name()};"
            f" border: 1px solid {tokens.border.name()}; border-radius: 10px; }}"
        )
        self.title_label.setStyleSheet(
            f"color: {tokens.fg.name()}; font-size: 13px; font-weight: 600; background: none;"
        )
        self.subtitle_label.setStyleSheet(
            f"color: {tokens.fg_subtle.name()}; font-size: 12px; background: none;"
        )


class PortedPropertiesMixin:
    """Make a port export and load the ``SafeProperty`` settings of the class it ports.

    ``BECConnector`` only collects the properties defined directly on ``type(self)``, so a
    subclass would silently drop the inherited ones (e.g. ``ring_json``) from saved profiles.
    Set ``PORTED_FROM`` to the original class; its properties and those of every class in
    between are collected.
    """

    PORTED_FROM: type | None = None

    def _get_bec_meta_objects(self) -> dict:
        objects = {}
        for cls in type(self).__mro__:
            for name, attr in vars(cls).items():
                if name in objects or not isinstance(attr, Property):
                    continue
                if getattr(attr.fget, "__is_safe_getter__", False):
                    objects[name] = attr
            if cls is self.PORTED_FROM:
                break
        return objects
