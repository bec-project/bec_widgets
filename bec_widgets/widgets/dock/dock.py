from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Optional

from pydantic import Field
from pyqtgraph.dockarea import Dock, DockLabel

from bec_widgets.cli.rpc_wigdet_handler import widget_handler
from bec_widgets.utils import ConnectionConfig, GridLayoutManager
from bec_widgets.utils.bec_widget import BECWidget

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget

    from bec_widgets.widgets.dock import BECDockArea


class DockConfig(ConnectionConfig):
    widgets: dict[str, Any] = Field({}, description="The widgets in the dock.")
    position: Literal["bottom", "top", "left", "right", "above", "below"] = Field(
        "bottom", description="The position of the dock."
    )
    parent_dock_area: Optional[str] = Field(
        None, description="The GUI ID of parent dock area of the dock."
    )


class CustomDockLabel(DockLabel):
    def updateStyle(self):
        r = "3px"
        if self.dim:
            fg = "#aaa"
            bg = "#44a"
            border = "#339"
        else:
            fg = "#fff"
            bg = "#3f4042"
            border = "#3f4042"

        if self.orientation == "vertical":
            self.vStyle = """DockLabel {
                background-color : %s;
                color : %s;
                border-top-right-radius: 0px;
                border-top-left-radius: %s;
                border-bottom-right-radius: 0px;
                border-bottom-left-radius: %s;
                border-width: 0px;
                border-right: 2px solid %s;
                padding-top: 3px;
                padding-bottom: 3px;
                font-size: %s;
            }""" % (
                bg,
                fg,
                r,
                r,
                border,
                self.fontSize,
            )
            self.setStyleSheet(self.vStyle)
        else:
            self.hStyle = """DockLabel {
                background-color : %s;
                color : %s;
                border-top-right-radius: %s;
                border-top-left-radius: %s;
                border-bottom-right-radius: 0px;
                border-bottom-left-radius: 0px;
                border-width: 0px;
                border-bottom: 2px solid %s;
                padding-left: 3px;
                padding-right: 3px;
                font-size: %s;
            }""" % (
                bg,
                fg,
                r,
                r,
                border,
                self.fontSize,
            )
            self.setStyleSheet(self.hStyle)


