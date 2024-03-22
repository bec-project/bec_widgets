from __future__ import annotations

import importlib
import select
import subprocess
import time
import uuid
from functools import wraps
from typing import TYPE_CHECKING

from qtpy.QtCore import QCoreApplication

import bec_widgets.cli.client as client
from bec_lib import MessageEndpoints, messages
from bec_lib.connector import MessageObject
from bec_lib.device import DeviceBase
from bec_widgets.utils.bec_dispatcher import BECDispatcher

if TYPE_CHECKING:
    from bec_widgets.cli.client import BECFigure


def rpc_call(func):
    """
    A decorator for calling a function on the server.

    Args:
        func: The function to call.

    Returns:
        The result of the function call.
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.gui_is_alive():
            raise RuntimeError("GUI is not alive")
        return self._run_rpc(func.__name__, *args, **kwargs)

    return wrapper


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


def update_script(figure: BECFigure, msg):
    """
    Update the script with the given data.
    """
    info = msg.info
    status = msg.status
    scan_id = msg.scanID
    scan_number = info.get("scan_number", 0)
    scan_name = info.get("scan_name", "Unknown")
    scan_report_devices = info.get("scan_report_devices", [])
    monitored_devices = info.get("readout_priority", {}).get("monitored", [])
    monitored_devices = [dev for dev in monitored_devices if dev not in scan_report_devices]

    if scan_name == "line_scan" and scan_report_devices:
        dev_x = scan_report_devices[0]
        dev_y = get_selected_device(monitored_devices, figure.selected_device)
        print(f"Selected device: {dev_y}")
        if not dev_y:
            return
        figure.clear_all()
        plt = figure.plot(dev_x, dev_y)
        plt.set(title=f"Scan {scan_number}", x_label=dev_x, y_label=dev_y)
    elif scan_name == "grid_scan" and scan_report_devices:
        print(f"Scan {scan_number} is running")
        dev_x = scan_report_devices[0]
        dev_y = scan_report_devices[1]
        figure.clear_all()
        plt = figure.plot(dev_x, dev_y, label=f"Scan {scan_number}")
        plt.set(title=f"Scan {scan_number}", x_label=dev_x, y_label=dev_y)
    elif scan_report_devices:
        dev_x = scan_report_devices[0]
        dev_y = get_selected_device(monitored_devices, figure.selected_device)
        if not dev_y:
            return
        figure.clear_all()
        plt = figure.plot(dev_x, dev_y, label=f"Scan {scan_number}")
        plt.set(title=f"Scan {scan_number}", x_label=dev_x, y_label=dev_y)


class BECFigureClientMixin:
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._process = None
        self.update_script = update_script
        self._target_endpoint = MessageEndpoints.scan_status()
        self._selected_device = None

    @property
    def selected_device(self):
        """
        Selected device for the plot.
        """
        return self._selected_device

    @selected_device.setter
    def selected_device(self, device: str | DeviceBase):
        if isinstance(device, DeviceBase):
            self._selected_device = device.name
        elif isinstance(device, str):
            self._selected_device = device
        else:
            raise ValueError("Device must be a string or a device object")

    def _start_update_script(self) -> None:
        self._client.connector.register(
            self._target_endpoint, cb=self._handle_msg_update, parent=self
        )

    @staticmethod
    def _handle_msg_update(msg: MessageObject, parent: BECFigureClientMixin) -> None:
        if parent.update_script is not None:
            # pylint: disable=protected-access
            parent._update_script_msg_parser(msg.value)

    def _update_script_msg_parser(self, msg: messages.BECMessage) -> None:
        if isinstance(msg, messages.ScanStatusMessage):
            if not self.gui_is_alive():
                return
            if msg.status == "open":
                self.update_script(self, msg)

    def show(self) -> None:
        """
        Show the figure.
        """
        if self._process is None or self._process.poll() is not None:
            self._start_plot_process()
        while not self.gui_is_alive():
            print("Waiting for GUI to start...")
            time.sleep(1)

    def close(self) -> None:
        """
        Close the figure.
        """
        if self._process is None:
            return
        self._run_rpc("close", (), wait_for_rpc_response=False)
        self._process.kill()
        self._process = None

    def _start_plot_process(self) -> None:
        """
        Start the plot in a new process.
        """
        self._start_update_script()
        # pylint: disable=subprocess-run-check
        monitor_module = importlib.import_module("bec_widgets.cli.server")
        monitor_path = monitor_module.__file__

        command = f"python {monitor_path} --id {self._gui_id}"
        self._process = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

    def print_log(self) -> None:
        """
        Print the log of the plot process.
        """
        if self._process is None:
            return
        print(self._get_stderr_output())

    def _get_stderr_output(self) -> str:
        stderr_output = []
        while self._process.poll() is not None:
            readylist, _, _ = select.select([self._process.stderr], [], [], 0.1)
            if not readylist:
                break
            line = self._process.stderr.readline()
            if not line:
                break
            stderr_output.append(line.decode("utf-8"))
        return "".join(stderr_output)


class RPCBase:
    def __init__(self, gui_id: str = None, config: dict = None, parent=None) -> None:
        self._client = BECDispatcher().client
        self._config = config if config is not None else {}
        self._gui_id = gui_id if gui_id is not None else str(uuid.uuid4())
        self._parent = parent
        super().__init__()
        # print(f"RPCBase: {self._gui_id}")

    def __repr__(self):
        type_ = type(self)
        qualname = type_.__qualname__
        return f"<{qualname} object at {hex(id(self))}>"

    @property
    def _root(self):
        """
        Get the root widget. This is the BECFigure widget that holds
        the anchor gui_id.
        """
        parent = self
        # pylint: disable=protected-access
        while parent._parent is not None:
            parent = parent._parent
        return parent

    def _run_rpc(self, method, *args, wait_for_rpc_response=True, **kwargs):
        """
        Run the RPC call.

        Args:
            method: The method to call.
            args: The arguments to pass to the method.
            wait_for_rpc_response: Whether to wait for the RPC response.
            kwargs: The keyword arguments to pass to the method.

        Returns:
            The result of the RPC call.
        """
        request_id = str(uuid.uuid4())
        rpc_msg = messages.GUIInstructionMessage(
            action=method,
            parameter={"args": args, "kwargs": kwargs, "gui_id": self._gui_id},
            metadata={"request_id": request_id},
        )
        # print(f"RPCBase: {rpc_msg}")
        # pylint: disable=protected-access
        receiver = self._root._gui_id
        self._client.connector.set_and_publish(MessageEndpoints.gui_instructions(receiver), rpc_msg)

        if not wait_for_rpc_response:
            return None
        response = self._wait_for_response(request_id)
        # get class name
        if not response.content["accepted"]:
            raise ValueError(response.content["message"]["error"])
        msg_result = response.content["message"].get("result")
        return self._create_widget_from_msg_result(msg_result)

    def _create_widget_from_msg_result(self, msg_result):
        if msg_result is None:
            return None
        if isinstance(msg_result, list):
            return [self._create_widget_from_msg_result(res) for res in msg_result]
        if isinstance(msg_result, dict):
            if "__rpc__" not in msg_result:
                return {
                    key: self._create_widget_from_msg_result(val) for key, val in msg_result.items()
                }
            cls = msg_result.pop("widget_class", None)
            msg_result.pop("__rpc__", None)

            if not cls:
                return msg_result

            cls = getattr(client, cls)
            # print(msg_result)
            return cls(parent=self, **msg_result)
        return msg_result

    def _wait_for_response(self, request_id):
        """
        Wait for the response from the server.
        """
        response = None
        while response is None and self.gui_is_alive():
            response = self._client.connector.get(
                MessageEndpoints.gui_instruction_response(request_id)
            )
            QCoreApplication.processEvents()  # keep UI responsive (and execute signals/slots)
        return response

    def gui_is_alive(self):
        """
        Check if the GUI is alive.
        """
        heart = self._client.connector.get(MessageEndpoints.gui_heartbeat(self._root._gui_id))
        return heart is not None
