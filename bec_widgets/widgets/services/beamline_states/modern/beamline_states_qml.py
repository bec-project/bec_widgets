"""Beamline states view rendered with QML, hosted in a ``QQuickWidget``."""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import QMetaObject, QUrl
from qtpy.QtWidgets import QMessageBox, QVBoxLayout, QWidget

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.qml_host import create_quick_widget
from bec_widgets.widgets.services.beamline_states.modern.actions import (
    open_add_dialog,
    open_edit_dialog,
)
from bec_widgets.widgets.services.beamline_states.modern.states_controller import (
    BeamlineStatesController,
)

QML_FILE = Path(__file__).parent / "qml" / "BeamlineStates.qml"


class BeamlineStatesQML(BECWidget, QWidget):
    """
    Beamline states with the scan interlock, rendered in QML.

    Prototype for comparison with :class:`BeamlineStatesWidget` (same UX in QWidgets) and the
    original ``BeamlineStateManager``.
    """

    PLUGIN = False
    RPC = False
    ICON_NAME = "format_list_bulleted"
    USER_ACCESS = ["clear_filters", "collapse_all", "state_summary", "remove", "attach", "detach"]

    def __init__(
        self,
        parent: QWidget | None = None,
        client=None,
        config: ConnectionConfig | None = None,
        gui_id: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(parent=parent, client=client, config=config, gui_id=gui_id, **kwargs)
        self.controller = BeamlineStatesController(self.client, self.bec_dispatcher, self)
        self.controller.error_occurred.connect(self._show_error)
        self.controller.add_requested.connect(self._open_add_dialog)
        self.controller.edit_requested.connect(self._open_edit_dialog)
        self.view = create_quick_widget(
            self, QML_FILE, {"controller": self.controller, "statesModel": self.controller.model}
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

    @SafeSlot()
    def clear_filters(self) -> None:
        """Reset the status chips and the search text."""
        self.controller.clearFilters()

    @SafeSlot()
    def collapse_all(self) -> None:
        """Collapse every expanded state."""
        QMetaObject.invokeMethod(self.view.rootObject(), "collapseAll")

    def state_summary(self) -> dict[str, dict[str, str]]:
        """
        Return all beamline states (including filtered ones) with their current status and label.

        Returns:
            dict: Mapping of state name to a dictionary with ``status`` and ``label`` keys.
        """
        return self.controller.state_summary()

    @SafeSlot(str, str)
    def _show_error(self, title: str, text: str) -> None:
        QMessageBox.warning(self, title, text)

    @SafeSlot()
    def _open_add_dialog(self) -> None:
        open_add_dialog(self, self.controller)

    @SafeSlot(str)
    def _open_edit_dialog(self, name: str) -> None:
        open_edit_dialog(self, self.controller, name)

    def cleanup(self) -> None:
        self.controller.cleanup()
        self.view.setSource(QUrl())
        super().cleanup()
