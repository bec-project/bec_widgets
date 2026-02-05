from __future__ import annotations

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.messages import BeamlineStateConfig
from qtpy.QtCore import QObject, QTimer, Signal

from bec_widgets.utils.bec_connector import BECConnector
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.toolbars.actions import StatusIndicatorAction, StatusState
from bec_widgets.utils.toolbars.toolbar import ModularToolBar

logger = bec_logger.logger


class BECStatusBroker(BECConnector, QObject):
    """Listen to BEC beamline state endpoints and emit structured signals."""

    _instance: "BECStatusBroker | None" = None
    _initialized: bool = False

    available_updated = Signal(list)  # list of states available
    status_updated = Signal(str, dict)  # name, status update

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, parent=None, gui_id: str | None = None, client=None, **kwargs):
        if self._initialized:
            return
        super().__init__(parent=parent, gui_id=gui_id, client=client, **kwargs)
        self._watched: set[str] = set()
        self.bec_dispatcher.connect_slot(
            self.on_available, MessageEndpoints.available_beamline_states()
        )

        self._initialized = True
        self.refresh_available()

    def refresh_available(self):
        """Fetch the current set of beamline conditions once."""
        try:
            msg = self.client.connector.get_last(MessageEndpoints.available_beamline_states())
            logger.info(f"StatusBroker: fetched available conditions payload: {msg}")
            if msg:
                self.on_available(msg.get("data").content, None)
        except Exception as exc:  # pragma: no cover - runtime env
            logger.debug(f"Could not fetch available conditions: {exc}")

    @SafeSlot(dict, dict)
    def on_available(self, data: dict, meta: dict | None = None):
        state_list = data.get("states")  # latest one from the stream
        self.available_updated.emit(state_list)
        for state in state_list:
            name = state.name
            if name:
                self.watch_state(name)

    def watch_state(self, name: str):
        """Subscribe to updates for a single beamline state."""
        if name in self._watched:
            return
        self._watched.add(name)
        endpoint = MessageEndpoints.beamline_state(name)
        logger.info(f"StatusBroker: watching state '{name}' on {endpoint.endpoint}")
        self.bec_dispatcher.connect_slot(self.on_state, endpoint)
        self.fetch_state(name)

    def fetch_state(self, name: str):
        """Fetch the current value of a beamline state once."""
        endpoint = MessageEndpoints.beamline_state(name)
        try:
            msg = self.client.connector.get_last(endpoint)
            logger.info(f"StatusBroker: fetched state '{name}' payload: {msg}")
            if msg:
                self.on_state(msg.get("data").content, None)
        except Exception as exc:  # pragma: no cover - runtime env
            logger.debug(f"Could not fetch state {name}: {exc}")

    @SafeSlot(dict, dict)
    def on_state(self, data: dict, meta: dict | None = None):
        name = data.get("name")
        if not name:
            return
        logger.info(f"StatusBroker: state update for '{name}' -> {data}")
        self.status_updated.emit(str(name), data)

    @classmethod
    def reset_singleton(cls):
        """
        Reset the singleton instance of the BECStatusBroker.
        """
        cls._instance = None
        cls._initialized = False


