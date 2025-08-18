import os
import sys

import PySide6QtAds as QtAds

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot

if sys.platform.startswith("linux"):
    qt_platform = os.environ.get("QT_QPA_PLATFORM", "")
    if qt_platform != "offscreen":
        os.environ["QT_QPA_PLATFORM"] = "xcb"

# Default QtAds configuration
QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.eConfigFlag.FocusHighlighting, True)
QtAds.CDockManager.setConfigFlag(
    QtAds.CDockManager.eConfigFlag.RetainTabSizeWhenCloseButtonHidden, True
)

__all__ = ["BECWidget", "SafeSlot", "SafeProperty"]
