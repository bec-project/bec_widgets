import os
import sys

if sys.platform.startswith("linux"):
    qt_platform = os.environ.get("QT_QPA_PLATFORM", "")
    if qt_platform != "offscreen":
        os.environ["QT_QPA_PLATFORM"] = "xcb"

__all__ = ["BECWidget", "SafeSlot", "SafeProperty"]


def __getattr__(name: str):
    if name == "BECWidget":
        from bec_widgets.utils.bec_widget import BECWidget

        return BECWidget
    if name in {"SafeProperty", "SafeSlot"}:
        from bec_widgets.utils.error_popups import SafeProperty, SafeSlot

        return {"SafeProperty": SafeProperty, "SafeSlot": SafeSlot}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
