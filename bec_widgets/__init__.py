__all__ = ["BECWidget", "SafeSlot", "SafeProperty"]


def __getattr__(name):
    if name == "BECWidget":
        from bec_widgets.utils.bec_widget import BECWidget

        return BECWidget
    if name in {"SafeSlot", "SafeProperty"}:
        from bec_widgets.utils.error_popups import SafeProperty, SafeSlot

        return {"SafeSlot": SafeSlot, "SafeProperty": SafeProperty}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
