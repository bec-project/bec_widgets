from __future__ import annotations

from abc import abstractmethod
from typing import Callable

from bec_lib.logger import bec_logger
from qtpy.QtCore import QObject

logger = bec_logger.logger


class BundleConnection(QObject):
    """
    Base class for toolbar bundle connections.

    Provides infrastructure for bidirectional property-toolbar synchronization:
    - Toolbar actions → Widget properties (via action.triggered connections)
    - Widget properties → Toolbar actions (via property_changed signal)
    """

    bundle_name: str

    def __init__(self, parent=None):
        super().__init__(parent)
        self._property_sync_methods: dict[str, Callable] = {}
        self._property_sync_connected = False

    def register_property_sync(self, prop_name: str, sync_method: Callable):
        """
        Register a method to synchronize toolbar state when a property changes.

        This enables automatic toolbar updates when properties are set programmatically,
        restored from QSettings, or changed via RPC.

        Args:
            prop_name: The property name to watch (e.g., "fft", "log", "x_grid")
            sync_method: Method to call when property changes. Should accept the new value
                        and update toolbar state (typically with signals blocked to prevent loops)

        Example:
            def _sync_fft_toolbar(self, value: bool):
                self.fft_action.blockSignals(True)
                self.fft_action.setChecked(value)
                self.fft_action.blockSignals(False)

            self.register_property_sync("fft", self._sync_fft_toolbar)
        """
        self._property_sync_methods[prop_name] = sync_method

    def _resolve_action(self, action_like):
        if hasattr(action_like, "action"):
            return action_like.action
        return action_like

    def register_checked_action_sync(self, prop_name: str, action_like):
        """
        Register a property sync for a checkable QAction (or wrapper with .action).

        This reduces boilerplate for simple boolean → checked state updates.
        """
        qt_action = self._resolve_action(action_like)

        def _sync_checked(value):
            qt_action.blockSignals(True)
            try:
                qt_action.setChecked(bool(value))
            finally:
                qt_action.blockSignals(False)

        self.register_property_sync(prop_name, _sync_checked)

    def connect_property_sync(self, target_widget):
        """
        Connect to target widget's property_changed signal for automatic toolbar sync.

        Call this in your connect() method after registering all property syncs.

        Args:
            target_widget: The widget to monitor for property changes
        """
        if self._property_sync_connected:
            return

        if hasattr(target_widget, "property_changed"):
            target_widget.property_changed.connect(self._on_property_changed)
            self._property_sync_connected = True
        else:
            logger.warning(
                f"{target_widget.__class__.__name__} does not have property_changed signal. "
                "Property-toolbar sync will not work."
            )

    def disconnect_property_sync(self, target_widget):
        """
        Disconnect from target widget's property_changed signal.

        Call this in your disconnect() method.

        Args:
            target_widget: The widget to stop monitoring
        """
        if not self._property_sync_connected:
            return

        if hasattr(target_widget, "property_changed"):
            try:
                target_widget.property_changed.disconnect(self._on_property_changed)
            except (RuntimeError, TypeError):
                # Signal already disconnected or connection doesn't exist
                pass
            self._property_sync_connected = False

    def _on_property_changed(self, prop_name: str, value):
        """
        Internal handler for property changes.

        Calls the registered sync method for the changed property.
        """
        if prop_name in self._property_sync_methods:
            try:
                self._property_sync_methods[prop_name](value)
            except Exception as e:
                logger.error(
                    f"Error syncing toolbar for property '{prop_name}': {e}", exc_info=True
                )

    @abstractmethod
    def connect(self):
        """
        Connects the bundle to the target widget or application.
        This method should be implemented by subclasses to define how the bundle interacts with the target.

        Subclasses should call connect_property_sync(target_widget) if property sync is needed.
        """

    @abstractmethod
    def disconnect(self):
        """
        Disconnects the bundle from the target widget or application.
        This method should be implemented by subclasses to define how to clean up connections.

        Subclasses should call disconnect_property_sync(target_widget) if property sync was connected.
        """
