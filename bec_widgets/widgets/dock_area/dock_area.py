from __future__ import annotations

import sys
from typing import Literal, Optional
from weakref import WeakValueDictionary

import qdarktheme
from PyQt6.QtWidgets import QApplication, QVBoxLayout
from pydantic import Field
from pyqtgraph.dockarea.DockArea import DockArea
from qtpy.QtCore import Qt
from qtpy.QtGui import QPainter, QPaintEvent
from qtpy.QtWidgets import QWidget, QMainWindow, QDockWidget

from bec_widgets.utils import BECConnector, ConnectionConfig, WidgetContainerUtils
from bec_widgets.widgets import BECFigure
from bec_widgets.widgets.dock_area.dock.dock import BECDockAlt, DockConfig


class DockAreaConfig(ConnectionConfig):
    docks: dict[str, DockConfig] = Field({}, description="The docks in the dock area.")


class BECDockAreaAlt(BECConnector, QMainWindow):
    USER_ACCESS = []
    positions = {
        "top": Qt.DockWidgetArea.TopDockWidgetArea,
        "bottom": Qt.DockWidgetArea.BottomDockWidgetArea,
        "left": Qt.DockWidgetArea.LeftDockWidgetArea,
        "right": Qt.DockWidgetArea.RightDockWidgetArea,
    }

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
        QMainWindow.__init__(self, parent=parent)
        # TODO experimetn with the options and features
        # self.setDockNestingEnabled(True)
        # self.setDockOptions(
        #     QMainWindow.DockOption.AllowTabbedDocks | QMainWindow.DockOption.AllowNestedDocks
        # )
        self._instructions_visible = True  # TODO do not know how to translate yet to native qt

        self._docks = WeakValueDictionary()

    @property
    def docks(self) -> dict:
        """
        Get the docks in the dock area.
        Returns:
            dock_dict(dict): The docks in the dock area.
        """
        return dict(self._docks)

    @docks.setter
    def docks(self, value: dict):
        self._docks = WeakValueDictionary(value)

    def add_dock(
        self,
        title: str = None,
        layout: Literal["horizontal", "vertical", "grid"] = "vertical",
        prefix: str = "dock",
        position: Literal["top", "bottom", "left", "right"] = "bottom",
    ):

        if title is None:
            title = WidgetContainerUtils.generate_unique_widget_id(self._docks, prefix=prefix)

        if title in set(self.docks.keys()):
            raise ValueError(f"Dock with name {title} already exists.")

        dock = BECDockAlt(title=title, parent=self, parent_dock_area=self, layout=layout)
        self.addDockWidget(self.positions[position], dock)
        self._docks[title] = dock

        return dock
