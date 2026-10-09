"""Small helpers to host a QML view inside a QWidget: theme bridge and Material icon provider."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

from bec_qthemes import material_icon
from qtpy.QtCore import Property, QObject, QSize, QUrl, Signal
from qtpy.QtGui import QColor, QPixmap
from qtpy.QtQuick import QQuickImageProvider
from qtpy.QtQuickWidgets import QQuickWidget
from qtpy.QtWidgets import QApplication, QWidget

from bec_widgets.utils.colors import get_theme_name
from bec_widgets.widgets.progress.scan_progressbar.scan_progress_model import current_theme_colors


class QmlTheme(QObject):
    """Exposes the current bec_qthemes palette to QML as ``theme.c.<KEY>`` hex strings."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent=parent)
        self._colors: dict[str, str] = {}
        self._dark = True
        self.refresh()
        app = QApplication.instance()
        if hasattr(app, "theme"):
            app.theme.theme_changed.connect(self.refresh)

    def refresh(self, *_args):
        """Re-read the palette from the application theme."""
        self._dark = get_theme_name() == "dark"
        self._colors = {k: QColor(v).name() for k, v in current_theme_colors().items()}
        self.changed.emit()

    @Property("QVariantMap", notify=changed)
    def c(self) -> dict:
        return self._colors

    @Property(bool, notify=changed)
    def dark(self) -> bool:
        return self._dark


class MaterialIconProvider(QQuickImageProvider):
    """Serves ``image://material/<name>?color=<hex>&filled=1`` from bec_qthemes."""

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Pixmap)

    def requestPixmap(self, icon_id: str, size, requested_size: QSize) -> QPixmap:
        name, _, query = icon_id.partition("?")
        if not name or name == "undefined":
            return QPixmap()
        params = {k: unquote(v) for k, v in (p.split("=", 1) for p in query.split("&") if "=" in p)}
        edge = max(requested_size.width(), requested_size.height(), 0) or 24
        pixmap = material_icon(
            name,
            size=(edge, edge),
            color=params.get("color", "#888888"),
            filled=params.get("filled") == "1",
        )
        if size is not None:
            size.setWidth(pixmap.width())
            size.setHeight(pixmap.height())
        return pixmap


def create_quick_widget(
    parent: QWidget, qml_file: Path, context: dict[str, QObject]
) -> QQuickWidget:
    """
    Create a QQuickWidget that loads ``qml_file`` with the given context properties.

    The theme bridge is always available as ``theme`` and icons under ``image://material/``.

    Args:
        parent(QWidget): Parent widget.
        qml_file(Path): QML file to load.
        context(dict[str, QObject]): Extra context properties.

    Returns:
        QQuickWidget: The configured widget.
    """
    view = QQuickWidget(parent)
    view.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    view.setClearColor(QColor(0, 0, 0, 0))
    engine = view.engine()
    # keep Python references, otherwise the wrappers are collected while QML still uses them
    view._icon_provider = MaterialIconProvider()
    engine.addImageProvider("material", view._icon_provider)
    theme = QmlTheme(view)
    view._qml_theme = theme
    view.rootContext().setContextProperty("theme", theme)
    for name, obj in context.items():
        view.rootContext().setContextProperty(name, obj)
    view.setSource(QUrl.fromLocalFile(str(qml_file)))
    for error in view.errors():
        raise RuntimeError(f"QML error in {qml_file.name}: {error.toString()}")
    return view
