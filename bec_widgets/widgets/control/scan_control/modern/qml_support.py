"""Small helpers for hosting QML views inside BEC widgets.

Provides a theme object that mirrors the active ``bec_qthemes`` colours, an image provider for
Material icons (``image://material/<name>?color=<hex>&filled=1``) and a factory for a configured
``QQuickWidget``.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from bec_qthemes import material_icon
from qtpy.QtCore import Property, QObject, QSize, QUrl, Signal
from qtpy.QtGui import QColor, QPixmap
from qtpy.QtQuick import QQuickImageProvider
from qtpy.QtQuickWidgets import QQuickWidget
from qtpy.QtWidgets import QApplication, QWidget

_FALLBACK = {
    "dark": {
        "PRIMARY": "#6089ef",
        "ON_PRIMARY": "#ffffff",
        "BG": "#1e1f22",
        "CARD_BG": "#2b2c2f",
        "FIELD_BG": "#26272a",
        "FG": "#dddddd",
        "BORDER": "#464749",
        "ACCENT_WARNING": "#EDA200",
        "ACCENT_EMERGENCY": "#E0534B",
        "ACCENT_SUCCESS": "#59A869",
    },
    "light": {
        "PRIMARY": "#3b82f6",
        "ON_PRIMARY": "#ffffff",
        "BG": "#f6f7fb",
        "CARD_BG": "#ffffff",
        "FIELD_BG": "#ffffff",
        "FG": "#151924",
        "BORDER": "#d9dde6",
        "ACCENT_WARNING": "#EAC435",
        "ACCENT_EMERGENCY": "#CC181E",
        "ACCENT_SUCCESS": "#2CA58D",
    },
}


def _app_theme():
    app = QApplication.instance()
    return getattr(app, "theme", None) if app is not None else None


def theme_colors() -> tuple[str, dict[str, QColor]]:
    """Name and colours of the active theme, falling back to built-in defaults."""
    theme = _app_theme()
    name = getattr(theme, "theme", "dark") if theme is not None else "dark"
    name = "light" if name == "light" else "dark"
    colors = {k: QColor(v) for k, v in _FALLBACK[name].items()}
    if theme is not None:
        for key in colors:
            colors[key] = theme.color(key, colors[key].name())
    return name, colors


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
    )


class QmlTheme(QObject):
    """Theme colours for QML, updated when the BEC theme changes."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._name = "dark"
        self._colors: dict[str, QColor] = {}
        self.refresh()
        theme = _app_theme()
        if theme is not None:
            theme.theme_changed.connect(self.refresh)

    def refresh(self, *_args) -> None:
        """Re-read the colours of the active theme."""
        self._name, self._colors = theme_colors()
        self.changed.emit()

    def _c(self, key: str) -> QColor:
        return self._colors[key]

    @Property(bool, notify=changed)
    def dark(self) -> bool:
        return self._name == "dark"

    @Property(QColor, notify=changed)
    def bg(self) -> QColor:
        return self._c("BG")

    @Property(QColor, notify=changed)
    def card(self) -> QColor:
        return self._c("CARD_BG")

    @Property(QColor, notify=changed)
    def field(self) -> QColor:
        return self._c("FIELD_BG")

    @Property(QColor, notify=changed)
    def fg(self) -> QColor:
        return self._c("FG")

    @Property(QColor, notify=changed)
    def muted(self) -> QColor:
        return _mix(self._c("FG"), self._c("CARD_BG"), 0.4)

    @Property(QColor, notify=changed)
    def border(self) -> QColor:
        return self._c("BORDER")

    @Property(QColor, notify=changed)
    def hover(self) -> QColor:
        return _mix(self._c("CARD_BG"), self._c("FG"), 0.08)

    @Property(QColor, notify=changed)
    def primary(self) -> QColor:
        return self._c("PRIMARY")

    @Property(QColor, notify=changed)
    def onPrimary(self) -> QColor:  # pylint: disable=invalid-name
        return self._c("ON_PRIMARY")

    @Property(QColor, notify=changed)
    def success(self) -> QColor:
        return self._c("ACCENT_SUCCESS")

    @Property(QColor, notify=changed)
    def warning(self) -> QColor:
        return self._c("ACCENT_WARNING")

    @Property(QColor, notify=changed)
    def danger(self) -> QColor:
        return self._c("ACCENT_EMERGENCY")


class MaterialIconProvider(QQuickImageProvider):
    """Serves ``image://material/<icon>?color=%23rrggbb&filled=1`` from bec_qthemes."""

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Pixmap)

    def requestPixmap(self, icon_id: str, size: QSize, requested_size: QSize) -> QPixmap:
        # pylint: disable=invalid-name
        parts = urlsplit(icon_id)
        query = {k: v[-1] for k, v in parse_qs(parts.query).items()}
        side = max(requested_size.width(), requested_size.height(), 0) or 24
        pixmap = material_icon(
            parts.path,
            size=(side, side),
            color=query.get("color"),
            filled=query.get("filled") == "1",
        )
        if size is not None:
            size.setWidth(pixmap.width())
            size.setHeight(pixmap.height())
        return pixmap


def create_quick_widget(
    parent: QWidget, qml_file: Path, context: dict[str, QObject]
) -> QQuickWidget:
    """Create a ``QQuickWidget`` that sizes its root item to the widget and loads ``qml_file``."""
    view = QQuickWidget(parent)
    view.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    engine = view.engine()
    engine.addImageProvider("material", MaterialIconProvider())
    for name, obj in context.items():
        view.rootContext().setContextProperty(name, obj)
    view.setSource(QUrl.fromLocalFile(str(qml_file)))
    if view.status() == QQuickWidget.Status.Error:
        errors = "\n".join(error.toString() for error in view.errors())
        raise RuntimeError(f"Failed to load {qml_file.name}:\n{errors}")
    return view
