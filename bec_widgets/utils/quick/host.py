"""Hosting helpers for QML views embedded into BEC widgets.

All QML views share one :class:`QQmlEngine` per application. The engine carries the
application-wide ``theme`` context property (a :class:`QmlTheme` bridging ``app.theme`` from
``bec_qthemes``), an ``image://material/<name>`` provider for Material icons and the import path
of the shared ``BecUi`` control module. Per-widget state is handed to the view through initial
properties of the root item, typically a single ``backend`` QObject.

Views that still pass per-view context properties get their own engine, configured the same way,
so the older ports can switch to this module without touching their QML.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs

from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy.QtCore import Property, QObject, QSize, Qt, QUrl, Signal, Slot
from qtpy.QtGui import QColor, QPixmap
from qtpy.QtQml import QQmlEngine
from qtpy.QtQuick import QQuickImageProvider
from qtpy.QtQuickWidgets import QQuickWidget
from qtpy.QtWidgets import QApplication, QWidget

from bec_widgets.utils.quick.tokens import METRICS, ThemeTokens, app_theme
from bec_widgets.utils.quick.tokens import blend as _blend  # kept for ports importing it from here

logger = bec_logger.logger

QML_IMPORT_PATH = Path(__file__).parent / "qml"

__all__ = [
    "QML_IMPORT_PATH",
    "MaterialIconProvider",
    "QmlTheme",
    "ThemeTokens",
    "configure_engine",
    "create_quick_widget",
    "quick_engine",
    "quick_theme",
    "release_quick_widget",
]


class QmlTheme(QObject):
    """Expose the BEC theme to QML as ``theme.<token>`` and follow theme changes.

    Canonical colour names: ``bg``, ``card``, ``field``, ``border``, ``separator``, ``fg``,
    ``fgMuted``, ``fgSubtle``, ``hover``, ``pressed``, ``track``, ``sunken``, ``primary``,
    ``onPrimary``, ``info``, ``success``, ``warning``, ``danger``, ``highlight`` and, for each
    status colour, ``<tone>Text`` (readable on cards) and ``<tone>Tint`` (soft fill).

    Metrics: ``radiusSmall``, ``radiusLarge``, ``controlHeight``, ``controlHeightCompact``,
    ``spacing``, ``padding``, ``fontCaption``, ``fontSmall``, ``fontBody``, ``fontTitle``,
    ``fontHeadline``, ``fontDisplay`` and ``monoFamily``.

    Tone helpers callable from QML: ``theme.tone(name)``, ``theme.toneText(name)`` and
    ``theme.toneTint(name)``.

    The names used by the first ports are kept as aliases (``muted``, ``faint``, ``text``,
    ``foreground``, ``background``, ``accent``, ``busy``, ``ok``, ``warn``, ``err``,
    ``emergency``, ``isDark``, ``busyText``, ``okTint``, ``window``, ``base``, ``button``,
    ``onAccent`` and the raw palette map ``c``), so their QML runs unchanged.
    """

    changed = Signal()

    # pylint: disable=no-self-argument
    def _color_property(token: str, notify=changed):
        return Property(QColor, lambda self: QColor(getattr(self._tokens, token)), notify=notify)

    def _metric_property(key: str):
        return Property(int, lambda self: METRICS[key], constant=True)

    # pylint: enable=no-self-argument

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._tokens = ThemeTokens()
        self._connected_theme = None
        self._connect_theme()

    def _connect_theme(self) -> None:
        theme = app_theme()
        if theme is None or theme is self._connected_theme:
            return
        theme.theme_changed.connect(self.refresh)
        self._connected_theme = theme

    @property
    def tokens(self) -> ThemeTokens:
        """The tokens currently exposed to QML."""
        return self._tokens

    def refresh(self, *_args) -> None:
        """Re-read the tokens from the application theme."""
        self._connect_theme()
        self._tokens = ThemeTokens()
        self.changed.emit()

    @Slot(str, result=QColor)
    def tone(self, name: str) -> QColor:
        """Base colour of a status tone, e.g. ``theme.tone("warning")``."""
        return self._tokens.tone(name)

    @Slot(str, result=QColor)
    def toneText(self, name: str) -> QColor:  # pylint: disable=invalid-name
        """Readable text colour of a status tone."""
        return self._tokens.tone_text(name)

    @Slot(str, result=QColor)
    def toneTint(self, name: str) -> QColor:  # pylint: disable=invalid-name
        """Soft background fill of a status tone."""
        return self._tokens.tone_tint(name)

    # pylint: disable=invalid-name
    name = Property(str, lambda self: self._tokens.name, notify=changed)
    dark = Property(bool, lambda self: self._tokens.dark, notify=changed)
    monoFamily = Property(str, lambda self: self._tokens.mono_family, notify=changed)

    bg = _color_property("bg")
    card = _color_property("card")
    field = _color_property("field")
    border = _color_property("border")
    separator = _color_property("separator")
    fg = _color_property("fg")
    fgMuted = _color_property("fg_muted")
    fgSubtle = _color_property("fg_subtle")
    hover = _color_property("hover")
    pressed = _color_property("pressed")
    track = _color_property("track")
    sunken = _color_property("sunken")
    primary = _color_property("primary")
    onPrimary = _color_property("on_primary")
    info = _color_property("info")
    success = _color_property("success")
    warning = _color_property("warning")
    danger = _color_property("danger")
    highlight = _color_property("highlight")
    infoText = _color_property("info_text")
    successText = _color_property("success_text")
    warningText = _color_property("warning_text")
    dangerText = _color_property("danger_text")
    highlightText = _color_property("highlight_text")
    infoTint = _color_property("info_tint")
    successTint = _color_property("success_tint")
    warningTint = _color_property("warning_tint")
    dangerTint = _color_property("danger_tint")
    highlightTint = _color_property("highlight_tint")

    radiusSmall = _metric_property("radiusSmall")
    radiusLarge = _metric_property("radiusLarge")
    controlHeight = _metric_property("controlHeight")
    controlHeightCompact = _metric_property("controlHeightCompact")
    spacing = _metric_property("spacing")
    padding = _metric_property("padding")
    fontCaption = _metric_property("fontCaption")
    fontSmall = _metric_property("fontSmall")
    fontBody = _metric_property("fontBody")
    fontTitle = _metric_property("fontTitle")
    fontHeadline = _metric_property("fontHeadline")
    fontDisplay = _metric_property("fontDisplay")

    # Aliases for the token names of the first ports (queue, status box, beamline states, fit
    # dialog). New QML should use the canonical names above.
    isDark = Property(bool, lambda self: self._tokens.dark, notify=changed)
    background = _color_property("bg")
    text = _color_property("fg")
    foreground = _color_property("fg")
    muted = _color_property("fg_muted")
    faint = _color_property("fg_subtle")
    accent = _color_property("accent")
    busy = _color_property("info")
    ok = _color_property("success")
    warn = _color_property("warning")
    err = _color_property("danger")
    emergency = _color_property("danger")
    busyText = _color_property("info_text")
    okText = _color_property("success_text")
    warnText = _color_property("warning_text")
    errText = _color_property("danger_text")
    busyTint = _color_property("info_tint")
    okTint = _color_property("success_tint")
    warnTint = _color_property("warning_tint")
    errTint = _color_property("danger_tint")
    window = _color_property("bg")
    base = _color_property("field")
    button = _color_property("card")
    onAccent = _color_property("on_primary")

    @Property("QVariantMap", notify=changed)
    def c(self) -> dict:
        """The raw ``bec_qthemes`` palette as ``{KEY: "#rrggbb"}``, e.g. ``theme.c.ACCENT_DEFAULT``."""
        theme = app_theme()
        colors = dict(getattr(theme, "colors", None) or {})
        return {
            key: QColor(value).name() for key, value in colors.items() if QColor(value).isValid()
        }

    # pylint: enable=invalid-name

    del _color_property, _metric_property


def _parse_icon_color(value: str | None) -> str | None:
    """Normalise the colour of an icon URL to ``#rrggbb`` or ``#rrggbbaa`` for bec_qthemes.

    Accepts ``#rrggbb``, ``rrggbb`` (no hash), ``#aarrggbb`` (QML's ``color.toString()`` for
    translucent colours) and SVG colour names such as ``red``.
    """
    if not value:
        return None
    if not value.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in value):
        value = f"#{value}"
    color = QColor(value)
    if not color.isValid():
        return None
    if color.alpha() == 255:
        return color.name()
    return f"{color.name()}{color.alpha():02x}"


class MaterialIconProvider(QQuickImageProvider):
    """Serve Material icons to QML as ``image://material/<name>?color=%23rrggbb&filled=1``.

    The colour may also be given without ``#`` (``color=40B6E0``). Unknown icon names give an
    empty pixmap and a log message instead of an exception.
    """

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Pixmap)

    def requestPixmap(self, icon_id: str, size: QSize, requested_size: QSize) -> QPixmap:
        name, _, query = icon_id.partition("?")
        options = parse_qs(query)
        color = _parse_icon_color(options.get("color", [None])[0])
        filled = options.get("filled", ["0"])[0] in ("1", "true")
        target = requested_size if requested_size.isValid() else QSize(24, 24)
        if target.width() <= 0 or target.height() <= 0:
            target = QSize(24, 24)
        pixmap = QPixmap()
        if name and name != "undefined":
            try:
                pixmap = material_icon(
                    name, size=target, color=color, filled=filled, convert_to_pixmap=True
                )
            except (KeyError, FileNotFoundError, ValueError):
                logger.warning(f"Unknown Material icon requested from QML: {name}")
        if size is not None:
            size.setWidth(pixmap.width())
            size.setHeight(pixmap.height())
        return pixmap


_ENGINE: QQmlEngine | None = None
_THEME: QmlTheme | None = None


def configure_engine(engine: QQmlEngine, theme: QmlTheme | None = None) -> QmlTheme:
    """Install the ``BecUi`` import path, the icon provider and the ``theme`` property.

    Args:
        engine(QQmlEngine): Engine to configure.
        theme(QmlTheme | None): Theme bridge to expose; a new one owned by the engine if None.

    Returns:
        QmlTheme: The theme bridge exposed as ``theme``.
    """
    engine.addImportPath(str(QML_IMPORT_PATH))
    engine.addImageProvider("material", MaterialIconProvider())
    theme = theme or QmlTheme(engine)
    engine.rootContext().setContextProperty("theme", theme)
    engine.warnings.connect(
        lambda warnings: [logger.warning(f"QML: {w.toString()}") for w in warnings]
    )
    return theme


def quick_engine() -> QQmlEngine:
    """Return the application-wide QML engine used by all BEC QML views."""
    global _ENGINE, _THEME  # pylint: disable=global-statement
    if _ENGINE is not None:
        if _THEME._connected_theme is not app_theme():  # pylint: disable=protected-access
            # the theme was applied after the engine was created
            _THEME.refresh()
        return _ENGINE
    app = QApplication.instance()
    _ENGINE = QQmlEngine(app)
    _THEME = configure_engine(_ENGINE)
    if app is not None:
        app.aboutToQuit.connect(_drop_engine)
    return _ENGINE


def quick_theme() -> QmlTheme:
    """Return the theme bridge of the shared engine."""
    quick_engine()
    return _THEME


def _drop_engine() -> None:
    global _ENGINE, _THEME  # pylint: disable=global-statement
    _ENGINE = None
    _THEME = None


class _ClearColorFollower(QObject):
    """Keeps the clear colour of a view in sync with the theme; dies with the view."""

    def __init__(self, view: QQuickWidget, theme: QmlTheme, background: str):
        super().__init__(view)
        self._view = view
        self._theme = theme
        self._background = background
        theme.changed.connect(self.apply)
        self.apply()

    @Slot()
    def apply(self) -> None:
        """Apply the clear colour for the current theme."""
        tokens = self._theme.tokens
        color = {"window": tokens.bg, "card": tokens.card}.get(self._background, QColor(0, 0, 0, 0))
        self._view.setClearColor(color)


def create_quick_widget(
    parent: QWidget,
    qml_file: str | Path,
    properties: dict | None = None,
    context: dict[str, QObject] | None = None,
    background: str = "window",
    raise_on_error: bool = False,
) -> QQuickWidget:
    """Create a QQuickWidget showing ``qml_file`` with the BEC theme, icons and ``BecUi``.

    Args:
        parent(QWidget): Parent widget, usually the BEC widget shell.
        qml_file(str | Path): Path of the root QML file.
        properties(dict | None): Initial properties of the root item, e.g. ``{"backend": obj}``.
            This is the preferred way to hand state to a view.
        context(dict[str, QObject] | None): Context properties, as used by the first ports.
            Views with context properties get their own engine (about 10 MB each), because
            context properties of the shared engine would leak into every other view.
        background(str): ``"window"``, ``"card"`` or ``"transparent"``; follows theme changes.
        raise_on_error(bool): Raise ``RuntimeError`` when the QML fails to load instead of
            only logging it.

    Returns:
        QQuickWidget: The view, already loaded.
    """
    qml_file = Path(qml_file)
    if context:
        view = QQuickWidget(parent)
        theme = configure_engine(view.engine(), QmlTheme(view))
        for name, obj in context.items():
            view.rootContext().setContextProperty(name, obj)
    else:
        view = QQuickWidget(quick_engine(), parent)
        theme = _THEME
    view.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    view.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, False)
    view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    _ClearColorFollower(view, theme, background)
    if properties:
        view.setInitialProperties(properties)
    view.setSource(QUrl.fromLocalFile(str(qml_file.resolve())))
    errors = [error.toString() for error in view.errors()]
    for error in errors:
        logger.error(f"QML error in {qml_file.name}: {error}")
    if errors and raise_on_error:
        raise RuntimeError(f"Failed to load {qml_file.name}: {'; '.join(errors)}")
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
