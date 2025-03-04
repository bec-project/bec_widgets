from __future__ import annotations

import itertools
from typing import Literal, Type

from qtpy.QtWidgets import QWidget

from bec_widgets.cli.rpc.rpc_register import RPCRegister


class WidgetContainerUtils:

    # We need one handler that checks if a WIDGET of a given name is already created for that DOCKAREA
    # 1. If the name exists, then it depends whether the name was auto-generated -> add _1 to the name
    #    or alternatively raise an error that it can't be added again ( just raise an error)
    # 2. Dock names in between docks should also be unique

    @staticmethod
    def has_name_valid_chars(name: str) -> bool:
        """Check if the name is valid.

        Args:
            name(str): The name to be checked.

        Returns:
            bool: True if the name is valid, False otherwise.
        """
        if not name or len(name) > 256:
            return False  # Don't accept empty names or names longer than 256 characters
        check_value = name.replace("_", "").replace("-", "")
        if not check_value.isalnum() or not check_value.isascii():
            return False
        return True

    @staticmethod
    def generate_unique_name(name: str, list_of_names: list[str] | None = None) -> str:
        """Generate a unique ID.

        Args:
            name(str): The name of the widget.
        Returns:
            tuple (str): The unique name
        """
        if list_of_names is None:
            list_of_names = []
        ii = 0
        while ii < 1000:  # 1000 is arbritrary!
            name_candidate = f"{name}_{ii}"
            if name_candidate not in list_of_names:
                return name_candidate
            ii += 1
        raise ValueError("Could not generate a unique name after within 1000 attempts.")

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
