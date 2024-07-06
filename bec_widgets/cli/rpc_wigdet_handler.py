from bec_widgets.utils import BECConnector


class RPCWidgetHandler:
    """Handler class for creating widgets from RPC messages."""

    def __init__(self):
        self._widget_classes = None

    @property
    def widget_classes(self):
        """
        Get the available widget classes.

        Returns:
            dict: The available widget classes.
        """
        if self._widget_classes is None:
            self.update_available_widgets()
        return self._widget_classes

    def update_available_widgets(self):
        """
        Update the available widgets.

        Returns:
            None
        """
        from bec_widgets.utils.plugin_utils import get_rpc_classes

        clss = get_rpc_classes("bec_widgets")
        self._widget_classes = {cls.__name__: cls for cls in clss.top_level_classes}

    def create_widget(self, widget_type, **kwargs) -> BECConnector:
        """
        Create a widget from an RPC message.

        Args:
            widget_type(str): The type of the widget.
            **kwargs: The keyword arguments for the widget.

        Returns:
            widget(BECConnector): The created widget.
        """
        if self._widget_classes is None:
            self.update_available_widgets()
        widget_class = self._widget_classes.get(widget_type)
        if widget_class:
            return widget_class(**kwargs)
        raise ValueError(f"Unknown widget type: {widget_type}")


widget_handler = RPCWidgetHandler()
