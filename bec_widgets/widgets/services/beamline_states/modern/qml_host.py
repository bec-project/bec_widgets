"""
Helpers for hosting QML views inside BEC widgets.

A QML view is embedded with ``QQuickWidget`` so it lives inside the usual ``BECWidget`` shell
(dock areas, RPC, cleanup). The view gets two shared helpers:

* ``theme``: a :class:`QmlTheme` context property exposing the active bec_qthemes colors, and
* ``image://material/<name>?color=<hex>&filled=<0|1>``: Material icons rendered by bec_qthemes.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from bec_qthemes import material_icon
from qtpy.QtCore import Property, QObject, QSize, QUrl, Signal
from qtpy.QtGui import QColor, QImage
from qtpy.QtQuick import QQuickImageProvider
from qtpy.QtQuickWidgets import QQuickWidget
from qtpy.QtWidgets import QApplication, QWidget

from bec_widgets.utils.colors import Colors

_DARK_FALLBACK = {
    "BG": "#1e1f22",
    "CARD_BG": "#2b2c2f",
    "FIELD_BG": "#26272a",
    "FG": "#dddddd",
    "BORDER": "#464749",
    "PRIMARY": "#6089ef",
    "ON_PRIMARY": "#ffffff",
    "ACCENT_DEFAULT": "#40B6E0",
    "ACCENT_WARNING": "#EDA200",
    "ACCENT_EMERGENCY": "#E0534B",
    "ACCENT_SUCCESS": "#59A869",
}


def _app_theme():
    app = QApplication.instance()
    return getattr(app, "theme", None) if app is not None else None


class QmlTheme(QObject):
    """Theme colors of the running BEC application, exposed to QML as ``theme``."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._colors: dict[str, QColor] = {}
        self._dark = True
        theme = _app_theme()
        if theme is not None:
            theme.theme_changed.connect(self.refresh)
        self.refresh()

    def refresh(self, *_args) -> None:
        """Re-read the colors from the application theme."""
        theme = _app_theme()
        self._dark = theme is None or theme.theme != "light"
        self._colors = {
            key: theme.color(key, fallback) if theme is not None else QColor(fallback)
            for key, fallback in _DARK_FALLBACK.items()
        }
        self.changed.emit()

    def get(self, key: str) -> QColor:
        """Return a theme color by its bec_qthemes key."""
        return QColor(self._colors.get(key, QColor(_DARK_FALLBACK.get(key, "#000000"))))

    def _color(key: str, notify=changed):  # pylint: disable=no-self-argument
        return Property(QColor, lambda self: self.get(key), notify=notify)

    dark = Property(bool, lambda self: self._dark, notify=changed)
    background = _color("BG")
    card = _color("CARD_BG")
    field = _color("FIELD_BG")
    foreground = _color("FG")
    border = _color("BORDER")
    primary = _color("PRIMARY")
    onPrimary = _color("ON_PRIMARY")  # noqa: N815
    info = _color("ACCENT_DEFAULT")
    success = _color("ACCENT_SUCCESS")
    warning = _color("ACCENT_WARNING")
    danger = _color("ACCENT_EMERGENCY")

    @Property(QColor, notify=changed)
    def muted(self) -> QColor:
        """Secondary text color, between card background and foreground."""
        return Colors._blend(self.get("CARD_BG"), self.get("FG"), 0.62)

    del _color


class MaterialIconProvider(QQuickImageProvider):
    """Serves ``image://material/<name>?color=<hex>&filled=<0|1>`` from bec_qthemes."""

    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Image)

    def requestImage(self, icon_id: str, size: QSize, requested: QSize) -> QImage:  # noqa: N802
        parts = urlsplit(icon_id)
        query = parse_qs(parts.query)
        color = query.get("color", [None])[0]
        filled = query.get("filled", ["0"])[0] in ("1", "true")
        width = requested.width() if requested.width() > 0 else 24
        height = requested.height() if requested.height() > 0 else width
        try:
            image = material_icon(
                parts.path, size=(width, height), color=color, filled=filled
            ).toImage()
        except KeyError:
            image = QImage(width, height, QImage.Format.Format_ARGB32)
            image.fill(0)
        if size is not None:
            size.setWidth(image.width())
            size.setHeight(image.height())
        return image


def create_quick_widget(
    parent: QWidget, qml_file: str | Path, context: dict[str, QObject] | None = None
) -> QQuickWidget:
    """
    Create a ``QQuickWidget`` showing ``qml_file`` with the shared theme and icon helpers.

    Args:
        parent: Widget that owns the view.
        qml_file: Path to the root QML file.
        context: Extra objects exposed to QML as context properties.

    Returns:
        QQuickWidget: The loaded view. Its ``theme`` context property is a :class:`QmlTheme`.
    """
    view = QQuickWidget(parent)
    view.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    view.setClearColor(QColor(0, 0, 0, 0))
    engine = view.engine()
    engine.addImageProvider("material", MaterialIconProvider())
    theme = QmlTheme(view)
    view.setProperty("qml_theme", theme)
    root_context = view.rootContext()
    root_context.setContextProperty("theme", theme)
    for name, obj in (context or {}).items():
        root_context.setContextProperty(name, obj)
    view.setSource(QUrl.fromLocalFile(str(Path(qml_file).resolve())))
    if view.status() == QQuickWidget.Status.Error:
        errors = "\n".join(error.toString() for error in view.errors())
        raise RuntimeError(f"Failed to load {qml_file}:\n{errors}")
    return view
