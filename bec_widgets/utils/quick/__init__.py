"""The BEC UI kit: shared plumbing and controls for QML and QWidget versions of BEC widgets.

* :mod:`bec_widgets.utils.quick.tokens`: colour and metric tokens from ``bec_qthemes``.
* :mod:`bec_widgets.utils.quick.host`: the shared QML engine, theme bridge and icon provider.
* ``bec_widgets/utils/quick/qml/BecUi``: the QML controls (``import BecUi``).
* :mod:`bec_widgets.utils.ux_kit`: the matching QWidget controls.

See ``bec_widgets/utils/quick/README.md`` for the component reference.
"""

from bec_widgets.utils.quick.host import (
    QML_IMPORT_PATH,
    MaterialIconProvider,
    QmlTheme,
    configure_engine,
    create_quick_widget,
    quick_engine,
    quick_theme,
    release_quick_widget,
)
from bec_widgets.utils.quick.list_model import DictListModel
from bec_widgets.utils.quick.tokens import ThemeTokens

__all__ = [
    "QML_IMPORT_PATH",
    "DictListModel",
    "MaterialIconProvider",
    "QmlTheme",
    "ThemeTokens",
    "configure_engine",
    "create_quick_widget",
    "quick_engine",
    "quick_theme",
    "release_quick_widget",
]
