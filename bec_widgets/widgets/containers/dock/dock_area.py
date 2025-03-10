from __future__ import annotations

from typing import Literal, Optional
from weakref import WeakValueDictionary

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from pydantic import Field
from pyqtgraph.dockarea.DockArea import DockArea
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QPainter, QPaintEvent
from qtpy.QtWidgets import QApplication, QSizePolicy, QVBoxLayout, QWidget

from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.qt_utils.error_popups import SafeSlot
from bec_widgets.qt_utils.toolbar import (
    ExpandableMenuAction,
    MaterialIconAction,
    ModularToolBar,
    SeparatorAction,
)
from bec_widgets.utils import ConnectionConfig, WidgetContainerUtils
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.containers.dock.dock import BECDock, DockConfig
from bec_widgets.widgets.control.device_control.positioner_box import PositionerBox
from bec_widgets.widgets.control.scan_control.scan_control import ScanControl
from bec_widgets.widgets.editors.vscode.vscode import VSCodeEditor
from bec_widgets.widgets.plots.image.image_widget import BECImageWidget
from bec_widgets.widgets.plots.motor_map.motor_map_widget import BECMotorMapWidget
from bec_widgets.widgets.plots.multi_waveform.multi_waveform_widget import BECMultiWaveformWidget
from bec_widgets.widgets.plots_next_gen.waveform.waveform import Waveform
from bec_widgets.widgets.progress.ring_progress_bar.ring_progress_bar import RingProgressBar
from bec_widgets.widgets.services.bec_queue.bec_queue import BECQueue
from bec_widgets.widgets.services.bec_status_box.bec_status_box import BECStatusBox
from bec_widgets.widgets.utility.logpanel.logpanel import LogPanel
from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

logger = bec_logger.logger


class DockAreaConfig(ConnectionConfig):
    docks: dict[str, DockConfig] = Field({}, description="The docks in the dock area.")
    docks_state: Optional[dict] = Field(
        None, description="The state of the docks in the dock area."
    )


