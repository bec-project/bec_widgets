from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Optional
from weakref import WeakValueDictionary

from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QGridLayout
from PyQt6.QtCore import Qt
from pydantic import Field
from pyqtgraph.dockarea import Dock


from bec_widgets.cli.rpc_wigdet_handler import RPCWidgetHandler
from bec_widgets.utils import BECConnector, ConnectionConfig, GridLayoutManager
from qtpy.QtWidgets import QWidget, QMainWindow, QDockWidget, QSizePolicy

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget
    from bec_widgets.widgets.dock_area.dock_area import BECDockAreaAlt


class DockConfig(ConnectionConfig):
    widgets: dict[str, ConnectionConfig] = Field({}, description="The widgets in the dock.")
    position: Literal["bottom", "top", "left", "right", "above", "below"] = Field(
        "bottom", description="The position of the dock."
    )
    parent_dock_area: Optional[str] = Field(
        None, description="The GUI ID of parent dock area of the dock."
    )


class BECDockAlt(BECConnector, QDockWidget):
    USER_ACCESS = []

    def __init__(
        self,
        parent: QWidget | None = None,
        parent_dock_area: BECDockAreaAlt | None = None,
        config: DockConfig | None = None,
        title: str | None = None,  # TODO maybe rename to title
        client=None,
        gui_id: str | None = None,
        layout: Literal["horizontal", "vertical", "grid"] = "vertical",
    ) -> None:
        if config is None:
            config = DockConfig(
                widget_class=self.__class__.__name__, parent_dock_area=parent_dock_area.gui_id
            )
        else:
            if isinstance(config, dict):
                config = DockConfig(**config)
        super().__init__(client=client, config=config, gui_id=gui_id)
        QDockWidget.__init__(self, title, parent)

        self._parent_dock_area = parent_dock_area
        self._init_setup()
        self.setup_layout(layout)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self._grid_layout_manager = GridLayoutManager(self)
        # self._widget_handler.init()
        # self._grid_layout_manager.init

    def _init_setup(self):
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self._widget_handler = RPCWidgetHandler()
        self._base_widget = QWidget()
        self._widgets = WeakValueDictionary()

    def setup_layout(self, layout: Literal["horizontal", "vertical", "grid"] = "grid"):
        if layout == "horizontal":
            self.layout = QHBoxLayout()
        elif layout == "vertical":
            self.layout = QVBoxLayout()
        elif layout == "grid":
            self.layout = QGridLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self._base_widget.setLayout(self.layout)
        self.setWidget(self._base_widget)

    def add_widget(self, widget: QWidget, row: int = None, col: int = None):

        if isinstance(self.layout, QVBoxLayout) or isinstance(self.layout, QHBoxLayout):
            self.layout.addWidget(widget)
            if row or col:
                print(f"Warning: row and column are not used in this layout - {self.layout}")
        elif isinstance(self.layout, QGridLayout):
            if row is None:
                row = self.layout.rowCount()
            if col is None:
                col = self.layout.columnCount()
            self.layout.addWidget(widget, row, col)

        return widget

    def add_widget_bec(self, widget_type: str, row: int = None, col: int = None):
        widget = self._widget_handler.create_widget(widget_type)
        self.add_widget(widget, row, col)
        return widget

    def remove_widget(self, widget_id: str):
        widget = self.widgets.pop(widget_id)
        widget.deleteLater()
        return widget

    def cleanup(self):
        """
        Clean up the dock, including all its widgets.
        """
        for widget in self.widgets:
            if hasattr(widget, "cleanup"):
                widget.cleanup()
        super().cleanup()

    def close(self):
        self.cleanup()
        super().close()
