"""Module to define a widget for the admin view."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bec_lib.endpoints import MessageEndpoints
from bec_lib.messages import DeploymentInfoMessage
from qtpy.QtWidgets import QStackedLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot


class AdminWidget(BECWidget, QWidget):
    """Widget for admin view."""

    RPC = False

    def __init__(self, parent=None, client=None):
        super().__init__(parent=parent, client=client)
        self._current_deployment_info: DeploymentInfoMessage | None = None

        self.stacked_layout = QStackedLayout()
        self.stacked_layout.setContentsMargins(0, 0, 0, 0)
        self.stacked_layout.setSpacing(0)
        self.stacked_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        self.setLayout(self.stacked_layout)

        self.bec_dispatcher.connect_slot(
            slot=self._update_deployment_info,
            endpoint=MessageEndpoints.deployment_info(),
            from_start=True,
        )

    @SafeSlot(dict, dict)
    def _update_deployment_info(self, msg: dict, metadata: dict) -> None:
        """Fetch current deployment info from the server."""
        deployment = DeploymentInfoMessage.model_validate(msg)
        self._current_deployment_info = deployment
