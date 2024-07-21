from __future__ import annotations

from typing import Literal, Optional
from weakref import WeakValueDictionary

from pydantic import Field
from pyqtgraph.dockarea.DockArea import DockArea
from qtpy.QtCore import Qt
from qtpy.QtGui import QPainter, QPaintEvent
from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.qt_utils.toolbar import (
    ExpandableMenuAction,
    IconAction,
    ModularToolBar,
    SeparatorAction,
)
from bec_widgets.utils import ConnectionConfig, WidgetContainerUtils
from bec_widgets.utils.bec_widget import BECWidget

from ...qt_utils.error_popups import SafeSlot
from .dock import BECDock, DockConfig


class DockAreaConfig(ConnectionConfig):
    docks: dict[str, DockConfig] = Field({}, description="The docks in the dock area.")
    docks_state: Optional[dict] = Field(
        None, description="The state of the docks in the dock area."
    )


class BECDockArea(BECWidget, QWidget):
    USER_ACCESS = [
        "_config_dict",
        "panels",
        "save_state",
        "remove_dock",
        "restore_state",
        "add_dock",
        "clear_all",
        "detach_dock",
        "attach_all",
        "_get_all_rpc",
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
        QWidget.__init__(self, parent=parent)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(5)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self._instructions_visible = True

        self.dock_area = DockArea()
        self.toolbar = ModularToolBar(
            actions={
                "menu_plots": ExpandableMenuAction(
                    label="Add Plot ",
                    actions={
                        "waveform": IconAction(icon_path="waveform.svg", tooltip="Add Waveform"),
                        "image": IconAction(icon_path="image.svg", tooltip="Add Image"),
                        "motor_map": IconAction(icon_path="motor_map.svg", tooltip="Add Motor Map"),
                    },
                ),
                "separator_0": SeparatorAction(),
                "menu_devices": ExpandableMenuAction(
                    label="Add Device Control ",
                    actions={
                        "scan_control": IconAction(
                            icon_path="scan_control.svg", tooltip="Add Scan Control"
                        ),
                        "device_box": IconAction(
                            icon_path="device_box.svg", tooltip="Add Device Box"
                        ),
                    },
                ),
                "separator_1": SeparatorAction(),
                "menu_utils": ExpandableMenuAction(
                    label="Add Utils ",
                    actions={
                        "queue": IconAction(icon_path="queue.svg", tooltip="Add Scan Queue"),
                        "vs_code": IconAction(icon_path="terminal.svg", tooltip="Add VS Code"),
                        "status": IconAction(icon_path="status.svg", tooltip="Add BEC Status Box"),
                        "progress_bar": IconAction(
                            icon_path="progress.svg", tooltip="Add Circular ProgressBar"
                        ),
                    },
                ),
                "separator_2": SeparatorAction(),
                "attach_all": IconAction(
                    icon_path="attach_all.svg", tooltip="Attach all floating docks"
                ),
                "save_state": IconAction(icon_path="save_state.svg", tooltip="Save Dock State"),
                "restore_state": IconAction(
                    icon_path="restore_state.svg", tooltip="Restore Dock State"
                ),
            },
            target_widget=self,
        )

        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.dock_area)
        self._hook_toolbar()

    def _hook_toolbar(self):
        # Menu Plot
        self.toolbar.widgets["menu_plots"].widgets["waveform"].triggered.connect(
            lambda: self.add_dock(widget="BECWaveformWidget")
        )
        self.toolbar.widgets["menu_plots"].widgets["image"].triggered.connect(
            lambda: self.add_dock(widget="BECImageWidget")
        )
        self.toolbar.widgets["menu_plots"].widgets["motor_map"].triggered.connect(
            lambda: self.add_dock(widget="BECMotorMapWidget")
        )

        # Menu Devices
        self.toolbar.widgets["menu_devices"].widgets["scan_control"].triggered.connect(
            lambda: self.add_dock(widget="ScanControl")
        )
        self.toolbar.widgets["menu_devices"].widgets["device_box"].triggered.connect(
            lambda: self.add_dock(widget="DeviceBox")
        )

        # Menu Utils
        self.toolbar.widgets["menu_utils"].widgets["queue"].triggered.connect(
            lambda: self.add_dock(widget="BECQueue")
        )
        self.toolbar.widgets["menu_utils"].widgets["status"].triggered.connect(
            lambda: self.add_dock(widget="BECStatusBox")
        )
        self.toolbar.widgets["menu_utils"].widgets["vs_code"].triggered.connect(
            lambda: self.add_dock(widget="VSCodeEditor")
        )
        self.toolbar.widgets["menu_utils"].widgets["progress_bar"].triggered.connect(
            lambda: self.add_dock(widget="RingProgressBar")
        )

        # Icons
        self.toolbar.widgets["attach_all"].action.triggered.connect(self.attach_all)
        self.toolbar.widgets["save_state"].action.triggered.connect(self.save_state)
        self.toolbar.widgets["restore_state"].action.triggered.connect(self.restore_state)

    def paintEvent(self, event: QPaintEvent):  # TODO decide if we want any default instructions
        super().paintEvent(event)
        if self._instructions_visible:
            painter = QPainter(self)
            painter.drawText(
                self.rect(),
                Qt.AlignCenter,
                "Add docks using 'add_dock' method from CLI\n or \n Add widget docks using the toolbar",
            )

    @property
    def panels(self) -> dict[str, BECDock]:
        """
        Get the docks in the dock area.
        Returns:
            dock_dict(dict): The docks in the dock area.
        """
        return dict(self.dock_area.docks)

    @panels.setter
    def panels(self, value: dict[str, BECDock]):
        self.dock_area.docks = WeakValueDictionary(value)

    @property
    def temp_areas(self) -> list:
        """
        Get the temporary areas in the dock area.

        Returns:
            list: The temporary areas in the dock area.
        """
        return list(map(str, self.dock_area.tempAreas))

    @temp_areas.setter
    def temp_areas(self, value: list):
        self.dock_area.tempAreas = list(map(str, value))

    @SafeSlot()
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
        self.dock_area.restoreState(state, missing=missing, extra=extra)

    @SafeSlot()
    def save_state(self) -> dict:
        """
        Save the state of the dock area.

        Returns:
            dict: The state of the dock area.
        """
        last_state = self.dock_area.saveState()
        self.config.docks_state = last_state
        return last_state

    def remove_dock(self, name: str):
        """
        Remove a dock by name and ensure it is properly closed and cleaned up.

        Args:
            name(str): The name of the dock to remove.
        """
        dock = self.dock_area.docks.pop(name, None)
        self.config.docks.pop(name, None)
        if dock:
            dock.close()
            if len(self.dock_area.docks) <= 1:
                for dock in self.dock_area.docks.values():
                    dock.hide_title_bar()

        else:
            raise ValueError(f"Dock with name {name} does not exist.")

    @SafeSlot(popup_error=True)
    def add_dock(
        self,
        name: str = None,
        position: Literal["bottom", "top", "left", "right", "above", "below"] = None,
        relative_to: BECDock | None = None,
        closable: bool = True,
        floating: bool = False,
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
            floating(bool): Whether the dock is detached after creating.
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
                container=self.dock_area.docks, prefix=prefix
            )

        if name in set(self.dock_area.docks.keys()):
            raise ValueError(f"Dock with name {name} already exists.")

        if position is None:
            position = "bottom"

        dock = BECDock(name=name, parent_dock_area=self, closable=closable)
        dock.config.position = position
        self.config.docks[name] = dock.config

        self.dock_area.addDock(dock=dock, position=position, relativeTo=relative_to)

        if len(self.dock_area.docks) <= 1:
            dock.hide_title_bar()
        elif len(self.dock_area.docks) > 1:
            for dock in self.dock_area.docks.values():
                dock.show_title_bar()

        if widget is not None and isinstance(widget, str):
            dock.add_widget(widget=widget, row=row, col=col, rowspan=rowspan, colspan=colspan)
        elif widget is not None and isinstance(widget, QWidget):
            dock.addWidget(widget, row=row, col=col, rowspan=rowspan, colspan=colspan)
        if (
            self._instructions_visible
        ):  # TODO still decide how initial instructions should be handled
            self._instructions_visible = False
            self.update()
        if floating:
            dock.detach()
        return dock

    def detach_dock(self, dock_name: str) -> BECDock:
        """
        Undock a dock from the dock area.

        Args:
            dock_name(str): The dock to undock.

        Returns:
            BECDock: The undocked dock.
        """
        dock = self.dock_area.docks[dock_name]
        dock.detach()
        return dock

    @SafeSlot()
    def attach_all(self):
        """
        Return all floating docks to the dock area.
        """
        while self.dock_area.tempAreas:
            for temp_area in self.dock_area.tempAreas:
                self.dock_area.removeTempArea(temp_area)

    def clear_all(self):
        """
        Close all docks and remove all temp areas.
        """
        self.attach_all()
        for dock in dict(self.dock_area.docks).values():
            dock.remove()
        self.dock_area.docks.clear()

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
