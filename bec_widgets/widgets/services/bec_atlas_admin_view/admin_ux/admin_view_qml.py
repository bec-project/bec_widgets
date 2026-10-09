"""Admin view rendered with Qt Quick (QML).

Same UX as :mod:`admin_view_qwidget`; the state comes from
:class:`~.admin_ux_common.AdminViewBase`.
"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Property, QObject, Signal, Slot
from qtpy.QtWidgets import QVBoxLayout

from bec_widgets.utils.quick import DictListModel, create_quick_widget, release_quick_widget
from bec_widgets.widgets.services.bec_atlas_admin_view.admin_ux.admin_ux_common import (
    DEFAULT_ATLAS_URL,
    HOW_IT_WORKS,
    AdminViewBase,
)

QML_DIR = Path(__file__).parent / "qml"

ROW_ROLES = ["pgroup", "title", "pi", "beamtime", "status", "statusLabel", "isActive", "isNext"]


class AdminBackend(QObject):
    """Bridge between :class:`AdminViewQML` and ``AdminView.qml``."""

    changed = Signal()

    def __init__(self, view: AdminViewQML):
        super().__init__(view)
        self._view = view
        self._state: dict = {}
        self._rows = DictListModel(ROW_ROLES, self)

    def update_from(self, state: dict) -> None:
        """Take a new view state from the widget."""
        state = dict(state)
        rows = state.pop("rows")
        if [r["pgroup"] for r in rows] != [r["pgroup"] for r in self._rows.items] or any(
            new["status"] != old["status"] for new, old in zip(rows, self._rows.items)
        ):
            self._rows.set_items([{key: row[key] for key in ROW_ROLES} for row in rows])
        state["rowCount"] = len(rows)
        state["howItWorks"] = HOW_IT_WORKS
        self._state = state
        self.changed.emit()

    # pylint: disable=invalid-name,missing-function-docstring
    @Slot(str, str)
    def login(self, username: str, password: str) -> None:
        self._view.login(username.strip(), password)

    @Slot()
    def logout(self) -> None:
        self._view.logout()

    @Slot(str)
    def openSection(self, section: str) -> None:
        self._view.open_section(section)

    @Slot(str)
    def setQuery(self, query: str) -> None:
        self._view.set_query(query)

    @Slot(str)
    def setScope(self, scope: str) -> None:
        self._view.set_scope(scope)

    @Slot(str)
    def selectExperiment(self, pgroup: str) -> None:
        self._view.select_experiment(pgroup)

    @Slot(str)
    def startSwitch(self, pgroup: str) -> None:
        self._view.start_switch(pgroup)

    @Slot()
    def next(self) -> None:
        self._view.wizard_next()

    @Slot()
    def back(self) -> None:
        self._view.wizard_back()

    @Slot(bool)
    def setAcknowledged(self, value: bool) -> None:
        self._view.set_acknowledged(value)

    @Slot()
    def confirm(self) -> None:
        self._view.confirm_switch()

    @Slot()
    def closeWizard(self) -> None:
        self._view.close_wizard()

    def _get_state(self) -> dict:
        return self._state

    def _get_rows(self) -> DictListModel:
        return self._rows

    state = Property("QVariantMap", _get_state, notify=changed)
    rows = Property(QObject, _get_rows, constant=True)


class AdminViewQML(AdminViewBase):
    """Admin view: sign in, see the active experiment and switch it with step-by-step guidance."""

    def __init__(self, parent=None, atlas_url: str = DEFAULT_ATLAS_URL, client=None, **kwargs):
        self.backend = None
        self.view = None
        super().__init__(parent=parent, atlas_url=atlas_url, client=client, **kwargs)
        self.backend = AdminBackend(self)
        self.backend.update_from(self.view_state())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = create_quick_widget(self, QML_DIR / "AdminView.qml", {"backend": self.backend})
        layout.addWidget(self.view)

    def _render(self, state: dict) -> None:
        if self.backend is not None:
            self.backend.update_from(state)

    def apply_theme(self, theme: str):
        """Match the QML clear colour to the new theme."""
        if self.view is not None:
            self.view.setClearColor(self.palette().window().color())

    def cleanup(self):
        """Unload the QML scene before the backend goes away."""
        release_quick_widget(self.view)
        super().cleanup()
