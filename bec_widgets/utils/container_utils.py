from __future__ import annotations

import itertools
from typing import Type

from qtpy.QtWidgets import QWidget


class WidgetContainerUtils:

    @staticmethod
    def generate_unique_widget_id(container: dict, prefix: str = "widget") -> str:
        """
        Generate a unique widget ID.

        Args:
            container(dict): The container of widgets.
            prefix(str): The prefix of the widget ID.

        Returns:
            widget_id(str): The unique widget ID.
        """
        existing_ids = set(container.keys())
        for i in itertools.count(1):
            widget_id = f"{prefix}_{i}"
            if widget_id not in existing_ids:
                return widget_id

    @staticmethod
    def find_first_widget_by_class(
        container: dict, widget_class: Type[QWidget], can_fail: bool = True
    ) -> QWidget | None:
        """
        Find the first widget of a given class in the figure.

        Args:
            container(dict): The container of widgets.
            widget_class(Type): The class of the widget to find.
            can_fail(bool): If True, the method will return None if no widget is found. If False, it will raise an error.

        Returns:
            widget: The widget of the given class.
        """
        for widget_id, widget in container.items():
            if isinstance(widget, widget_class):
                return widget
        if can_fail:
            return None
        else:
            raise ValueError(f"No widget of class {widget_class} found.")
