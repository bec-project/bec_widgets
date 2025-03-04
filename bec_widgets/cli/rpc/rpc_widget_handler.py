from __future__ import annotations

from typing import Any

from bec_widgets.utils.bec_widget import BECWidget


class RPCWidgetHandler:
    """Handler class for creating widgets from RPC messages."""

    def __init__(self):
        self._widget_classes = None

    @property
    def widget_classes(self) -> dict[str, Any]:
        """
        Get the available widget classes.

        Returns:
            dict: The available widget classes.
        """
        if self._widget_classes is None:
            self.update_available_widgets()
        return self._widget_classes  # type: ignore

    def update_available_widgets(self):
        """
        Update the available widgets.

        Returns:
            None
        """
        from bec_widgets.utils.plugin_utils import get_custom_classes

        clss = get_custom_classes("bec_widgets")
        self._widget_classes = {cls.__name__: cls for cls in clss.widgets}

    def create_widget(self, widget_type, name: str, **kwargs) -> BECWidget:
        """
        Create a widget from an RPC message.

        Args:
            widget_type(str): The type of the widget.
            name (str): The name of the widget.
            **kwargs: The keyword arguments for the widget.

        Returns:
            widget(BECWidget): The created widget.
        """
        if self._widget_classes is None:
            self.update_available_widgets()
        widget_class = self._widget_classes.get(widget_type)  # type: ignore
        if widget_class:
            return widget_class(name=name, **kwargs)
        raise ValueError(f"Unknown widget type: {widget_type}")


widget_handler = RPCWidgetHandler()
