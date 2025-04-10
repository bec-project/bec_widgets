from __future__ import annotations

from typing import TYPE_CHECKING, Literal, overload

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.messages import ScanStatusMessage

from bec_widgets.utils.error_popups import SafeSlot

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.utils.bec_widget import BECWidget
    from bec_widgets.widgets.containers.dock.dock import BECDock
    from bec_widgets.widgets.containers.dock.dock_area import BECDockArea
    from bec_widgets.widgets.plots.image.image import Image
    from bec_widgets.widgets.plots.motor_map.motor_map import MotorMap
    from bec_widgets.widgets.plots.multi_waveform.multi_waveform import MultiWaveform
    from bec_widgets.widgets.plots.scatter_waveform.scatter_waveform import ScatterWaveform
    from bec_widgets.widgets.plots.waveform.waveform import Waveform


logger = bec_logger.logger


class AutoUpdates:
    _default_dock: BECDock

    def __init__(self, dock_area: BECDockArea):
        self.dock_area = dock_area
        self.bec_dispatcher = dock_area.bec_dispatcher
        self._default_dock = None  # type:ignore
        self.current_widget: BECWidget | None = None
        self.dock_name = None
        self._enabled = False

    def connect(self):
        """
        Establish all connections for the auto updates.
        """
        self.bec_dispatcher.connect_slot(self._on_scan_status, MessageEndpoints.scan_status())

    def disconnect(self):
        """
        Disconnect all connections for the auto updates.
        """
        self.bec_dispatcher.disconnect_slot(
            self._on_scan_status, MessageEndpoints.scan_status()  # type:ignore
        )

    @SafeSlot()
    def _on_scan_status(self, content: dict, metadata: dict) -> None:
        """
        Callback for scan status messages.
        """
        msg = ScanStatusMessage(**content, metadata=metadata)
        if not self.enabled:
            return

        self.enable_gui_highlights(True)

        match msg.status:
            case "open":
                self.on_scan_open(msg)
            case "closed":
                self.on_scan_closed(msg)
            case ["aborted", "halted"]:
                self.on_scan_abort(msg)
            case _:
                pass

    def start_default_dock(self):
        """
        Create a default dock for the auto updates.
        """
        self.dock_name = "update_dock"
        self._default_dock = self.dock_area.new(self.dock_name)
        self.current_widget = self._default_dock.new("Waveform")

    @overload
    def set_dock_to_widget(self, widget: Literal["Waveform"]) -> Waveform: ...

    @overload
    def set_dock_to_widget(self, widget: Literal["Image"]) -> Image: ...

    @overload
    def set_dock_to_widget(self, widget: Literal["ScatterWaveform"]) -> ScatterWaveform: ...

    @overload
    def set_dock_to_widget(self, widget: Literal["MotorMap"]) -> MotorMap: ...

    @overload
    def set_dock_to_widget(self, widget: Literal["MultiWaveform"]) -> MultiWaveform: ...

    def set_dock_to_widget(
        self,
        widget: Literal["Waveform", "Image", "ScatterWaveform", "MotorMap", "MultiWaveForm"] | str,
    ) -> BECWidget:
        """
        Set the dock to the widget.

        Args:
            widget (str): The widget to set the dock to. Must be the name of a valid widget class.

        Returns:
            BECWidget: The widget that was set.
        """
        if self._default_dock is None or self.current_widget is None:
            logger.warning(
                f"Auto Updates: No default dock found. Creating a new one with name {self.dock_name}"
            )
            self.start_default_dock()
        assert self.current_widget is not None

        if not self.current_widget.__class__.__name__ == widget:
            self._default_dock.delete(self.current_widget.object_name)
            self.current_widget = self._default_dock.new(widget)
        return self.current_widget

    def get_selected_device(
        self, monitored_devices, selected_device: str | None = None
    ) -> str | None:
        """
        Get the selected device for the plot. If no device is selected, the first
        device in the monitored devices list is selected.
        """

        if selected_device is None:
            selected_device = self.dock_area.selected_device
        if selected_device:
            return selected_device
        if len(monitored_devices) > 0:
            sel_device = monitored_devices[0]
            return sel_device
        return None

    def enable_gui_highlights(self, enable: bool) -> None:
        """
        Enable or disable GUI highlights.

        Args:
            enable (bool): Whether to enable or disable the highlights.
        """
        if enable:
            title = self.dock_area.window().windowTitle()
            if " [Auto Updates]" in title:
                return
            self.dock_area.window().setWindowTitle(f"{title} [Auto Updates]")
        else:
            title = self.dock_area.window().windowTitle()
            self.dock_area.window().setWindowTitle(title.replace(" [Auto Updates]", ""))

    @property
    def enabled(self) -> bool:
        """
        Get the enabled status of the auto updates.
        """
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """
        Set the enabled status of the auto updates.
        """
        if self._enabled == value:
            return
        self._enabled = value

        if value:
            self.connect()
            self.enable_gui_highlights(True)
            self.on_start()
        else:
            self.disconnect()
            self.enable_gui_highlights(False)
            self.on_stop()

    ########################################################################
    ################# Update Functions #####################################
    ########################################################################

    def simple_line_scan(self, info: ScanStatusMessage) -> None:
        """
        Simple line scan.

        Args:
            info (ScanStatusMessage): The scan status message.
        """

        # Set the dock to the waveform widget
        wf = self.set_dock_to_widget("Waveform")

        # Get the scan report devices reported by the scan
        dev_x = info.scan_report_devices[0]  # type:ignore

        # For the y axis, get the selected device
        dev_y = self.get_selected_device(info.readout_priority["monitored"])  # type:ignore
        if not dev_y:
            return

        # Clear the waveform widget and plot the data
        # with the scan number and device names
        # as the label and title
        wf.clear_all()
        wf.plot(
            x_name=dev_x,
            y_name=dev_y,
            label=f"Scan {info.scan_number} - {dev_y}",
            title=f"Scan {info.scan_number}",
            x_label=dev_x,
            y_label=dev_y,
        )

        logger.info(
            f"Auto Update [simple_line_scan]: Started plot with: x_name={dev_x}, y_name={dev_y}"
        )

    def simple_grid_scan(self, info: ScanStatusMessage) -> None:
        """
        Simple grid scan.

        Args:
            info (ScanStatusMessage): The scan status message.
        """
        # Set the dock to the scatter waveform widget
        scatter = self.set_dock_to_widget("ScatterWaveform")

        # Get the scan report devices reported by the scan
        dev_x, dev_y = info.scan_report_devices[0], info.scan_report_devices[1]  # type:ignore
        dev_z = self.get_selected_device(info.readout_priority["monitored"])  # type:ignore

        # Clear the scatter waveform widget and plot the data
        scatter.clear_all()
        scatter.plot(
            x_name=dev_x, y_name=dev_y, z_name=dev_z, label=f"Scan {info.scan_number} - {dev_z}"
        )

        logger.info(
            f"Auto Update [simple_grid_scan]: Started plot with: x_name={dev_x}, y_name={dev_y}, z_name={dev_z}"
        )

    def best_effort(self, info: ScanStatusMessage) -> None:
        """
        Best effort scan.

        Args:
            info (ScanStatusMessage): The scan status message.
        """

        # If the scan report devices are empty, there is nothing we can do
        if not info.scan_report_devices:
            return
        dev_x = info.scan_report_devices[0]  # type:ignore
        dev_y = self.get_selected_device(info.readout_priority["monitored"])  # type:ignore
        if not dev_y:
            return

        # Set the dock to the waveform widget
        wf = self.set_dock_to_widget("Waveform")

        # Clear the waveform widget and plot the data
        wf.clear_all()
        wf.plot(
            x_name=dev_x,
            y_name=dev_y,
            label=f"Scan {info.scan_number} - {dev_y}",
            title=f"Scan {info.scan_number}",
            x_label=dev_x,
            y_label=dev_y,
        )

        logger.info(f"Auto Update [best_effort]: Started plot with: x_name={dev_x}, y_name={dev_y}")

    #######################################################################
    ################# GUI Callbacks #######################################
    #######################################################################

    def on_start(self) -> None:
        """
        Procedure to run when the auto updates are enabled.
        """
        self.start_default_dock()

    def on_stop(self) -> None:
        """
        Procedure to run when the auto updates are disabled.
        """

    def on_scan_open(self, msg: ScanStatusMessage) -> None:
        """
        Procedure to run when a scan starts.

        Args:
            msg (ScanStatusMessage): The scan status message.
        """
        if msg.scan_name == "line_scan" and msg.scan_report_devices:
            return self.simple_line_scan(msg)
        if msg.scan_name == "grid_scan" and msg.scan_report_devices:
            return self.simple_grid_scan(msg)
        if msg.scan_report_devices:
            return self.best_effort(msg)
        return None

    def on_scan_closed(self, msg: ScanStatusMessage) -> None:
        """
        Procedure to run when a scan ends.

        Args:
            msg (ScanStatusMessage): The scan status message.
        """

    def on_scan_abort(self, msg: ScanStatusMessage) -> None:
        """
        Procedure to run when a scan is aborted.

        Args:
            msg (ScanStatusMessage): The scan status message.
        """