class BECDock(BECWidget, Dock):
    USER_ACCESS = [
        "_config_dict",
        "_rpc_id",
        "widget_list",
        "show_title_bar",
        "hide_title_bar",
        "get_widgets_positions",
        "set_title",
        "add_widget",
        "list_eligible_widgets",
        "move_widget",
        "remove_widget",
        "remove",
        "attach",
        "detach",
    ]

    def __init__(
        self,
        parent: QWidget | None = None,
        parent_dock_area: QWidget | None = None,
        config: DockConfig | None = None,
        name: str | None = None,
        client=None,
        gui_id: str | None = None,
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
        label = CustomDockLabel(text=name)
        Dock.__init__(self, name=name, label=label, **kwargs)
        # Dock.__init__(self, name=name, **kwargs)

        self.parent_dock_area = parent_dock_area

        # Layout Manager
        self.layout_manager = GridLayoutManager(self.layout)

    def dropEvent(self, event):
        source = event.source()
        old_area = source.area
        self.setOrientation("horizontal", force=True)
        super().dropEvent(event)
        if old_area in self.orig_area.tempAreas and old_area != self.orig_area:
            self.orig_area.removeTempArea(old_area)

    def float(self):
        """
        Float the dock.
        Overwrites the default pyqtgraph dock float.
        """

        # need to check if the dock is temporary and if it is the only dock in the area
        # fixes bug in pyqtgraph detaching
        if self.area.temporary == True and len(self.area.docks) <= 1:
            return
        elif self.area.temporary == True and len(self.area.docks) > 1:
            self.area.docks.pop(self.name(), None)
            super().float()
        else:
            super().float()

    @property
    def widget_list(self) -> list[BECWidget]:
        """
        Get the widgets in the dock.

        Returns:
            widgets(list): The widgets in the dock.
        """
        return self.widgets

    @widget_list.setter
    def widget_list(self, value: list[BECWidget]):
        self.widgets = value

    def hide_title_bar(self):
        """
        Hide the title bar of the dock.
        """
        # self.hideTitleBar() #TODO pyqtgraph looks bugged ATM, doing my implementation
        self.label.hide()
        self.labelHidden = True

    def show_title_bar(self):
        """
        Hide the title bar of the dock.
        """
        # self.showTitleBar() #TODO pyqtgraph looks bugged ATM, doing my implementation
        self.label.show()
        self.labelHidden = False

    def set_title(self, title: str):
        """
        Set the title of the dock.

        Args:
            title(str): The title of the dock.
        """
        self.orig_area.docks[title] = self.orig_area.docks.pop(self.name())
        self.setTitle(title)
        self._name = title

    def get_widgets_positions(self) -> dict:
        """
        Get the positions of the widgets in the dock.

        Returns:
            dict: The positions of the widgets in the dock as dict -> {(row, col, rowspan, colspan):widget}
        """
        return self.layout_manager.get_widgets_positions()

    def list_eligible_widgets(
        self,
    ) -> list:  # TODO can be moved to some util mixin like container class for rpc widgets
        """
        List all widgets that can be added to the dock.

        Returns:
            list: The list of eligible widgets.
        """
        return list(widget_handler.widget_classes.keys())

    def add_widget(
        self,
        widget: BECWidget | str,
        row=None,
        col=0,
        rowspan=1,
        colspan=1,
        shift: Literal["down", "up", "left", "right"] = "down",
    ) -> BECWidget:
        """
        Add a widget to the dock.

        Args:
            widget(QWidget): The widget to add.
            row(int): The row to add the widget to. If None, the widget will be added to the next available row.
            col(int): The column to add the widget to.
            rowspan(int): The number of rows the widget should span.
            colspan(int): The number of columns the widget should span.
            shift(Literal["down", "up", "left", "right"]): The direction to shift the widgets if the position is occupied.
        """
        if row is None:
            row = self.layout.rowCount()

        if self.layout_manager.is_position_occupied(row, col):
            self.layout_manager.shift_widgets(shift, start_row=row)

        if isinstance(widget, str):
            widget = widget_handler.create_widget(widget)
        else:
            widget = widget

        self.addWidget(widget, row=row, col=col, rowspan=rowspan, colspan=colspan)

        if hasattr(widget, "config"):
            self.config.widgets[widget.gui_id] = widget.config

        return widget

    def move_widget(self, widget: QWidget, new_row: int, new_col: int):
        """
        Move a widget to a new position in the layout.

        Args:
            widget(QWidget): The widget to move.
            new_row(int): The new row to move the widget to.
            new_col(int): The new column to move the widget to.
        """
        self.layout_manager.move_widget(widget, new_row, new_col)

    def attach(self):
        """
        Attach the dock to the parent dock area.
        """
        self.orig_area.removeTempArea(self.area)

    def detach(self):
        """
        Detach the dock from the parent dock area.
        """
        self.float()

    def remove_widget(self, widget_rpc_id: str):
        """
        Remove a widget from the dock.

        Args:
            widget_rpc_id(str): The ID of the widget to remove.
        """
        widget = self.rpc_register.get_rpc_by_id(widget_rpc_id)
        self.layout.removeWidget(widget)
        self.config.widgets.pop(widget_rpc_id, None)
        widget.close()

    def remove(self):
        """
        Remove the dock from the parent dock area.
        """
        # self.cleanup()
        self.parent_dock_area.remove_dock(self.name())

    def cleanup(self):
        """
        Clean up the dock, including all its widgets.
        """
        for widget in self.widgets:
            if hasattr(widget, "cleanup"):
                widget.cleanup()
        self.widgets.clear()
        super().cleanup()

    def close(self):
        """
        Close the dock area and cleanup.
        Has to be implemented to overwrite pyqtgraph event accept in Container close.
        """
        self.cleanup()
        super().close()
        self.parent_dock_area.dock_area.docks.pop(self.name(), None)
