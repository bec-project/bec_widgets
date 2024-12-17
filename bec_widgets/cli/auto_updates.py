from __future__ import annotations

import threading
from queue import Queue
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from .client import BECDockArea, BECFigure


class ScanInfo(BaseModel):
    scan_id: str
    scan_number: int
    scan_name: str
    scan_report_devices: list
    monitored_devices: list
    status: str
    model_config: dict = {"validate_assignment": True}


class AutoUpdates:
    create_default_dock: bool = False
    enabled: bool = False
    dock_name: str = None

    def __init__(self, gui: BECDockArea):
        self.gui = gui
        self._default_dock = None
        self._default_fig = None

    def start_default_dock(self):
        """
        Create a default dock for the auto updates.
        """
        self.dock_name = "default_figure"
        self._default_dock = self.gui.add_dock(self.dock_name)
        self._default_dock.add_widget("BECFigure")
        self._default_fig = self._default_dock.widget_list[0]

    @staticmethod
    def get_scan_info(msg) -> ScanInfo:
        """
        Update the script with the given data.
        """
        info = msg.info
        status = msg.status
        scan_id = msg.scan_id
        scan_number = info.get("scan_number", 0)
        scan_name = info.get("scan_name", "Unknown")
        scan_report_devices = info.get("scan_report_devices", [])
        monitored_devices = info.get("readout_priority", {}).get("monitored", [])
        monitored_devices = [dev for dev in monitored_devices if dev not in scan_report_devices]
        return ScanInfo(
            scan_id=scan_id,
            scan_number=scan_number,
            scan_name=scan_name,
            scan_report_devices=scan_report_devices,
            monitored_devices=monitored_devices,
            status=status,
        )

    def get_default_figure(self) -> BECFigure | None:
        """
        Get the default figure from the GUI.
        """
        return self._default_fig

    def do_update(self, msg):
        """
        Run the update function if enabled.
        """
        if not self.enabled:
            return
        if msg.status != "open":
            return
        info = self.get_scan_info(msg)
        return self.handler(info)

    def get_selected_device(self, monitored_devices, selected_device):
        """
        Get the selected device for the plot. If no device is selected, the first
        device in the monitored devices list is selected.
        """
        if selected_device:
            return selected_device
        if len(monitored_devices) > 0:
            sel_device = monitored_devices[0]
            return sel_device
        return None

    def handler(self, info: ScanInfo) -> None:
        """
        Default update function.
        """
        if info.scan_name == "line_scan" and info.scan_report_devices:
            return self.simple_line_scan(info)
        if info.scan_name == "grid_scan" and info.scan_report_devices:
            return self.simple_grid_scan(info)
        if info.scan_report_devices:
            return self.best_effort(info)

    def simple_line_scan(self, info: ScanInfo) -> None:
        """
        Simple line scan.
        """
        fig = self.get_default_figure()
        if not fig:
            return
        dev_x = info.scan_report_devices[0]
        selected_device = yield self.gui.selected_device
        dev_y = self.get_selected_device(info.monitored_devices, selected_device)
        if not dev_y:
            return
        yield fig.clear_all()
        yield fig.plot(
            x_name=dev_x,
            y_name=dev_y,
            label=f"Scan {info.scan_number} - {dev_y}",
            title=f"Scan {info.scan_number}",
            x_label=dev_x,
            y_label=dev_y,
        )

    def simple_grid_scan(self, info: ScanInfo) -> None:
        """
        Simple grid scan.
        """
        fig = self.get_default_figure()
        if not fig:
            return
        dev_x = info.scan_report_devices[0]
        dev_y = info.scan_report_devices[1]
        selected_device = yield self.gui.selected_device
        dev_z = self.get_selected_device(info.monitored_devices, selected_device)
        yield fig.clear_all()
        yield fig.plot(
            x_name=dev_x,
            y_name=dev_y,
            z_name=dev_z,
            label=f"Scan {info.scan_number} - {dev_z}",
            title=f"Scan {info.scan_number}",
            x_label=dev_x,
            y_label=dev_y,
        )

    def best_effort(self, info: ScanInfo) -> None:
        """
        Best effort scan.
        """
        fig = self.get_default_figure()
        if not fig:
            return
        dev_x = info.scan_report_devices[0]
        selected_device = yield self.gui.selected_device
        dev_y = self.get_selected_device(info.monitored_devices, selected_device)
        if not dev_y:
            return
        yield fig.clear_all()
        yield fig.plot(
            x_name=dev_x,
            y_name=dev_y,
            label=f"Scan {info.scan_number} - {dev_y}",
            title=f"Scan {info.scan_number}",
            x_label=dev_x,
            y_label=dev_y,
        )
