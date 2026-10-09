"""Positioner box rendered with QML inside a QQuickWidget."""

from __future__ import annotations

from pathlib import Path

from bec_qthemes import material_icon
from qtpy.QtCore import Property, QObject, QSize, QUrl, Signal
from qtpy.QtGui import QColor, QPalette
from qtpy.QtQuick import QQuickImageProvider
from qtpy.QtQuickWidgets import QQuickWidget
from qtpy.QtWidgets import QApplication

from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.device_control.positioner_box.positioner_box_modern.positioner_box_modern_base import (
    ModernPositionerBoxBase,
)

QML_FILE = Path(__file__).parent / "qml" / "PositionerBox.qml"


class QmlTheme(QObject):
    """Theme colors for QML, taken from the application palette and BEC accent colors."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._colors: dict[str, QColor] = {}
        self.refresh()

    def refresh(self):
        """Re-read the colors after a theme change."""
        palette = QApplication.palette()
        accents = get_accent_colors()
        window = palette.color(QPalette.ColorRole.Window)
        self._colors = {
            "window": window,
            "base": palette.color(QPalette.ColorRole.Base),
            "button": palette.color(QPalette.ColorRole.Button),
            "border": palette.color(QPalette.ColorRole.Mid),
            "text": palette.color(QPalette.ColorRole.WindowText),
            "muted": palette.color(QPalette.ColorRole.PlaceholderText),
            "accent": palette.color(QPalette.ColorRole.Highlight),
            "onAccent": palette.color(QPalette.ColorRole.HighlightedText),
            "success": accents.success,
            "warning": accents.warning,
            "danger": accents.emergency,
        }
        self.changed.emit()

    def color(self, name: str) -> QColor:
        """Return a theme color by name, e.g. ``"window"``."""
        return self._colors[name]

    def _color(name, notify=changed):  # pylint: disable=no-self-argument
        return Property(QColor, lambda self: self.color(name), notify=notify)

    window = _color("window")
    base = _color("base")
    button = _color("button")
    border = _color("border")
    text = _color("text")
    muted = _color("muted")
    accent = _color("accent")
    onAccent = _color("onAccent")
    success = _color("success")
    warning = _color("warning")
    danger = _color("danger")


class MaterialIconProvider(QQuickImageProvider):
    """Serves ``image://material/<name>?<color>`` from bec_qthemes Material icons."""

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Pixmap)

    def requestPixmap(self, icon_id: str, size: QSize, requested_size: QSize):
        name, _, color = icon_id.partition("?")
        side = requested_size.width() if requested_size.width() > 0 else 24
        pixmap = material_icon(name, size=(side, side), color=color or None, filled=True)
        if size is not None:
            size.setWidth(pixmap.width())
            size.setHeight(pixmap.height())
        return pixmap


class PositionerBoxQML(ModernPositionerBoxBase):
    """Positioner box with the modernized UX, drawn in QML."""

    def init_view(self):
        self.theme = QmlTheme(self)
        self.view = QQuickWidget(self)
        self.view.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        engine = self.view.engine()
        engine.addImageProvider("material", MaterialIconProvider())
        context = self.view.rootContext()
        context.setContextProperty("box", self.state)
        context.setContextProperty("theme", self.theme)
        self.view.setClearColor(self.theme.color("window"))
        self.view.setSource(QUrl.fromLocalFile(str(QML_FILE)))
        for error in self.view.errors():
            raise RuntimeError(f"PositionerBox.qml: {error.toString()}")
        self.view.setMinimumSize(240, 250)
        self.main_layout.addWidget(self.view)

    @SafeSlot(str)
    def apply_theme(self, theme: str):
        self.theme.refresh()
        self.view.setClearColor(self.theme.color("window"))

    def cleanup(self):
        self.view.setSource(QUrl())
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    widget = PositionerBoxQML(device="samx")
    widget.show()
    sys.exit(app.exec())
