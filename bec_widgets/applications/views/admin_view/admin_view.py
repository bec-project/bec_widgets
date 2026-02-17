"""Module for Admin View."""

from qtpy.QtWidgets import QWidget

from bec_widgets.applications.views.admin_view.admin_widget import AdminWidget
from bec_widgets.applications.views.view import ViewBase
from bec_widgets.utils.error_popups import SafeSlot


class AdminView(ViewBase):
    """
    A view for administrators to change the current active experiment, manage messaging
    services, and more tasks reserved for users with admin privileges.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        content: QWidget | None = None,
        *,
        id: str | None = None,
        title: str | None = None,
    ):
        super().__init__(parent=parent, content=content, id=id, title=title)
        self.admin_widget = AdminWidget(parent=self)
        self.set_content(self.admin_widget)

    @SafeSlot()
    def on_enter(self) -> None:
        """Called after the view becomes current/visible.

        Default implementation does nothing. Override in subclasses.
        """
        self.admin_widget.on_enter()

    @SafeSlot()
    def on_exit(self) -> None:
        """Called before the view is hidden.

        Default implementation does nothing. Override in subclasses.
        """
        self.admin_widget.on_exit()
