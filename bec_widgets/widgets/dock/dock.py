from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field
from pyqtgraph.dockarea import Dock
from qtpy.QtWidgets import QWidget

from bec_widgets.utils import BECConnector, ConnectionConfig


class DockConfig(ConnectionConfig):
    widgets: dict[str, ConnectionConfig] = Field({}, description="The widgets in the dock.")
    position: Literal["bottom", "top", "left", "right", "above", "below"] = Field(
        "bottom", description="The position of the dock."
    )
    parent_dock_area: Optional[str] = Field(
        None, description="The GUI ID of parent dock area of the dock."
    )


class BECDock(BECConnector, Dock):
    USER_ACCESS = ["add_widget", "widget_list"]

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        parent_dock_area: Optional["BECDockArea"] = None,
        config: Optional[
            DockConfig
        ] = None,  # TODO ATM connection config -> will be changed when I will know what I want to use there
        name: Optional[str] = None,
        client=None,
        gui_id: Optional[str] = None,
        **kwargs,
    ) -> None:
        if config is None:
            config = DockConfig(
                widget_class=self.__class__.__name__, parent_dock_area=parent_dock_area.gui_id
            )
        else:
            if isinstance(config, dict):
                config = DockConfig(**config)
            self.config = config
        super().__init__(client=client, config=config, gui_id=gui_id)
        Dock.__init__(self, name=name, **kwargs)

        self.parent_dock_area = parent_dock_area

        self.sigClosed.connect(self._remove_from_dock_area)

    @property
    def widget_list(self) -> list:
        return self.widgets

    @widget_list.setter
    def widget_list(self, value: list):
        self.widgets = value

    def add_widget(self, widget: QWidget, row=None, col=0, rowspan=1, colspan=1):
        self.addWidget(widget, row=row, col=col, rowspan=rowspan, colspan=colspan)

    def _remove_from_dock_area(self):
        """Remove this dock from the DockArea it lives inside."""
        self.parent_dock_area.docks.pop(self.name())
