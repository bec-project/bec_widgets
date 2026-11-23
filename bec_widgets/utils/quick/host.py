"""Hosting helpers for QML views embedded into BEC widgets.

All QML views share one :class:`QQmlEngine` per application. The engine carries the
application-wide ``theme`` context property (a :class:`QmlTheme` bridging ``app.theme`` from
``bec_qthemes``), an ``image://material/<name>`` provider for Material icons and the import path
of the shared ``BecUi`` control module. Per-widget state is handed to the view through initial
properties of the root item, typically a single ``backend`` QObject.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs

from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy.QtCore import Property, QObject, QSize, Qt, QUrl, Signal
from qtpy.QtGui import QColor, QPixmap
from qtpy.QtQml import QQmlEngine
from qtpy.QtQuick import QQuickImageProvider
from qtpy.QtQuickWidgets import QQuickWidget
from qtpy.QtWidgets import QApplication, QWidget

logger = bec_logger.logger

QML_IMPORT_PATH = Path(__file__).parent / "qml"

_DARK_FALLBACK = {
    "PRIMARY": "#3b82f6",
    "ON_PRIMARY": "#ffffff",
    "BG": "#0f1115",
    "CARD_BG": "#171a21",
    "FIELD_BG": "#10131a",
    "BORDER": "#2a2f3a",
    "FG": "#e8ebf1",
    "ACCENT_DEFAULT": "#8ab4f7",
    "ACCENT_HIGHLIGHT": "#B53565",
    "ACCENT_WARNING": "#EAC435",
    "ACCENT_EMERGENCY": "#CC181E",
    "ACCENT_SUCCESS": "#2CA58D",
}


def _blend(base: QColor, top: QColor, amount: float) -> QColor:
    """Return ``top`` mixed into ``base`` by ``amount`` (0 = base, 1 = top)."""
    return QColor.fromRgbF(
        base.redF() + (top.redF() - base.redF()) * amount,
        base.greenF() + (top.greenF() - base.greenF()) * amount,
        base.blueF() + (top.blueF() - base.blueF()) * amount,
        1.0,
    )


class ThemeTokens:
    """Resolved colour tokens of the active BEC theme, shared by the QML and QWidget ports."""

    def __init__(self):
        app = QApplication.instance()
        theme = getattr(app, "theme", None) if app is not None else None
        name = getattr(theme, "theme", "dark") if theme is not None else "dark"

        def color(key: str) -> QColor:
            fallback = _DARK_FALLBACK.get(key, "#808080")
            if theme is None:
                return QColor(fallback)
            return QColor(theme.color(key, fallback))

        self.name: str = str(name)
        self.bg = color("BG")
        self.card = color("CARD_BG")
        self.field = color("FIELD_BG")
        self.border = color("BORDER")
        self.fg = color("FG")
        self.primary = color("PRIMARY")
        self.on_primary = color("ON_PRIMARY")
        self.accent = color("ACCENT_DEFAULT")
        self.highlight = color("ACCENT_HIGHLIGHT")
        self.warning = color("ACCENT_WARNING")
        self.danger = color("ACCENT_EMERGENCY")
        self.success = color("ACCENT_SUCCESS")
        self.dark = self.bg.lightnessF() < 0.5
        self.fg_muted = _blend(self.card, self.fg, 0.62)
        self.fg_subtle = _blend(self.card, self.fg, 0.4)
        self.hover = _blend(self.card, self.fg, 0.06)
        self.pressed = _blend(self.card, self.fg, 0.12)
        self.track = _blend(self.card, self.fg, 0.1)

    def soft(self, color: QColor, amount: float = 0.16) -> QColor:
        """Tint ``color`` onto the card background, e.g. for chips and banners."""
        return _blend(self.card, color, amount)


class QmlTheme(QObject):
    """Expose the BEC theme colours to QML as ``theme.<token>`` and follow theme changes."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._tokens = ThemeTokens()
        self._connected_theme = None
        self._connect_theme()

    def _connect_theme(self) -> None:
        app = QApplication.instance()
        theme = getattr(app, "theme", None) if app is not None else None
        if theme is None or theme is self._connected_theme:
            return
        theme.theme_changed.connect(self.refresh)
        self._connected_theme = theme

    def refresh(self, *_args) -> None:
        """Re-read the tokens from the application theme."""
        self._connect_theme()
        self._tokens = ThemeTokens()
        self.changed.emit()

    # pylint: disable=missing-function-docstring
    def _get(self, name: str) -> QColor:
        return getattr(self._tokens, name)

    name = Property(str, lambda self: self._tokens.name, notify=changed)
    dark = Property(bool, lambda self: self._tokens.dark, notify=changed)
    bg = Property(QColor, lambda self: self._get("bg"), notify=changed)
    card = Property(QColor, lambda self: self._get("card"), notify=changed)
    field = Property(QColor, lambda self: self._get("field"), notify=changed)
    border = Property(QColor, lambda self: self._get("border"), notify=changed)
    fg = Property(QColor, lambda self: self._get("fg"), notify=changed)
    fgMuted = Property(QColor, lambda self: self._get("fg_muted"), notify=changed)
    fgSubtle = Property(QColor, lambda self: self._get("fg_subtle"), notify=changed)
    hover = Property(QColor, lambda self: self._get("hover"), notify=changed)
    pressed = Property(QColor, lambda self: self._get("pressed"), notify=changed)
    track = Property(QColor, lambda self: self._get("track"), notify=changed)
    primary = Property(QColor, lambda self: self._get("primary"), notify=changed)
    onPrimary = Property(QColor, lambda self: self._get("on_primary"), notify=changed)
    accent = Property(QColor, lambda self: self._get("accent"), notify=changed)
    highlight = Property(QColor, lambda self: self._get("highlight"), notify=changed)
    warning = Property(QColor, lambda self: self._get("warning"), notify=changed)
    danger = Property(QColor, lambda self: self._get("danger"), notify=changed)
    success = Property(QColor, lambda self: self._get("success"), notify=changed)


