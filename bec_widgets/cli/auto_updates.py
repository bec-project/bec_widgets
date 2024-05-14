from __future__ import annotations

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


class AutoUpdates:
    create_default_dock: bool = False
    enabled: bool = False
    dock_name: str = None

    def __init__(self, gui: BECDockArea):
        self.gui = gui

    def start_default_dock(self):
        """
        Create a default dock for the auto updates.
        """
        dock = self.gui.add_dock("default_figure")
        dock.add_widget_bec("BECFigure")
        self.dock_name = "default_figure"

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
        dock = self.gui.panels.get(self.dock_name, [])
        if not dock:
            return None
        widgets = dock.widget_list
        if not widgets:
            return None
        return widgets[0]

    def run(self, msg):
        """
        Run the update function if enabled.
        """
        if not self.enabled:
            return
        if msg.status != "open":
            return
        info = self.get_scan_info(msg)
        self.handler(info)

    @staticmethod
    def get_selected_device(monitored_devices, selected_device):
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
            self.simple_line_scan(info)
            return
        if info.scan_name == "grid_scan" and info.scan_report_devices:
            self.simple_grid_scan(info)
            return
        if info.scan_report_devices:
            self.best_effort(info)
            return

    def simple_line_scan(self, info: ScanInfo) -> None:
        """
        Simple line scan.
        """
        fig = self.get_default_figure()
        if not fig:
            return
        dev_x = info.scan_report_devices[0]
        dev_y = self.get_selected_device(info.monitored_devices, self.gui.selected_device)
        if not dev_y:
            return
        fig.clear_all()
        plt = fig.plot(x_name=dev_x, y_name=dev_y)
        plt.set(title=f"Scan {info.scan_number}", x_label=dev_x, y_label=dev_y)

    def simple_grid_scan(self, info: ScanInfo) -> None:
        """
        Simple grid scan.
        """
        fig = self.get_default_figure()
        if not fig:
            return
        dev_x = info.scan_report_devices[0]
        dev_y = info.scan_report_devices[1]
        dev_z = self.get_selected_device(info.monitored_devices, self.gui.selected_device)
        fig.clear_all()
        plt = fig.plot(x_name=dev_x, y_name=dev_y, z_name=dev_z, label=f"Scan {info.scan_number}")
        plt.set(title=f"Scan {info.scan_number}", x_label=dev_x, y_label=dev_y)

    def best_effort(self, info: ScanInfo) -> None:
        """
        Best effort scan.
        """
        fig = self.get_default_figure()
        if not fig:
            return
        dev_x = info.scan_report_devices[0]
        dev_y = self.get_selected_device(info.monitored_devices, self.gui.selected_device)
        if not dev_y:
            return
        fig.clear_all()
        plt = fig.plot(x_name=dev_x, y_name=dev_y, label=f"Scan {info.scan_number}")
        plt.set(title=f"Scan {info.scan_number}", x_label=dev_x, y_label=dev_y)
