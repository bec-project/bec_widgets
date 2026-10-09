"""Helpers to host QML views inside BEC QWidgets (QQuickWidget, theme colours, Material icons)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs

from bec_qthemes import material_icon
from qtpy.QtCore import QSize, QUrl
from qtpy.QtGui import QColor, QPixmap
from qtpy.QtQuick import QQuickImageProvider
from qtpy.QtQuickWidgets import QQuickWidget
from qtpy.QtWidgets import QWidget


class MaterialIconProvider(QQuickImageProvider):
    """Serve bec_qthemes Material icons to QML as ``image://material/<name>?color=<hex>``.

    Add ``&filled=1`` for the filled variant.
    """

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Pixmap)

    def requestPixmap(self, icon_id: str, size: QSize, requested_size: QSize) -> QPixmap:
        """Render the requested icon.

        Args:
            icon_id (str): Icon name with optional query parameters.
            size (QSize): Out-parameter for the original size (unused).
            requested_size (QSize): The size requested by QML.

        Returns:
            QPixmap: The rendered icon.
        """
        name, _, query = icon_id.partition("?")
        options = {key: values[-1] for key, values in parse_qs(query).items()}
        width = requested_size.width() if requested_size.width() > 0 else 24
        height = requested_size.height() if requested_size.height() > 0 else width
        color = options.get("color")
        return material_icon(
            name,
            size=(width, height),
            color=QColor(color) if color else None,
            filled=options.get("filled") == "1",
            convert_to_pixmap=True,
        )


def create_quick_widget(
    parent: QWidget, qml_file: str | Path, context: dict[str, object] | None = None
) -> QQuickWidget:
    """Create a transparent QQuickWidget that sizes its root item to the widget.

    Args:
        parent (QWidget): Parent widget.
        qml_file (str | Path): The QML file to load.
        context (dict[str, object] | None): Objects exposed to QML as context properties.

    Returns:
        QQuickWidget: The loaded view. Check ``status()`` and ``errors()`` for load failures.
    """
    view = QQuickWidget(parent)
    view.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    view.setClearColor(QColor(0, 0, 0, 0))
    engine = view.engine()
    engine.addImageProvider("material", MaterialIconProvider())
    for name, obj in (context or {}).items():
        view.rootContext().setContextProperty(name, obj)
    view.setSource(QUrl.fromLocalFile(str(Path(qml_file).resolve())))
    return view
