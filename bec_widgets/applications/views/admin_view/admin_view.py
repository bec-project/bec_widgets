"""Module for Admin View."""

import os

from qtpy.QtWidgets import QWidget

from bec_widgets.applications.views.view import ViewBase
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.services.bec_atlas_admin_view.bec_atlas_admin_view import BECAtlasAdminView

ADMIN_UI_ENV = "BEC_ADMIN_UI"


def create_admin_widget(parent: QWidget | None = None) -> QWidget:
    """Create the admin panel selected by ``BEC_ADMIN_UI``.

    ``qml`` and ``qwidget`` select the reworked view with the guided experiment switch; anything
    else keeps the current :class:`BECAtlasAdminView`.
    """
    choice = os.environ.get(ADMIN_UI_ENV, "").strip().lower()
    if choice == "qml":
        # pylint: disable=import-outside-toplevel
        from bec_widgets.widgets.services.bec_atlas_admin_view.admin_ux.admin_view_qml import (
            AdminViewQML,
        )

        return AdminViewQML(parent=parent)
    if choice == "qwidget":
        # pylint: disable=import-outside-toplevel
        from bec_widgets.widgets.services.bec_atlas_admin_view.admin_ux.admin_view_qwidget import (
            AdminViewQWidget,
        )

        return AdminViewQWidget(parent=parent)
    return BECAtlasAdminView(parent=parent)


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
        view_id: str | None = None,
        title: str | None = None,
        **kwargs,
    ):
        super().__init__(parent=parent, content=content, view_id=view_id, title=title)
        self.admin_widget = create_admin_widget(parent=self)
        self.set_content(self.admin_widget)

    @SafeSlot()
    def on_exit(self) -> None:
        """Called before the view is hidden.

        Default implementation does nothing. Override in subclasses.
        """
        self.admin_widget.logout()
