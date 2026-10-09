"""Helpers for hosting QML views inside BEC QWidgets.

The helpers expose the active BEC theme to QML (``theme`` context property), serve Material icons
from ``bec_qthemes`` through the ``image://material/<name>?color=<hex>&filled=1`` URL scheme, and
create a ``QQuickWidget`` that resizes with its host widget.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs

from bec_qthemes import material_icon
from qtpy.QtCore import Property, QObject, QSize, QUrl, Signal
from qtpy.QtGui import QColor, QPixmap
from qtpy.QtQuick import QQuickImageProvider
from qtpy.QtQuickWidgets import QQuickWidget
from qtpy.QtWidgets import QApplication, QWidget

from bec_widgets.utils.colors import get_theme_name

_FALLBACK_COLORS = {
    "dark": {
        "BG": "#1e1f22",
        "CARD_BG": "#2b2c2f",
        "FG": "#dddddd",
        "BORDER": "#464749",
        "DISABLED_FG": "#6f6f71",
        "PRIMARY": "#6089ef",
        "ACCENT_DEFAULT": "#40b6e0",
        "ACCENT_WARNING": "#eda200",
        "ACCENT_EMERGENCY": "#e0534b",
        "ACCENT_SUCCESS": "#59a869",
    },
    "light": {
        "BG": "#ffffff",
        "CARD_BG": "#f4f5f7",
        "FG": "#1e1f22",
        "BORDER": "#d0d3d9",
        "DISABLED_FG": "#8a8d93",
        "PRIMARY": "#0a60ff",
        "ACCENT_DEFAULT": "#0a60ff",
        "ACCENT_WARNING": "#c88600",
        "ACCENT_EMERGENCY": "#d32f2f",
        "ACCENT_SUCCESS": "#2e7d32",
    },
}


class QmlTheme(QObject):
    """Expose the active BEC theme colors to QML and follow theme changes."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        app = QApplication.instance()
        theme = getattr(app, "theme", None)
        if theme is not None:
            theme.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, _theme: str):
        self.changed.emit()

    def _color(self, key: str) -> QColor:
        name = get_theme_name()
        fallback = _FALLBACK_COLORS.get(name, _FALLBACK_COLORS["dark"])[key]
        theme = getattr(QApplication.instance(), "theme", None)
        if theme is None:
            return QColor(fallback)
        return theme.color(key, fallback)

    @Property(bool, notify=changed)
    def dark(self) -> bool:
        """Whether the dark theme is active."""
        return get_theme_name() != "light"

    @Property(QColor, notify=changed)
    def background(self) -> QColor:
        """Window background color."""
        return self._color("BG")

    @Property(QColor, notify=changed)
    def card(self) -> QColor:
        """Card/surface background color."""
        return self._color("CARD_BG")

    @Property(QColor, notify=changed)
    def text(self) -> QColor:
        """Primary text color."""
        return self._color("FG")

    @Property(QColor, notify=changed)
    def muted(self) -> QColor:
        """Secondary text color."""
        return self._color("DISABLED_FG")

    @Property(QColor, notify=changed)
    def border(self) -> QColor:
        """Border and divider color."""
        return self._color("BORDER")

    @Property(QColor, notify=changed)
    def primary(self) -> QColor:
        """Primary accent color."""
        return self._color("PRIMARY")

    @Property(QColor, notify=changed)
    def success(self) -> QColor:
        """Success accent color."""
        return self._color("ACCENT_SUCCESS")

    @Property(QColor, notify=changed)
    def warning(self) -> QColor:
        """Warning accent color."""
        return self._color("ACCENT_WARNING")

    @Property(QColor, notify=changed)
    def emergency(self) -> QColor:
        """Emergency accent color."""
        return self._color("ACCENT_EMERGENCY")


class MaterialIconProvider(QQuickImageProvider):
    """Serve ``bec_qthemes`` Material icons to QML as ``image://material/<name>?color=..``."""

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Pixmap)

    def requestPixmap(self, icon_id: str, size: QSize, requested_size: QSize) -> QPixmap:
        name, _, query = icon_id.partition("?")
        params = {key: values[-1] for key, values in parse_qs(query).items()}
        side = max(requested_size.width(), requested_size.height(), 0) or 24
        pixmap = material_icon(
            name,
            size=(side, side),
            color=params.get("color"),
            filled=params.get("filled") == "1",
            convert_to_pixmap=True,
        )
        if size is not None:
            size.setWidth(pixmap.width())
            size.setHeight(pixmap.height())
        return pixmap


def create_quick_widget(
    parent: QWidget, qml_file: str | Path, context: dict[str, QObject] | None = None
) -> QQuickWidget:
    """Create a QQuickWidget for a QML file with the BEC theme and icon provider installed.

    Args:
        parent (QWidget): The host widget.
        qml_file (str | Path): Path to the root QML file.
        context (dict[str, QObject] | None): Extra context properties exposed to QML.

    Returns:
        QQuickWidget: The widget, already loaded. Errors are raised as RuntimeError.
    """
    quick = QQuickWidget(parent)
    quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    quick.setClearColor(QColor(0, 0, 0, 0))
    engine = quick.engine()
    engine.addImageProvider("material", MaterialIconProvider())
    theme = QmlTheme(quick)
    quick.rootContext().setContextProperty("theme", theme)
    for name, obj in (context or {}).items():
        quick.rootContext().setContextProperty(name, obj)
    quick.setSource(QUrl.fromLocalFile(str(Path(qml_file).resolve())))
    if quick.status() == QQuickWidget.Status.Error:
        errors = "; ".join(err.toString() for err in quick.errors())
        raise RuntimeError(f"Failed to load {qml_file}: {errors}")
    return quick
