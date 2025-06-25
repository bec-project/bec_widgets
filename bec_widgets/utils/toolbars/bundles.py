from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, DefaultDict
from weakref import ReferenceType

import louie
from bec_lib.logger import bec_logger
from pydantic import BaseModel

from bec_widgets.utils.toolbars.actions import SeparatorAction, ToolBarAction

if TYPE_CHECKING:
    from bec_widgets.utils.toolbars.connections import BundleConnection
    from bec_widgets.utils.toolbars.toolbar import ModularToolBar

logger = bec_logger.logger


class ActionInfo(BaseModel):
    action: ToolBarAction
    toolbar_bundle: ToolbarBundle | None = None

    model_config = {"arbitrary_types_allowed": True}


class ToolbarComponents:
    def __init__(self, toolbar: ModularToolBar):
        """
        Initializes the toolbar components.

        Args:
            toolbar (ModularToolBar): The toolbar to which the components will be added.
        """
        self.toolbar = toolbar

        self._components: dict[str, ActionInfo] = {}
        self.add("separator", SeparatorAction())

    def add(self, name: str, component: ToolBarAction):
        """
        Adds a component to the toolbar.

        Args:
            component (ToolBarAction): The component to add.
        """
        if name in self._components:
            raise ValueError(f"Component with name '{name}' already exists.")
        self._components[name] = ActionInfo(action=component, toolbar_bundle=None)

    def add_safe(self, name: str, component: ToolBarAction):
        """
        Adds a component to the toolbar, ensuring it does not already exist.

        Args:
            name (str): The name of the component.
            component (ToolBarAction): The component to add.
        """
        if self.exists(name):
            logger.info(f"Component with name '{name}' already exists. Skipping addition.")
            return
        self.add(name, component)

    def exists(self, name: str) -> bool:
        """
        Checks if a component exists in the toolbar.

        Args:
            name (str): The name of the component to check.

        Returns:
            bool: True if the component exists, False otherwise.
        """
        return name in self._components

    def get_action_reference(self, name: str) -> ReferenceType[ToolBarAction]:
        """
        Retrieves a component by name.

        Args:
            name (str): The name of the component to retrieve.

        """
        if not self.exists(name):
            raise KeyError(f"Component with name '{name}' does not exist.")
        return louie.saferef.safe_ref(self._components[name].action)

    def get_action(self, name: str) -> ToolBarAction:
        """
        Retrieves a component by name.

        Args:
            name (str): The name of the component to retrieve.

        Returns:
            ToolBarAction: The action associated with the given name.
        """
        if not self.exists(name):
            raise KeyError(
                f"Component with name '{name}' does not exist. The following components are available: {list(self._components.keys())}"
            )
        return self._components[name].action

    def set_bundle(self, name: str, bundle: ToolbarBundle):
        """
        Sets the bundle for a component.

        Args:
            name (str): The name of the component.
            bundle (ToolbarBundle): The bundle to set.
        """
        if not self.exists(name):
            raise KeyError(f"Component with name '{name}' does not exist.")
        comp = self._components[name]
        if comp.toolbar_bundle is not None:
            logger.info(
                f"Component '{name}' already has a bundle ({comp.toolbar_bundle.name}). Setting it to {bundle.name}."
            )
            comp.toolbar_bundle.bundle_actions.pop(name, None)
        comp.toolbar_bundle = bundle

    def remove_action(self, name: str):
        """
        Removes a component from the toolbar.

        Args:
            name (str): The name of the component to remove.
        """
        if not self.exists(name):
            raise KeyError(f"Action with ID '{name}' does not exist.")
        action_info = self._components.pop(name)
        if action_info.toolbar_bundle:
            action_info.toolbar_bundle.bundle_actions.pop(name, None)
            self.toolbar.refresh()
            action_info.toolbar_bundle = None
        if hasattr(action_info.action, "cleanup"):
            # Call cleanup if the action has a cleanup method
            action_info.action.cleanup()

    def cleanup(self):
        """
        Cleans up the toolbar components by removing all actions and bundles.
        """
        for action_info in self._components.values():
            if hasattr(action_info.action, "cleanup"):
                # Call cleanup if the action has a cleanup method
                action_info.action.cleanup()
        self._components.clear()


class ToolbarBundle:
    def __init__(self, name: str, components: ToolbarComponents):
        """
        Initializes a new bundle component.

        Args:
            bundle_name (str): Unique identifier for the bundle.
        """
        self.name = name
        self.components = components
        self.bundle_actions: DefaultDict[str, ReferenceType[ToolBarAction]] = defaultdict()
        self._connections: dict[str, BundleConnection] = {}

    def add_action(self, name: str):
        """
        Adds an action to the bundle.

        Args:
            name (str): Unique identifier for the action.
            action (ToolBarAction): The action to add.
        """
        if name in self.bundle_actions:
            raise ValueError(f"Action with name '{name}' already exists in bundle '{self.name}'.")
        if not self.components.exists(name):
            raise ValueError(
                f"Component with name '{name}' does not exist in the toolbar. Please add it first using the `ToolbarComponents.add` method."
            )
        self.bundle_actions[name] = self.components.get_action_reference(name)
        self.components.set_bundle(name, self)

    def remove_action(self, name: str):
        """
        Removes an action from the bundle.

        Args:
            name (str): The name of the action to remove.
        """
        if name not in self.bundle_actions:
            raise KeyError(f"Action with name '{name}' does not exist in bundle '{self.name}'.")
        del self.bundle_actions[name]

    def add_separator(self):
        """
        Adds a separator action to the bundle.
        """
        self.add_action("separator")

    def add_connection(self, name: str, connection):
        """
        Adds a connection to the bundle.

        Args:
            name (str): Unique identifier for the connection.
            connection: The connection to add.
        """
        if name in self._connections:
            raise ValueError(
                f"Connection with name '{name}' already exists in bundle '{self.name}'."
            )
        self._connections[name] = connection

    def remove_connection(self, name: str):
        """
        Removes a connection from the bundle.

        Args:
            name (str): The name of the connection to remove.
        """
        if name not in self._connections:
            raise KeyError(f"Connection with name '{name}' does not exist in bundle '{self.name}'.")
        self._connections[name].disconnect()
        del self._connections[name]

    def get_connection(self, name: str):
        """
        Retrieves a connection by name.

        Args:
            name (str): The name of the connection to retrieve.

        Returns:
            The connection associated with the given name.
        """
        if name not in self._connections:
            raise KeyError(f"Connection with name '{name}' does not exist in bundle '{self.name}'.")
        return self._connections[name]

    def disconnect(self):
        """
        Disconnects all connections in the bundle.
        """
        for connection in self._connections.values():
            connection.disconnect()
        self._connections.clear()