class BECDockArea(BECWidget, QWidget):
    PLUGIN = True
    USER_ACCESS = [
        "new",
        "show",
        "hide",
        "panels",
        "panel_list",
        "delete",
        "delete_all",
        "remove",
        "detach_dock",
        "attach_all",
        "selected_device",
        "save_state",
        "restore_state",
    ]

    def __init__(
        self,
        parent: QWidget | None = None,
        config: DockAreaConfig | None = None,
        client=None,
        gui_id: str = None,
        name: str | None = None,
        **kwargs,
    ) -> None:
        if config is None:
            config = DockAreaConfig(widget_class=self.__class__.__name__)
        else:
            if isinstance(config, dict):
                config = DockAreaConfig(**config)
            self.config = config
        super().__init__(client=client, config=config, gui_id=gui_id, name=name, **kwargs)
        QWidget.__init__(self, parent=parent)
        self._parent = parent
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
                        "waveform": MaterialIconAction(
                            icon_name=Waveform.ICON_NAME, tooltip="Add Waveform", filled=True
                        ),
                        "multi_waveform": MaterialIconAction(
                            icon_name=BECMultiWaveformWidget.ICON_NAME,
                            tooltip="Add Multi Waveform",
                            filled=True,
                        ),
                        "image": MaterialIconAction(
                            icon_name=BECImageWidget.ICON_NAME, tooltip="Add Image", filled=True
                        ),
                        "motor_map": MaterialIconAction(
                            icon_name=BECMotorMapWidget.ICON_NAME,
                            tooltip="Add Motor Map",
                            filled=True,
                        ),
                    },
                ),
                "separator_0": SeparatorAction(),
                "menu_devices": ExpandableMenuAction(
                    label="Add Device Control ",
                    actions={
                        "scan_control": MaterialIconAction(
                            icon_name=ScanControl.ICON_NAME, tooltip="Add Scan Control", filled=True
                        ),
                        "positioner_box": MaterialIconAction(
                            icon_name=PositionerBox.ICON_NAME, tooltip="Add Device Box", filled=True
                        ),
                    },
                ),
                "separator_1": SeparatorAction(),
                "menu_utils": ExpandableMenuAction(
                    label="Add Utils ",
                    actions={
                        "queue": MaterialIconAction(
                            icon_name=BECQueue.ICON_NAME, tooltip="Add Scan Queue", filled=True
                        ),
                        "vs_code": MaterialIconAction(
                            icon_name=VSCodeEditor.ICON_NAME, tooltip="Add VS Code", filled=True
                        ),
                        "status": MaterialIconAction(
                            icon_name=BECStatusBox.ICON_NAME,
                            tooltip="Add BEC Status Box",
                            filled=True,
                        ),
                        "progress_bar": MaterialIconAction(
                            icon_name=RingProgressBar.ICON_NAME,
                            tooltip="Add Circular ProgressBar",
                            filled=True,
                        ),
                        "log_panel": MaterialIconAction(
                            icon_name=LogPanel.ICON_NAME, tooltip="Add LogPanel", filled=True
                        ),
                    },
                ),
                "separator_2": SeparatorAction(),
                "attach_all": MaterialIconAction(
                    icon_name="zoom_in_map", tooltip="Attach all floating docks"
                ),
                "save_state": MaterialIconAction(icon_name="bookmark", tooltip="Save Dock State"),
                "restore_state": MaterialIconAction(
                    icon_name="frame_reload", tooltip="Restore Dock State"
                ),
            },
            target_widget=self,
        )

        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.dock_area)
        self.spacer = QWidget()
        self.spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.toolbar.addWidget(self.spacer)
        self.toolbar.addWidget(DarkModeButton(toolbar=True))
        self._hook_toolbar()

    def minimumSizeHint(self):
        return QSize(800, 600)

    def _hook_toolbar(self):
        # Menu Plot
        self.toolbar.widgets["menu_plots"].widgets["waveform"].triggered.connect(
            lambda: self._create_widget_from_toolbar(widget_name="Waveform")
        )
        self.toolbar.widgets["menu_plots"].widgets["multi_waveform"].triggered.connect(
            lambda: self._create_widget_from_toolbar(widget_name="BECMultiWaveformWidget")
        )
        self.toolbar.widgets["menu_plots"].widgets["image"].triggered.connect(
            lambda: self._create_widget_from_toolbar(widget_name="BECImageWidget")
        )
        self.toolbar.widgets["menu_plots"].widgets["motor_map"].triggered.connect(
            lambda: self._create_widget_from_toolbar(widget_name="BECMotorMapWidget")
        )

        # Menu Devices
        self.toolbar.widgets["menu_devices"].widgets["scan_control"].triggered.connect(
            lambda: self._create_widget_from_toolbar(widget_name="ScanControl")
        )
        self.toolbar.widgets["menu_devices"].widgets["positioner_box"].triggered.connect(
            lambda: self._create_widget_from_toolbar(widget_name="PositionerBox")
        )

        # Menu Utils
        self.toolbar.widgets["menu_utils"].widgets["queue"].triggered.connect(
            lambda: self._create_widget_from_toolbar(widget_name="BECQueue")
        )
        self.toolbar.widgets["menu_utils"].widgets["status"].triggered.connect(
            lambda: self._create_widget_from_toolbar(widget_name="BECStatusBox")
        )
        self.toolbar.widgets["menu_utils"].widgets["vs_code"].triggered.connect(
            lambda: self._create_widget_from_toolbar(widget_name="VSCodeEditor")
        )
        self.toolbar.widgets["menu_utils"].widgets["progress_bar"].triggered.connect(
            lambda: self._create_widget_from_toolbar(widget_name="RingProgressBar")
        )
        self.toolbar.widgets["menu_utils"].widgets["log_panel"].triggered.connect(
            lambda: self._create_widget_from_toolbar(widget_name="LogPanel")
        )

        # Icons
        self.toolbar.widgets["attach_all"].action.triggered.connect(self.attach_all)
        self.toolbar.widgets["save_state"].action.triggered.connect(self.save_state)
        self.toolbar.widgets["restore_state"].action.triggered.connect(self.restore_state)

    @SafeSlot()
    def _create_widget_from_toolbar(self, widget_name: str) -> None:
        dock_name = WidgetContainerUtils.generate_unique_name(widget_name, self.panels.keys())
        self.new(name=dock_name, widget=widget_name)

    def paintEvent(self, event: QPaintEvent):  # TODO decide if we want any default instructions
        super().paintEvent(event)
        if self._instructions_visible:
            painter = QPainter(self)
            painter.drawText(
                self.rect(),
                Qt.AlignCenter,
                "Add docks using 'new' method from CLI\n or \n Add widget docks using the toolbar",
            )

    @property
    def selected_device(self) -> str:
        gui_id = QApplication.instance().gui_id
        auto_update_config = self.client.connector.get(
            MessageEndpoints.gui_auto_update_config(gui_id)
        )
        try:
            return auto_update_config.selected_device
        except AttributeError:
            return None

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
        self.dock_area.docks = WeakValueDictionary(value)  # This can not work can it?

    @property
    def panel_list(self) -> list[BECDock]:
        """
        Get the docks in the dock area.

        Returns:
            list: The docks in the dock area.
        """
        return list(self.dock_area.docks.values())

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

    @SafeSlot(popup_error=True)
    def new(
        self,
        name: str | None = None,
        widget: str | QWidget | None = None,
        widget_name: str | None = None,
        position: Literal["bottom", "top", "left", "right", "above", "below"] = "bottom",
        relative_to: BECDock | None = None,
        closable: bool = True,
        floating: bool = False,
        row: int | None = None,
        col: int = 0,
        rowspan: int = 1,
        colspan: int = 1,
    ) -> BECDock:
        """
        Add a dock to the dock area. Dock has QGridLayout as layout manager by default.

        Args:
            name(str): The name of the dock to be displayed and for further references. Has to be unique.
            widget(str|QWidget|None): The widget to be added to the dock. While using RPC, only BEC RPC widgets from RPCWidgetHandler are allowed.
            position(Literal["bottom", "top", "left", "right", "above", "below"]): The position of the dock.
            relative_to(BECDock): The dock to which the new dock should be added relative to.
            closable(bool): Whether the dock is closable.
            floating(bool): Whether the dock is detached after creating.
            row(int): The row of the added widget.
            col(int): The column of the added widget.
            rowspan(int): The rowspan of the added widget.
            colspan(int): The colspan of the added widget.

        Returns:
            BECDock: The created dock.
        """
        dock_names = [dock._name for dock in self.panel_list]  # pylint: disable=protected-access
        if name is not None:  # Name is provided
            if name in dock_names:
                raise ValueError(
                    f"Name {name} must be unique for docks, but already exists in DockArea "
                    f"with name: {self._name} and id {self.gui_id}."
                )
        else:  # Name is not provided
            name = WidgetContainerUtils.generate_unique_name(name="dock", list_of_names=dock_names)

        dock = BECDock(name=name, parent_dock_area=self, closable=closable)
        dock.config.position = position
        self.config.docks[dock.name()] = dock.config
        # The dock.name is equal to the name passed to BECDock
        self.dock_area.addDock(dock=dock, position=position, relativeTo=relative_to)

        if len(self.dock_area.docks) <= 1:
            dock.hide_title_bar()
        elif len(self.dock_area.docks) > 1:
            for dock in self.dock_area.docks.values():
                dock.show_title_bar()

        if widget is not None:
            # Check if widget name exists.
            dock.new(
                widget=widget, name=widget_name, row=row, col=col, rowspan=rowspan, colspan=colspan
            )
        if (
            self._instructions_visible
        ):  # TODO still decide how initial instructions should be handled
            self._instructions_visible = False
            self.update()
        if floating:
            dock.detach()
        # Run broadcast update
        self._broadcast_update()
        return dock

    def _broadcast_update(self):
        rpc_register = RPCRegister()
        rpc_register.broadcast()

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
                self.remove_temp_area(temp_area)

    def remove_temp_area(self, area):
        """
        Remove a temporary area from the dock area.
        This is a patched method of pyqtgraph's removeTempArea
        """
        if area not in self.dock_area.tempAreas:
            # FIXME add some context for the logging, I am not sure which object is passed.
            # It looks like a pyqtgraph.DockArea
            logger.info(f"Attempted to remove dock_area, but was not floating.")
            return
        self.dock_area.tempAreas.remove(area)
        area.window().close()
        area.window().deleteLater()

    def cleanup(self):
        """
        Cleanup the dock area.
        """
        self.delete_all()
        self.toolbar.close()
        self.toolbar.deleteLater()
        self.dock_area.close()
        self.dock_area.deleteLater()
        super().cleanup()

    def show(self):
        """Show all windows including floating docks."""
        super().show()
        for docks in self.panels.values():
            if docks.window() is self:
                # avoid recursion
                continue
            docks.window().show()

    def hide(self):
        """Hide all windows including floating docks."""
        super().hide()
        for docks in self.panels.values():
            if docks.window() is self:
                # avoid recursion
                continue
            docks.window().hide()

    def delete_all(self) -> None:
        """
        Delete all docks.
        """
        self.attach_all()
        for dock_name in self.panels.keys():
            self.delete(dock_name)

    def delete(self, dock_name: str):
        """
        Delete a dock by name.

        Args:
            dock_name(str): The name of the dock to delete.
        """
        dock = self.dock_area.docks.pop(dock_name, None)
        self.config.docks.pop(dock_name, None)
        if dock:
            dock.close()
            dock.deleteLater()
            if len(self.dock_area.docks) <= 1:
                for dock in self.dock_area.docks.values():
                    dock.hide_title_bar()
        else:
            raise ValueError(f"Dock with name {dock_name} does not exist.")
        self._broadcast_update()

    def remove(self) -> None:
        """Remove the dock area."""
        self.close()


if __name__ == "__main__":  # pragma: no cover

    import sys

    from bec_widgets.utils.colors import set_theme

    app = QApplication([])
    set_theme("auto")
    dock_area = BECDockArea()
    dock_1 = dock_area.new(name="dock_0", widget="Waveform")
    # dock_1 = dock_area.new(name="dock_0", widget="Waveform")
    dock_area.new(widget="Waveform")
    dock_area.show()
    dock_area.setGeometry(100, 100, 800, 600)
    app.topLevelWidgets()
    app.exec_()
    sys.exit(app.exec_())
