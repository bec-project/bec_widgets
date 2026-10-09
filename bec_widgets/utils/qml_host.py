"""
Helpers for hosting a QML view inside a BEC widget.

A QML-based widget keeps its QWidget shell (``BECWidget`` + a Qt widget class) so RPC, the
Designer plugin and docking work unchanged. The shell embeds a ``QQuickWidget`` created with
:func:`create_quick_widget`, which wires up two things every BEC QML view needs:

* ``theme`` — a :class:`QmlTheme` context property mirroring the active ``bec_qthemes`` palette,
  updated live when the application theme changes;
* ``image://material/<name>`` — Material icons rendered by ``bec_qthemes.material_icon``,
  e.g. ``image://material/pause?color=40B6E0&filled=1``.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs

from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy.QtCore import Property, QObject, QSize, Qt, QUrl, Signal
from qtpy.QtGui import QColor, QPixmap
from qtpy.QtQml import QQmlImageProviderBase
from qtpy.QtQuick import QQuickImageProvider
from qtpy.QtQuickWidgets import QQuickWidget
from qtpy.QtWidgets import QApplication, QWidget

logger = bec_logger.logger

# Fallback palette (bec_qthemes "dark") used when no theme has been applied yet.
_FALLBACK = {
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


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    """Blend colour ``a`` towards ``b`` by ``t`` (0 = a, 1 = b)."""
    return QColor.fromRgbF(
        a.redF() + (b.redF() - a.redF()) * t,
        a.greenF() + (b.greenF() - a.greenF()) * t,
        a.blueF() + (b.blueF() - a.blueF()) * t,
        1.0,
    )


def _readable_on(color: QColor, background: QColor, is_dark: bool) -> QColor:
    """Return ``color`` adjusted so it stays legible as text on ``background``."""
    if is_dark:
        return _mix(color, QColor("#ffffff"), 0.15)
    # Accent colours such as the light theme's yellow are too pale for text on white.
    return _mix(color, QColor("#000000"), 0.35 if color.lightnessF() > 0.5 else 0.1)


class QmlTheme(QObject):
    """
    The active ``bec_qthemes`` palette as QML-readable properties.

    Base colours come straight from the theme; derived colours (muted text, hover fills, state
    text and tints) are computed here so every QML view uses the same rules.
    """

    changed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._c: dict[str, QColor] = {}
        self._dark = True
        self._reload()
        app = QApplication.instance()
        theme = getattr(app, "theme", None)
        if theme is not None and hasattr(theme, "theme_changed"):
            theme.theme_changed.connect(self._reload)

    def _reload(self, *_args):
        app = QApplication.instance()
        theme = getattr(app, "theme", None)
        colors = {k: QColor(v) for k, v in _FALLBACK.items()}
        if theme is not None:
            try:
                colors.update({k: QColor(v) for k, v in theme.colors.items()})
            except Exception:  # pragma: no cover - defensive, theme API drift
                logger.warning("Could not read the bec_qthemes palette; using defaults.")
        bg, fg = colors["BG"], colors["FG"]
        self._dark = bg.lightnessF() < 0.5
        card = colors["CARD_BG"]
        c = dict(colors)
        c["MUTED"] = _mix(fg, card, 0.38)
        c["FAINT"] = _mix(fg, card, 0.6)
        c["HOVER"] = _mix(card, fg, 0.07)
        c["PRESSED"] = _mix(card, fg, 0.13)
        c["SEPARATOR"] = _mix(card, fg, 0.1)
        for key, name in (
            ("ACCENT_DEFAULT", "BUSY"),
            ("ACCENT_SUCCESS", "OK"),
            ("ACCENT_WARNING", "WARN"),
            ("ACCENT_EMERGENCY", "ERR"),
        ):
            c[f"{name}_TEXT"] = _readable_on(colors[key], card, self._dark)
            c[f"{name}_TINT"] = _mix(card, colors[key], 0.18 if self._dark else 0.12)
        self._c = c
        self.changed.emit()

    def _get(self, key: str) -> QColor:
        return self._c.get(key, QColor("#ff00ff"))

    # pylint: disable=missing-function-docstring
    isDark = Property(bool, lambda self: self._dark, notify=changed)
    bg = Property(QColor, lambda self: self._get("BG"), notify=changed)
    card = Property(QColor, lambda self: self._get("CARD_BG"), notify=changed)
    field = Property(QColor, lambda self: self._get("FIELD_BG"), notify=changed)
    fg = Property(QColor, lambda self: self._get("FG"), notify=changed)
    muted = Property(QColor, lambda self: self._get("MUTED"), notify=changed)
    faint = Property(QColor, lambda self: self._get("FAINT"), notify=changed)
    border = Property(QColor, lambda self: self._get("BORDER"), notify=changed)
    separator = Property(QColor, lambda self: self._get("SEPARATOR"), notify=changed)
    hover = Property(QColor, lambda self: self._get("HOVER"), notify=changed)
    pressed = Property(QColor, lambda self: self._get("PRESSED"), notify=changed)
    primary = Property(QColor, lambda self: self._get("PRIMARY"), notify=changed)
    onPrimary = Property(QColor, lambda self: self._get("ON_PRIMARY"), notify=changed)
    busy = Property(QColor, lambda self: self._get("ACCENT_DEFAULT"), notify=changed)
    ok = Property(QColor, lambda self: self._get("ACCENT_SUCCESS"), notify=changed)
    warn = Property(QColor, lambda self: self._get("ACCENT_WARNING"), notify=changed)
    err = Property(QColor, lambda self: self._get("ACCENT_EMERGENCY"), notify=changed)
    busyText = Property(QColor, lambda self: self._get("BUSY_TEXT"), notify=changed)
    okText = Property(QColor, lambda self: self._get("OK_TEXT"), notify=changed)
    warnText = Property(QColor, lambda self: self._get("WARN_TEXT"), notify=changed)
    errText = Property(QColor, lambda self: self._get("ERR_TEXT"), notify=changed)
    busyTint = Property(QColor, lambda self: self._get("BUSY_TINT"), notify=changed)
    okTint = Property(QColor, lambda self: self._get("OK_TINT"), notify=changed)
    warnTint = Property(QColor, lambda self: self._get("WARN_TINT"), notify=changed)
    errTint = Property(QColor, lambda self: self._get("ERR_TINT"), notify=changed)


class MaterialIconProvider(QQuickImageProvider):
    """
    Serves ``bec_qthemes`` Material icons to QML.

    URL form: ``image://material/<icon_name>?color=<hex without #>&filled=1``.
    """

    def __init__(self):
        super().__init__(QQmlImageProviderBase.ImageType.Pixmap)

    def requestPixmap(self, icon_id: str, size: QSize, requested_size: QSize) -> QPixmap:
        name, _, query = icon_id.partition("?")
        params = parse_qs(query)
        color = params.get("color", [None])[0]
        filled = params.get("filled", ["0"])[0] == "1"
        if requested_size.isValid() and requested_size.width() > 0:
            target = requested_size
        else:
            target = QSize(24, 24)
        pixmap = material_icon(
            name,
            size=(target.width(), target.height()),
            color=f"#{color}" if color else None,
            filled=filled,
            convert_to_pixmap=True,
        )
        if size is not None:
            size.setWidth(pixmap.width())
            size.setHeight(pixmap.height())
        return pixmap


def create_quick_widget(
    parent: QWidget, qml_file: Path, context: dict[str, QObject]
) -> QQuickWidget:
    """
    Create a ``QQuickWidget`` that loads ``qml_file`` with the BEC theme and icon provider.

    Args:
        parent(QWidget): Parent widget (the BEC widget shell).
        qml_file(Path): The root QML file.
        context(dict[str, QObject]): Extra context properties, e.g. the widget's controller.

    Returns:
        QQuickWidget: The view, already loaded. QML errors are logged.
    """
    view = QQuickWidget(parent)
    view.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    engine = view.engine()
    engine.addImageProvider("material", MaterialIconProvider())
    theme = QmlTheme(view)
    view.rootContext().setContextProperty("theme", theme)
    for name, obj in context.items():
        view.rootContext().setContextProperty(name, obj)
    view.setClearColor(theme.card)
    theme.changed.connect(lambda: view.setClearColor(theme.card))
    view.setSource(QUrl.fromLocalFile(str(qml_file)))
    if view.status() == QQuickWidget.Status.Error:
        for error in view.errors():
            logger.error(f"QML error in {qml_file.name}: {error.toString()}")
    return view
