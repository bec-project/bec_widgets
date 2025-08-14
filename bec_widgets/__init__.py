import os
import sys

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot

if sys.platform.startswith("linux"):
    qt_platform = os.environ.get("QT_QPA_PLATFORM", "")
    if qt_platform != "offscreen":
        os.environ["QT_QPA_PLATFORM"] = "xcb"

__all__ = ["BECWidget", "SafeSlot", "SafeProperty"]
