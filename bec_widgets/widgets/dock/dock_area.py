from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field
from pyqtgraph.dockarea.DockArea import DockArea
from qtpy.QtWidgets import QWidget

from bec_widgets.utils import BECConnector, ConnectionConfig, WidgetContainerUtils

from .dock import BECDock, DockConfig

# from bec_widgets.widgets import BECDock


class DockAreaConfig(ConnectionConfig):
    docks: dict[str, DockConfig] = Field({}, description="The docks in the dock area.")


class BECDockArea(BECConnector, DockArea):
    USER_ACCESS = [
        "add_dock",
        "remove_dock_by_id",
        "clear_all",
        "dock_dict",
    ]

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

    @property
    def dock_dict(self) -> dict:
        return dict(self.docks)

    @dock_dict.setter
    def dock_dict(self, value: dict):
        from weakref import WeakValueDictionary

        self.docks = WeakValueDictionary(value)

    def remove_dock_by_id(self, dock_id: str):
        if dock_id in self.docks:
            dock_to_remove = self.docks[dock_id]
            dock_to_remove.close()
        else:
            raise ValueError(f"Dock with id {dock_id} does not exist.")

    def remove_dock(self, name: str):
        for id, dock in self.docks.items():
            dock_name = dock.name()
            if dock_name == name:
                dock.close()
                break

    def add_dock(
        self,
        name: str = None,
        position: Literal["bottom", "top", "left", "right", "above", "below"] = None,
        relative_to: Optional[BECDock] = None,
        prefix: str = "dock",
        widget: QWidget = None,
        row: int = None,
        col: int = None,
        rowspan: int = 1,
        colspan: int = 1,
    ) -> BECDock:
        """
        Add a dock to the dock area. Dock has QGridLayout as layout manager by default.

        Args:
            name(str): The name of the dock to be displayed and for further references. Has to be unique.
            position(Literal["bottom", "top", "left", "right", "above", "below"]): The position of the dock.
            relative_to(BECDock): The dock to which the new dock should be added relative to.
            prefix(str): The prefix for the dock name if no name is provided.
            widget(QWidget): The widget to be added to the dock.
            row(int): The row of the added widget.
            col(int): The column of the added widget.
            rowspan(int): The rowspan of the added widget.
            colspan(int): The colspan of the added widget.

        Returns:
            BECDock: The created dock.
        """
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

        self.addDock(dock=dock, position=position, relativeTo=relative_to)

        if widget is not None:
            dock.addWidget(widget)  # , row, col, rowspan, colspan)

        return dock

    def clear_all(self):
        for dock in self.docks.values():
            dock.close()
