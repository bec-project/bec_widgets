from __future__ import annotations

from typing import TYPE_CHECKING

from bec_widgets.utils.plugin_utils import get_rpc_widget, rpc_widget_registry

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.utils.bec_widget import BECWidget


class RPCWidgetHandler:
    """Handler class for creating widgets from RPC messages."""

    def __init__(self):
        self._widget_registry = None

    @property
    def widget_classes(self) -> dict[str, tuple[str, str]]:
        """
        Get the available widget classes.

        Returns:
            dict: The available widget classes.
        """
        registry = rpc_widget_registry()
        if not registry:
            return {}
        return registry

    @staticmethod
    def create_widget(widget_type, **kwargs) -> BECWidget:
        """
        Create a widget from an RPC message.

        Args:
            widget_type(str): The type of the widget.
            name (str): The name of the widget.
            **kwargs: The keyword arguments for the widget.

        Returns:
            widget(BECWidget): The created widget.
        """
        widget = get_rpc_widget(widget_type, raise_on_missing=False)
        if widget:
            return widget(**kwargs)
        raise ValueError(f"Unknown widget type: {widget_type}")


widget_handler = RPCWidgetHandler()