class MaterialIconProvider(QQuickImageProvider):
    """Serve Material icons to QML as ``image://material/<name>?color=%23rrggbb&filled=1``."""

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Pixmap)

    def requestPixmap(self, icon_id: str, size: QSize, requested_size: QSize) -> QPixmap:
        name, _, query = icon_id.partition("?")
        options = parse_qs(query)
        color = options.get("color", [None])[0]
        filled = options.get("filled", ["0"])[0] in ("1", "true")
        target = requested_size if requested_size.isValid() else QSize(24, 24)
        if target.width() <= 0 or target.height() <= 0:
            target = QSize(24, 24)
        pixmap = material_icon(name, size=target, color=color, filled=filled)
        if size is not None:
            size.setWidth(pixmap.width())
            size.setHeight(pixmap.height())
        return pixmap


_ENGINE: QQmlEngine | None = None
_THEME: QmlTheme | None = None


def quick_engine() -> QQmlEngine:
    """Return the application-wide QML engine used by all BEC QML views."""
    global _ENGINE, _THEME  # pylint: disable=global-statement
    if _ENGINE is not None:
        if _THEME._connected_theme is None:  # pylint: disable=protected-access
            # the theme was applied after the engine was created
            _THEME.refresh()
        return _ENGINE
    app = QApplication.instance()
    _ENGINE = QQmlEngine(app)
    _ENGINE.addImportPath(str(QML_IMPORT_PATH))
    _ENGINE.addImageProvider("material", MaterialIconProvider())
    _THEME = QmlTheme(_ENGINE)
    _ENGINE.rootContext().setContextProperty("theme", _THEME)
    _ENGINE.warnings.connect(
        lambda warnings: [logger.warning(f"QML: {w.toString()}") for w in warnings]
    )
    if app is not None:
        app.aboutToQuit.connect(_drop_engine)
    return _ENGINE


def _drop_engine() -> None:
    global _ENGINE, _THEME  # pylint: disable=global-statement
    _ENGINE = None
    _THEME = None


def create_quick_widget(
    parent: QWidget, qml_file: str | Path, properties: dict | None = None
) -> QQuickWidget:
    """Create a QQuickWidget showing ``qml_file`` on the shared engine.

    Args:
        parent(QWidget): Parent widget, usually the BEC widget shell.
        qml_file(str | Path): Path of the root QML file.
        properties(dict | None): Initial properties of the root item, e.g. ``{"backend": obj}``.

    Returns:
        QQuickWidget: The view, already loaded. Load errors are logged.
    """
    view = QQuickWidget(quick_engine(), parent)
    view.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    view.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, False)
    view.setClearColor(parent.palette().window().color())
    if properties:
        view.setInitialProperties(properties)
    view.setSource(QUrl.fromLocalFile(str(qml_file)))
    for error in view.errors():
        logger.error(f"QML error in {qml_file}: {error.toString()}")
    return view


def release_quick_widget(view: QQuickWidget | None) -> None:
    """Unload the QML scene of ``view`` before its backend objects are destroyed.

    Without this, bindings of a still-loaded scene are re-evaluated against already deleted
    backends during teardown and log ``TypeError`` warnings.
    """
    if view is None:
        return
    try:
        view.setSource(QUrl())
    except RuntimeError:
        # the C++ object is already gone
        return
