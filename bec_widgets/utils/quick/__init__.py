"""Shared plumbing for widgets that render their content with Qt Quick (QML).

The QML ports keep the usual ``BECWidget`` shell and public API and only swap the rendering
layer: a :class:`~qtpy.QtQuickWidgets.QQuickWidget` is embedded into the existing widget and
driven by a small Python backend object.
"""

from bec_widgets.utils.quick.host import (
    QML_IMPORT_PATH,
    MaterialIconProvider,
    QmlTheme,
    create_quick_widget,
    quick_engine,
    release_quick_widget,
)
from bec_widgets.utils.quick.list_model import DictListModel

__all__ = [
    "QML_IMPORT_PATH",
    "DictListModel",
    "MaterialIconProvider",
    "QmlTheme",
    "create_quick_widget",
    "quick_engine",
    "release_quick_widget",
]
