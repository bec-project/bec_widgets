from collections import defaultdict
from typing import Optional, Literal

import pyqtgraph as pg
from qtpy.QtWidgets import QWidget
from pydantic import Field
from pyqtgraph.dockarea.DockArea import DockArea, Dock
from bec_widgets.utils import BECConnector, ConnectionConfig, WidgetContainerUtils
from bec_widgets.widgets import BECWaveform, BECFigure, BECMotorMap
from bec_widgets.widgets.plots import BECImageShow


class DockConfig(ConnectionConfig):
    widgets: dict[str, ConnectionConfig] = Field({}, description="The widgets in the dock.")
    position: Literal["bottom", "top", "left", "right", "above", "below"] = Field(
        "bottom", description="The position of the dock."
    )
    parent_dock_area: Optional[str] = Field(
        None, description="The GUI ID of parent dock area of the dock."
    )


class DockAreaConfig(ConnectionConfig):
    docks: dict[str, DockConfig] = Field({}, description="The docks in the dock area.")


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


class BECDockArea(BECConnector, DockArea):
    USER_ACCESS = ["figure", "plot", "image", "motor_map", "add_dock", "remove_dock_by_id", "clear"]

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        config: Optional[DockAreaConfig] = None,
        client=None,
        gui_id: Optional[str] = None,
    ) -> None:
        if config is None:
            config = DockAreaConfig(widget_class=self.__class__.__name__)
        else:
            if isinstance(config, dict):
                config = DockAreaConfig(**config)
            self.config = config
        super().__init__(client=client, config=config, gui_id=gui_id)
        DockArea.__init__(self, parent=parent)

        self._last_state = None  # TODO not sure if this will ever work

    def figure(self, name: str = None) -> BECFigure:
        figure = BECFigure(gui_id="remote")
        self.add_dock(name=name, widget=figure, prefix="figure")
        return figure

    def plot(
        self,
        x_name: str = None,
        y_name: str = None,
        name: str = None,
    ) -> BECWaveform:
        figure = BECFigure(gui_id="remote")
        self.add_dock(name=name, widget=figure, prefix="plot")

        plot = figure.plot(x_name, y_name)
        return plot

    def image(self, monitor: str = "eiger", name: str = None) -> BECImageShow:
        figure = BECFigure(gui_id="remote")
        self.add_dock(name=name, widget=figure, prefix="image")

        image = figure.image(monitor)
        return image

    def motor_map(self, x_name: str = None, y_name: str = None, name: str = None) -> BECMotorMap:
        figure = BECFigure(gui_id="remote")
        self.add_dock(name=name, widget=figure, prefix="motor_map")

        motor_map = figure.motor_map(x_name, y_name)
        return motor_map

    def add_dock(
        self,
        name: str = None,
        widget: QWidget = None,
        position: Literal["bottom", "top", "left", "right", "above", "below"] = None,
        relative_to: Optional[BECDock] = None,  # TODO implement relative_to
        prefix: str = "dock",
    ) -> BECDock:
        if name is None:
            name = WidgetContainerUtils.generate_unique_widget_id(
                container=self.docks, prefix=prefix
            )

        if name in set(self.docks.keys()):
            raise ValueError(f"Dock with name {name} already exists.")

        if position is None:
            position = "bottom"

        dock = BECDock(name=name, parent_dock_area=self, closable=True)
        dock.config.position = position
        self.config.docks[name] = dock.config

        self.addDock(dock, position)

        if widget is not None:
            dock.addWidget(widget)

        return dock

    def remove_dock_by_id(self, dock_id: str):
        if dock_id in self.docks:
            dock_to_remove = self.docks[dock_id]
            dock_to_remove.close()
        else:
            raise ValueError(f"Dock with id {dock_id} does not exist.")
