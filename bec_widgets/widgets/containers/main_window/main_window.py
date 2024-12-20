from bec_lib.endpoints import MessageEndpoints
from bec_lib.utils.import_utils import lazy_import, lazy_import_from
from qtpy.QtWidgets import QApplication, QMainWindow

from bec_widgets.utils import BECConnector
from bec_widgets.widgets.containers.dock.dock_area import BECDockArea

messages = lazy_import("bec_lib.messages")
# from bec_lib.connector import MessageObject
MessageObject = lazy_import_from("bec_lib.connector", ("MessageObject",))

from pydantic import BaseModel


class ScanInfo(BaseModel):
    scan_id: str
    scan_number: int
    scan_name: str
    scan_report_devices: list
    monitored_devices: list
    status: str
    model_config: dict = {"validate_assignment": True}


class BECMainWindow(QMainWindow, BECConnector):
    def __init__(self, *args, **kwargs):
        BECConnector.__init__(self, **kwargs)
        QMainWindow.__init__(self, *args, **kwargs)

    def _dump(self):
        """Return a dictionary with informations about the application state, for use in tests"""
        # TODO: ModularToolBar and something else leak top-level widgets (3 or 4 QMenu + 2 QWidget);
        # so, a filtering based on title is applied here, but the solution is to not have those widgets
        # as top-level (so for now, a window with no title does not appear in _dump() result)

        # NOTE: the main window itself is excluded, since we want to dump dock areas
        info = {
            tlw.gui_id: {
                "title": tlw.windowTitle(),
                "visible": tlw.isVisible(),
                "class": str(type(tlw)),
            }
            for tlw in QApplication.instance().topLevelWidgets()
            if tlw is not self and tlw.windowTitle()
        }
        # Add the main window dock area
        info[self.centralWidget().gui_id] = {
            "title": self.windowTitle(),
            "visible": self.isVisible(),
            "class": str(type(self.centralWidget())),
        }
        return info

    def new_dock_area(self, name):
        dock_area = BECDockArea()
        dock_area.resize(dock_area.minimumSizeHint())
        dock_area.window().setWindowTitle(name)
        dock_area.show()
        return dock_area

    def install_auto_update(self):
        dock_area = self.centralWidget()
        figure_dock = dock_area.add_dock("default_figure")
        self.auto_update_fig = figure_dock.add_widget("BECFigure")
        self.client.connector.register(MessageEndpoints.scan_status(), cb=self._handle_msg_update)

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

    def _handle_msg_update(self, msg: MessageObject) -> None:
        msg = msg.value
        if isinstance(msg, messages.ScanStatusMessage):
            return self.do_update(msg)

    def get_scan_info(self, msg) -> ScanInfo:
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

    def do_update(self, msg):
        if msg.status != "open":
            return
        info = self.get_scan_info(msg)
        return self.handler(info)

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

    def simple_line_scan(self, info: ScanInfo) -> None:
        """
        Simple line scan.
        """
        fig = self.auto_update_fig
        if not fig:
            return
        dev_x = info.scan_report_devices[0]
        dev_y = self.get_selected_device(info.monitored_devices, self.selected_device)
        if not dev_y:
            return
        fig.clear_all()
        fig.plot(
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
        fig = self.auto_update_fig
        if not fig:
            return
        dev_x = info.scan_report_devices[0]
        dev_y = info.scan_report_devices[1]
        dev_z = self.get_selected_device(info.monitored_devices, self.selected_device)
        fig.clear_all()
        fig.plot(
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
        fig = self.auto_update_fig
        if not fig:
            return
        dev_x = info.scan_report_devices[0]
        dev_y = self.get_selected_device(info.monitored_devices, self.selected_device)
        if not dev_y:
            return
        fig.clear_all()
        fig.plot(
            x_name=dev_x,
            y_name=dev_y,
            label=f"Scan {info.scan_number} - {dev_y}",
            title=f"Scan {info.scan_number}",
            x_label=dev_x,
            y_label=dev_y,
        )
