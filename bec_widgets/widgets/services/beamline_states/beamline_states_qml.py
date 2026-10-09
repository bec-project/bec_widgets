"""Beamline state manager rendered with Qt Quick (QML), same API as :class:`BeamlineStateManager`."""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Property, QObject, Signal, Slot
from qtpy.QtWidgets import QVBoxLayout

from bec_widgets.utils.quick import DictListModel, create_quick_widget, release_quick_widget
from bec_widgets.widgets.services.beamline_states.beamline_states_ux_common import (
    BeamlineStatesPortBase,
)

QML_FILE = Path(__file__).parent / "qml" / "BeamlineStatesView.qml"

ROW_ROLES = [
    "kind",
    "key",
    "name",
    "label",
    "status",
    "statusText",
    "tone",
    "icon",
    "device",
    "stateType",
    "params",
    "watched",
    "tripped",
    "armed",
    "acceptedText",
    "tripOnWarning",
    "expanded",
    "title",
    "count",
]


class BeamlineStatesBackend(QObject):
    """Bridge between :class:`BeamlineStatesQML` and ``BeamlineStatesView.qml``."""

    changed = Signal()

    def __init__(self, manager: "BeamlineStatesQML"):
        super().__init__(manager)
        self._manager = manager
        self._state: dict = {}
        self._rows = DictListModel(ROW_ROLES, self)

    def update_from(self, state: dict) -> None:
        """Take a new view state from the manager."""
        self._rows.set_items(state.pop("rows"))
        self._state = state
        self.changed.emit()

    # pylint: disable=invalid-name,missing-function-docstring
    @Slot(str)
    def toggleStatus(self, status: str) -> None:
        self._manager.toggle_status_filter(status)

    @Slot(str)
    def setFilterText(self, text: str) -> None:
        self._manager.set_filter_text(text)

    @Slot()
    def clearFilters(self) -> None:
        self._manager.clear_filters()

    @Slot()
    def addState(self) -> None:
        self._manager.open_add_state_dialog()

    @Slot(str)
    def toggleExpanded(self, name: str) -> None:
        self._manager.toggle_expanded(name)

    @Slot(str)
    def toggleInterlockFor(self, name: str) -> None:
        self._manager.toggle_interlock_for(name)

    @Slot(str, bool)
    def setTripOnWarning(self, name: str, trip: bool) -> None:
        self._manager.set_trip_on_warning(name, trip)

    @Slot(bool)
    def setInterlockEnabled(self, enabled: bool) -> None:
        self._manager.set_interlock_enabled(enabled)

    @Slot(str)
    def editState(self, name: str) -> None:
        self._manager.edit_state(name)

    @Slot(str)
    def removeState(self, name: str) -> None:
        self._manager.remove_state(name)

    @Slot(bool)
    def setShowHidden(self, show: bool) -> None:
        self._manager.set_show_hidden(show)

    state = Property("QVariantMap", lambda self: self._state, notify=changed)
    rows = Property(QObject, lambda self: self._rows, constant=True)


class BeamlineStatesQML(BeamlineStatesPortBase):
    """Beamline state manager with the modernised UX rendered in QML."""

    def _init_view(self) -> None:
        self.backend = BeamlineStatesBackend(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = create_quick_widget(self, QML_FILE, {"backend": self.backend})
        self.view.setMinimumSize(320, 300)
        layout.addWidget(self.view)

    def _sync_view(self) -> None:
        if hasattr(self, "backend"):
            self.backend.update_from(self.view_state())

    def apply_theme(self, theme: str):
        super().apply_theme(theme)
        self.view.setClearColor(self.palette().window().color())

    def cleanup(self):
        release_quick_widget(self.view)
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    widget = BeamlineStatesQML()
    widget.resize(460, 560)
    widget.show()
    sys.exit(app.exec())
