from bec_widgets.utils import BECConnector
from bec_widgets.widgets.figure import BECFigure


class RPCWidgetHandler:
    """Handler class for creating widgets from RPC messages."""

    widget_classes = {
        "BECFigure": BECFigure,
    }

    @staticmethod
    def create_widget(widget_type, **kwargs) -> BECConnector:
        """
        Create a widget from an RPC message.

        Args:
            widget_type(str): The type of the widget.
            **kwargs: The keyword arguments for the widget.

        Returns:
            widget(BECConnector): The created widget.
        """
        widget_class = RPCWidgetHandler.widget_classes.get(widget_type)
        if widget_class:
            return widget_class(**kwargs)
        raise ValueError(f"Unknown widget type: {widget_type}")
