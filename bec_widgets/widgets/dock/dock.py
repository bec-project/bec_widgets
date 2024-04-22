from typing import Literal, Optional

from pydantic import Field
from pyqtgraph.dockarea import Dock
from qtpy.QtWidgets import QWidget

from bec_widgets.utils import BECConnector, ConnectionConfig, WidgetContainerUtils


class DockConfig(ConnectionConfig):
    widgets: dict[str, ConnectionConfig] = Field({}, description="The widgets in the dock.")
    position: Literal["bottom", "top", "left", "right", "above", "below"] = Field(
        "bottom", description="The position of the dock."
    )
    parent_dock_area: Optional[str] = Field(
        None, description="The GUI ID of parent dock area of the dock."
    )


class BECDock(BECConnector, Dock):
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

    def _remove_from_dock_area(self):
        """Remove this dock from the DockArea it lives inside."""
        self.parent_dock_area.docks.pop(self.name())
