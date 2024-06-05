from __future__ import annotations

from typing import Literal, Optional
from weakref import WeakValueDictionary

from pydantic import Field
from pyqtgraph.dockarea.DockArea import DockArea
from qtpy.QtCore import Qt
from qtpy.QtGui import QPainter, QPaintEvent
from qtpy.QtWidgets import QWidget

from bec_widgets.utils import BECConnector, ConnectionConfig, WidgetContainerUtils

from .dock import BECDock, DockConfig


class DockAreaConfig(ConnectionConfig):
    docks: dict[str, DockConfig] = Field({}, description="The docks in the dock area.")
    docks_state: Optional[dict] = Field(
        None, description="The state of the docks in the dock area."
    )


class BECDockArea(BECConnector, DockArea):
    USER_ACCESS = [
        "config_dict",
        "panels",
        "save_state",
        "remove_dock",
        "restore_state",
        "add_dock",
        "clear_all",
        "detach_dock",
        "attach_all",
        "get_all_rpc",
        "temp_areas",
    ]

    def __init__(
        self,
        parent: QWidget | None = None,
        config: DockAreaConfig | None = None,
        client=None,
        gui_id: str = None,
    ) -> None:
        if config is None:
            config = DockAreaConfig(widget_class=self.__class__.__name__)
        else:
            if isinstance(config, dict):
                config = DockAreaConfig(**config)
            self.config = config
        super().__init__(client=client, config=config, gui_id=gui_id)
        DockArea.__init__(self, parent=parent)

        self._instructions_visible = True

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)
        if self._instructions_visible:
            painter = QPainter(self)
            painter.drawText(self.rect(), Qt.AlignCenter, "Add docks using 'add_dock' method")

    @property
    def panels(self) -> dict:
        """
        Get the docks in the dock area.
        Returns:
            dock_dict(dict): The docks in the dock area.
        """
        return dict(self.docks)

    @panels.setter
    def panels(self, value: dict):
        self.docks = WeakValueDictionary(value)

    @property
    def temp_areas(self) -> list:
        """
        Get the temporary areas in the dock area.

        Returns:
            list: The temporary areas in the dock area.
        """
        return list(map(str, self.tempAreas))

    @temp_areas.setter
    def temp_areas(self, value: list):
        self.tempAreas = list(map(str, value))

    def restore_state(
        self, state: dict = None, missing: Literal["ignore", "error"] = "ignore", extra="bottom"
    ):
        """
        Restore the state of the dock area. If no state is provided, the last state is restored.

        Args:
            state(dict): The state to restore.
            missing(Literal['ignore','error']): What to do if a dock is missing.
            extra(str): Extra docks that are in the dockarea but that are not mentioned in state will be added to the bottom of the dockarea, unless otherwise specified by the extra argument.
        """
        if state is None:
            state = self.config.docks_state
        self.restoreState(state, missing=missing, extra=extra)

    def save_state(self) -> dict:
        """
        Save the state of the dock area.

        Returns:
            dict: The state of the dock area.
        """
        last_state = self.saveState()
        self.config.docks_state = last_state
        return last_state

    def remove_dock(self, name: str):
        """
        Remove a dock by name and ensure it is properly closed and cleaned up.

        Args:
            name(str): The name of the dock to remove.
        """
        dock = self.docks.pop(name, None)
        self.config.docks.pop(name, None)
        if dock:
            dock.close()
            if len(self.docks) <= 1:
                for dock in self.docks.values():
                    dock.hide_title_bar()

        else:
            raise ValueError(f"Dock with name {name} does not exist.")

    def add_dock(
        self,
        name: str = None,
        position: Literal["bottom", "top", "left", "right", "above", "below"] = None,
        relative_to: BECDock | None = None,
        closable: bool = False,
        prefix: str = "dock",
        widget: str | QWidget | None = None,
        row: int = None,
        col: int = 0,
        rowspan: int = 1,
        colspan: int = 1,
    ) -> BECDock:
        """
        Add a dock to the dock area. Dock has QGridLayout as layout manager by default.

        Args:
            name(str): The name of the dock to be displayed and for further references. Has to be unique.
            position(Literal["bottom", "top", "left", "right", "above", "below"]): The position of the dock.
            relative_to(BECDock): The dock to which the new dock should be added relative to.
            closable(bool): Whether the dock is closable.
            prefix(str): The prefix for the dock name if no name is provided.
            widget(str|QWidget|None): The widget to be added to the dock. While using RPC, only BEC RPC widgets from RPCWidgetHandler are allowed.
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

        dock = BECDock(name=name, parent_dock_area=self, closable=closable)
        dock.config.position = position
        self.config.docks[name] = dock.config

        self.addDock(dock=dock, position=position, relativeTo=relative_to)

        if len(self.docks) <= 1:
            dock.hide_title_bar()
        elif len(self.docks) > 1:
            for dock in self.docks.values():
                dock.show_title_bar()

        if widget is not None and isinstance(widget, str):
            dock.add_widget(widget=widget, row=row, col=col, rowspan=rowspan, colspan=colspan)
        elif widget is not None and isinstance(widget, QWidget):
            dock.addWidget(widget, row=row, col=col, rowspan=rowspan, colspan=colspan)
        if self._instructions_visible:
            self._instructions_visible = False
            self.update()
        return dock

    def detach_dock(self, dock_name: str) -> BECDock:
        """
        Undock a dock from the dock area.

        Args:
            dock_name(str): The dock to undock.

        Returns:
            BECDock: The undocked dock.
        """
        dock = self.docks[dock_name]
        dock.detach()
        return dock

    def attach_all(self):
        """
        Return all floating docks to the dock area.
        """
        while self.tempAreas:
            for temp_area in self.tempAreas:
                self.removeTempArea(temp_area)

    def clear_all(self):
        """
        Close all docks and remove all temp areas.
        """
        self.attach_all()
        for dock in dict(self.docks).values():
            dock.remove()

    def cleanup(self):
        """
        Cleanup the dock area.
        """
        self.clear_all()
        super().cleanup()

    def close(self):
        """
        Close the dock area and cleanup.
        Has to be implemented to overwrite pyqtgraph event accept in Container close.
        """
        self.cleanup()
        super().close()
