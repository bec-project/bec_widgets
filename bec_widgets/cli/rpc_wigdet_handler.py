from bec_widgets.utils import BECConnector
from bec_widgets.widgets.figure import BECFigure
from bec_widgets.widgets.spiral_progress_bar.spiral_progress_bar import SpiralProgressBar
from bec_widgets.widgets.text_box.text_box import TextBox
from bec_widgets.widgets.website.website import WebsiteWidget


class RPCWidgetHandler:
    """Handler class for creating widgets from RPC messages."""

    widget_classes = {
        "BECFigure": BECFigure,
        "SpiralProgressBar": SpiralProgressBar,
        "Website": WebsiteWidget,
        "TextBox": TextBox,
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
