"""Module for the Data view of the main application."""

from __future__ import annotations

from qtpy.QtWidgets import QWidget

from bec_widgets.applications.views.view import ViewBase
from bec_widgets.utils.error_popups import SafeSlot


class DataView(ViewBase):
    """
    A view to browse the scans BEC has written and to look into HDF5 files, with the HDF5
    viewer. The viewer is built the first time the view is opened, so the start of the
    application does not pay for it, and it stops reading files while the view is hidden.
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
        super().__init__(parent=parent, content=content, view_id=view_id, title=title, **kwargs)
        self.viewer = None

    def _build_viewer(self):
        # pylint: disable=import-outside-toplevel
        from bec_widgets.widgets.services.hdf5_viewer.hdf5_viewer import HDF5Viewer

        self.viewer = HDF5Viewer(parent=self, client=self.client)
        self.set_content(self.viewer)

    @SafeSlot()
    def on_enter(self) -> None:
        """Build the viewer on the first visit; later, pick up the reads cut off on leaving."""
        if self.viewer is None:
            self._build_viewer()
            return
        self.viewer.resume()

    @SafeSlot()
    def on_exit(self) -> bool:
        """Stop reading files while the view is hidden."""
        if self.viewer is not None:
            self.viewer.pause()
        return True
