from __future__ import annotations

from bec_widgets.cli.client_utils import IGNORE_WIDGETS
from bec_widgets.utils.bec_plugin_helper import get_all_plugin_widgets
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.plugin_utils import get_custom_classes


class RPCWidgetHandler:
    """Handler class for creating widgets from RPC messages."""

    def __init__(self):
        self._widget_classes = None

    @property
    def widget_classes(self) -> dict[str, type[BECWidget]]:
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
        self._widget_classes = (
            get_custom_classes("bec_widgets") + get_all_plugin_widgets()
        ).as_dict(IGNORE_WIDGETS)

    def create_widget(self, widget_type, **kwargs) -> BECWidget:
        """
        Create a widget from an RPC message.

        Args:
            widget_type(str): The type of the widget.
            name (str): The name of the widget.
            **kwargs: The keyword arguments for the widget.

        Returns:
            widget(BECWidget): The created widget.
        """
        widget_class = self.widget_classes.get(widget_type)  # type: ignore
        if widget_class:
            return widget_class(**kwargs)
        raise ValueError(f"Unknown widget type: {widget_type}")


widget_handler = RPCWidgetHandler()
