"""Module to define a widget for the admin view."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bec_lib.endpoints import MessageEndpoints
from bec_lib.messages import DeploymentInfoMessage
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QSizePolicy, QStackedLayout, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.services.bec_atlas_admin_view.bec_atlas_admin_view import BECAtlasAdminView
from bec_widgets.widgets.services.bec_atlas_admin_view.experiment_selection.experiment_selection import (
    ExperimentSelection,
)


class AdminWidget(BECWidget, QWidget):
    """Widget for admin view."""

    RPC = False

    def __init__(self, parent=None, client=None):
        super().__init__(parent=parent, client=client)
        # Overview widget
        layout = QVBoxLayout(self)
        self.admin_view_widget = BECAtlasAdminView(parent=self, client=self.client)
        layout.addWidget(self.admin_view_widget)

    def on_enter(self) -> None:
        """Called after the widget becomes visible."""
        self.admin_view_widget.check_health()

    def on_exit(self) -> None:
        """Called before the widget is hidden."""
        self.admin_view_widget.logout()


if __name__ == "__main__":
    from bec_qthemes import apply_theme
    from qtpy.QtWidgets import QApplication

    from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

    app = QApplication([])

    apply_theme("dark")
    w = QWidget()
    l = QVBoxLayout(w)
    widget = AdminWidget(parent=w)
    dark_mode_button = DarkModeButton(parent=w)
    l.addWidget(dark_mode_button)
    l.addWidget(widget)
    w.show()
    app.exec()
