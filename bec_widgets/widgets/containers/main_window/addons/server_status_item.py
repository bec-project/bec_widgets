"""
The BEC server pill for the main window status bar: an icon for the overall state of the core
services with the label "BEC", the number of core services that are down, and the full
BECStatusBox in a card that opens on hover.
"""

from __future__ import annotations

from typing import Callable

from qtpy.QtCore import QSettings
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.hover_card import HoverCard
from bec_widgets.widgets.containers.main_window.addons.status_pill import (
    PillStyle,
    StatusPillItem,
    ToolIndicator,
    ToolSeverity,
)
from bec_widgets.widgets.services.bec_status_box.bec_status_box import BECStatusBox
from bec_widgets.widgets.services.bec_status_box.status_model import (
    RestartState,
    ServiceStatusModel,
)

SETTINGS_PREFIX = "server_status"


def server_indicator(model: ServiceStatusModel) -> ToolIndicator:
    """
    The pill indicator for the status box model: the overall state, or the restart progress while
    a restart runs. The summary is the full state line, for the tooltip and screen readers; the
    pill itself only reads "BEC".

    Args:
        model(ServiceStatusModel): The model of the status box.
    """
    down = model.services_down
    tooltip = f"{model.headline}\n{model.detail}".strip()
    badge = f"{down} down" if down else None
    state = model.restart_state
    if state != RestartState.NONE:
        severity = {
            RestartState.RUNNING: ToolSeverity.INFO,
            RestartState.DONE: ToolSeverity.OK,
        }.get(state, ToolSeverity.CRITICAL)
        return ToolIndicator(
            severity=severity,
            summary=model.restart_text,
            badge=badge,
            tooltip=f"{model.restart_text}\n{model.detail}".strip(),
            active=state == RestartState.RUNNING,
        )
    return ToolIndicator(
        severity=model.severity,
        summary=model.headline,
        badge=badge,
        attention=bool(down),
        tooltip=tooltip,
    )


class ServerStatusCard(HoverCard):
    """The hover card of the server pill, with the full BECStatusBox."""

    def __init__(self, owner: "ServerStatusItem"):
        super().__init__(owner, width=380, object_name="server_status_card")
        self.status_box = BECStatusBox(
            parent=self.card, client=owner.client, rpc_exposed=False, rpc_passthrough_children=False
        )
        self.status_box.setMinimumHeight(400)
        self.set_content(self.status_box)


class ServerStatusItem(StatusPillItem):
    """
    Status-bar pill with the overall state of the BEC server, with the full BECStatusBox on hover.

    The status box in the card is the only source of the state: its model drives both the pill
    and the card. The pill is the compact icon style (the state icon and "BEC"); the large size is
    chosen in its right-click menu and saved per user.
    """

    PILL_STYLE = PillStyle.ICON
    PILL_LABEL = "BEC"
    DOCK_WIDGET = "BECStatusBox"

    def __init__(
        self,
        parent: QWidget | None = None,
        client=None,
        settings: Callable[[], QSettings] | None = None,
        **kwargs,
    ):
        super().__init__(
            parent=parent,
            client=client,
            settings=settings,
            settings_prefix=SETTINGS_PREFIX,
            **kwargs,
        )
        self.status_box = self.card.status_box
        self.model = self.status_box.model
        self.model.summary_changed.connect(self._update_indicator)
        self.model.rows_changed.connect(self._update_indicator)
        self.model.restart_changed.connect(self._update_indicator)
        # the status box shares one poller with all boxes and pills of the client; the pill counts
        # as a viewer only while it is shown, not in hidden windows like the launcher
        self.poller = self.status_box.bec_service_status
        self.apply_sizes()
        self._update_indicator()

    def create_card(self) -> HoverCard:
        return ServerStatusCard(self)

    @SafeSlot()
    def _update_indicator(self) -> None:
        self.set_indicator(server_indicator(self.model))

    def pill_text(self) -> str:
        """The pill label; the state is the icon, the tooltip and the card header."""
        return self.PILL_LABEL

    def showEvent(self, event):  # pylint: disable=invalid-name
        super().showEvent(event)
        self.poller.add_viewer(self)

    def hideEvent(self, event):  # pylint: disable=invalid-name
        super().hideEvent(event)
        self.poller.remove_viewer(self)

    def cleanup(self):
        """Stop being a viewer of the poller, close the card's status box, then the pill."""
        self.poller.remove_viewer(self)
        self.status_box.close()
        super().cleanup()