class StatusToolBar(ModularToolBar):
    """Status toolbar that auto-manages beamline state indicators."""

    STATUS_MAP: dict[str, StatusState] = {
        "valid": StatusState.SUCCESS,
        "warning": StatusState.WARNING,
        "invalid": StatusState.EMERGENCY,
    }

    def __init__(self, parent=None, names: list[str] | None = None, **kwargs):
        super().__init__(parent=parent, orientation="horizontal", **kwargs)
        self.setObjectName("StatusToolbar")
        self._status_bundle = self.new_bundle("status")
        self.show_bundles(["status"])
        self._apply_status_toolbar_style()

        self.allowed_names: set[str] | None = set(names) if names is not None else None
        logger.info(f"StatusToolbar init allowed_names={self.allowed_names}")

        self.broker = BECStatusBroker()
        self.broker.available_updated.connect(self.on_available_updated)
        self.broker.status_updated.connect(self.on_status_updated)

        QTimer.singleShot(0, self.refresh_from_broker)

    def refresh_from_broker(self) -> None:

        if self.allowed_names is None:
            self.broker.refresh_available()
        else:
            for name in self.allowed_names:
                if not self.components.exists(name):
                    # Pre-create a placeholder pill so it is visible even before data arrives.
                    self.add_status_item(
                        name=name, text=name, state=StatusState.DEFAULT, tooltip=None
                    )
                self.broker.watch_state(name)

    def _apply_status_toolbar_style(self) -> None:
        self.setStyleSheet(
            "QToolBar#StatusToolbar {"
            f" background-color: {self.background_color};"
            " border: none;"
            " border-bottom: 1px solid palette(mid);"
            "}"
        )

    # -------- Slots for updates --------
    @SafeSlot(list)
    def on_available_updated(self, available_states: list):
        """Process the available states stream and start watching them."""
        # Keep track of current names from the broker to remove stale ones.
        current_names: set[str] = set()
        for state in available_states:
            if not isinstance(state, BeamlineStateConfig):
                continue
            name = state.name
            title = state.title or name
            if not name:
                continue
            current_names.add(name)
            logger.info(f"StatusToolbar: discovered state '{name}' title='{title}'")
            # auto-add unless filtered out
            if self.allowed_names is None or name in self.allowed_names:
                self.add_status_item(name=name, text=title, state=StatusState.DEFAULT, tooltip=None)
            else:
                # keep hidden but present for context menu toggling
                self.add_status_item(name=name, text=title, state=StatusState.DEFAULT, tooltip=None)
                act = self.components.get_action(name)
                if act and act.action:
                    act.action.setVisible(False)

        # Remove actions that are no longer present in available_states.
        known_actions = [
            n for n in self.components._components.keys() if n not in ("separator",)
        ]  # direct access used for clean-up
        for name in known_actions:
            if name not in current_names:
                logger.info(f"StatusToolbar: removing stale state '{name}'")
                try:
                    self.components.remove_action(name)
                except Exception as exc:
                    logger.warning(f"Failed to remove stale state '{name}': {exc}")
        self.refresh()

    @SafeSlot(str, dict)
    def on_status_updated(self, name: str, payload: dict):  # TODO finish update logic
        """Update a status pill when a state update arrives."""
        state = self.STATUS_MAP.get(str(payload.get("status", "")).lower(), StatusState.DEFAULT)
        action = self.components.get_action(name) if self.components.exists(name) else None

        # Only update the label when a title is explicitly provided; otherwise keep current text.
        title = payload.get("title") or None
        text = title
        if text is None and action is None:
            text = payload.get("name") or name

        if "label" in payload:
            tooltip = payload.get("label") or ""
        else:
            tooltip = None
        logger.info(
            f"StatusToolbar: update state '{name}' -> state={state} text='{text}' tooltip='{tooltip}'"
        )
        self.set_status(name=name, text=text, state=state, tooltip=tooltip)

    # -------- Items Management --------
    def add_status_item(
        self,
        name: str,
        *,
        text: str = "Ready",
        state: StatusState | str = StatusState.DEFAULT,
        tooltip: str | None = None,
    ) -> StatusIndicatorAction | None:
        """
        Add or update a named status item in the toolbar.
        After you added all actions, call `toolbar.refresh()` to update the display.

        Args:
            name(str): Unique name for the status item.
            text(str): Text to display in the status item.
            state(StatusState | str): State of the status item.
            tooltip(str | None): Optional tooltip for the status item.

        Returns:
            StatusIndicatorAction | None: The created or updated status action, or None if toolbar is not initialized.
        """
        if self._status_bundle is None:
            return
        if self.components.exists(name):
            return

        action = StatusIndicatorAction(text=text, state=state, tooltip=tooltip)
        return self.add_status_action(name, action)

    def add_status_action(
        self, name: str, action: StatusIndicatorAction
    ) -> StatusIndicatorAction | None:
        """
        Attach an existing StatusIndicatorAction to the status toolbar.
        After you added all actions, call `toolbar.refresh()` to update the display.

        Args:
            name(str): Unique name for the status item.
            action(StatusIndicatorAction): The status action to add.

        Returns:
            StatusIndicatorAction | None: The added status action, or None if toolbar is not initialized.
        """
        self.components.add_safe(name, action)
        self.get_bundle("status").add_action(name)
        self.refresh()
        self.broker.fetch_state(name)
        return action

    def set_status(
        self,
        name: str = "main",
        *,
        state: StatusState | str | None = None,
        text: str | None = None,
        tooltip: str | None = None,
    ) -> None:
        """
        Update the status item with the given name, creating it if necessary.

        Args:
            name(str): Unique name for the status item.
            state(StatusState | str | None): New state for the status item.
            text(str | None): New text for the status item.
        """
        action = self.components.get_action(name) if self.components.exists(name) else None
        if action is None:
            action = self.add_status_item(
                name, text=text or "Ready", state=state or "default", tooltip=tooltip
            )
        if action is None:
            return
        if state is not None:
            action.set_state(state)
        if text is not None:
            action.set_text(text)
        if tooltip is not None and hasattr(action, "set_tooltip"):
            action.set_tooltip(tooltip)
