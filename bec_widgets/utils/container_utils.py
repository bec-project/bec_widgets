from __future__ import annotations

from typing import Any, Type

from qtpy.QtWidgets import QWidget

from bec_widgets.cli.client_utils import BECGuiClient


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

    @staticmethod
    def name_is_protected(name: str, container: Any = None) -> bool:
        """
        Check if the name is not protected.

        Args:
            name(str): The name to be checked.

        Returns:
            bool: True if the name is not protected, False otherwise.
        """
        if container is None:
            container = BECGuiClient
        gui_client_methods = set(filter(lambda x: not x.startswith("_"), dir(container)))
        return name in gui_client_methods

    @staticmethod
    def raise_for_invalid_name(name: str, container: Any = None) -> None:
        """
        Check if the name is valid. If not, raise a ValueError.

        Args:
            name(str): The name to be checked.
        Raises:
            ValueError: If the name is not valid.
        """
        if not WidgetContainerUtils.has_name_valid_chars(name):
            raise ValueError(
                f"Name '{name}' contains invalid characters. Only alphanumeric characters, underscores, and dashes are allowed."
            )
        if WidgetContainerUtils.name_is_protected(name, container):
            raise ValueError(f"Name '{name}' is protected. Please choose another name.")
