"""Module to define a widget for the admin view."""

from __future__ import annotations

from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.services.bec_atlas_admin_view.bec_atlas_admin_view import BECAtlasAdminView


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

    def on_exit(self) -> None:
        """Called before the widget is hidden."""
        self.admin_view_widget.logout()


# pylint: disable=ungrouped-imports
if __name__ == "__main__":  # pragma: no cover
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
