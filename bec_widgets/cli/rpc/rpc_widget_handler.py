from __future__ import annotations

from typing import TYPE_CHECKING

from bec_lib.utils.import_utils import lazy_import_from

from bec_widgets.utils.bec_plugin_helper import get_all_plugin_widget_references
from bec_widgets.utils.plugin_utils import get_custom_class_references

try:
    from bec_widgets.cli.constants import IGNORE_WIDGETS
except ModuleNotFoundError:  # pragma: no cover
    IGNORE_WIDGETS = ["LaunchWindow"]

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.utils.bec_widget import BECWidget


class RPCWidgetHandler:
    """Handler class for creating widgets from RPC messages."""

    def __init__(self):
        self._widget_classes = None

    @property
    def widget_classes(self) -> dict[str, type["BECWidget"]]:
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
        ignored = set(IGNORE_WIDGETS)
        widget_classes = {
            reference.name: lazy_import_from(reference.module, (reference.name,))
            for reference in get_all_plugin_widget_references(use_cache=False)
            if reference.name not in ignored
        }
        widget_classes.update(
            {
                reference.name: lazy_import_from(reference.module, (reference.name,))
                for reference in get_custom_class_references(
                    "bec_widgets", packages=("widgets", "applications"), use_cache=False
                )
                if reference.name not in ignored
            }
        )
        self._widget_classes = widget_classes

    def create_widget(self, widget_type, **kwargs) -> "BECWidget":
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
