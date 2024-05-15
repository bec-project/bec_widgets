from __future__ import annotations

import importlib
import importlib.metadata as imd
import os
import select
import subprocess
import sys
import threading
import time
import uuid
from functools import wraps
from typing import TYPE_CHECKING

from bec_lib.endpoints import MessageEndpoints
from bec_lib.service_config import ServiceConfig
from bec_lib.utils.import_utils import isinstance_based_on_class_name, lazy_import, lazy_import_from
from qtpy.QtCore import QCoreApplication

import bec_widgets.cli.client as client

if TYPE_CHECKING:
    from bec_lib.device import DeviceBase

    from bec_widgets.cli.client import BECDockArea, BECFigure

messages = lazy_import("bec_lib.messages")
# from bec_lib.connector import MessageObject
MessageObject = lazy_import_from("bec_lib.connector", ("MessageObject",))
BECDispatcher = lazy_import_from("bec_widgets.utils.bec_dispatcher", ("BECDispatcher",))


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
        # we could rely on a strict type check here, but this is more flexible
        # moreover, it would anyway crash for objects...
        out = []
        for arg in args:
            if hasattr(arg, "name"):
                arg = arg.name
            out.append(arg)
        args = tuple(out)
        for key, val in kwargs.items():
            if hasattr(val, "name"):
                kwargs[key] = val.name
        if not self.gui_is_alive():
            raise RuntimeError("GUI is not alive")
        return self._run_rpc(func.__name__, *args, **kwargs)

    return wrapper


class BECGuiClientMixin:
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._process = None
        self.update_script = self._get_update_script()
        self._target_endpoint = MessageEndpoints.scan_status()
        self._selected_device = None
        self.stderr_output = []

    def _get_update_script(self) -> AutoUpdates:
        eps = imd.entry_points(group="bec.widgets.auto_updates")
        for ep in eps:
            if ep.name == "plugin_widgets_update":
                return ep.load()(figure=self)
        return None

    @property
    def selected_device(self):
        """
        Selected device for the plot.
        """
        return self._selected_device

    @selected_device.setter
    def selected_device(self, device: str | DeviceBase):
        if isinstance_based_on_class_name(device, "bec_lib.device.DeviceBase"):
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
    def _handle_msg_update(msg: MessageObject, parent: BECGuiClientMixin) -> None:
        if parent.update_script is not None:
            # pylint: disable=protected-access
            parent._update_script_msg_parser(msg.value)

    def _update_script_msg_parser(self, msg: messages.BECMessage) -> None:
        if isinstance(msg, messages.ScanStatusMessage):
            if not self.gui_is_alive():
                return
            self.update_script.run(msg)

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
        if self.gui_is_alive():
            self._run_rpc("close", (), wait_for_rpc_response=True)
        else:
            self._run_rpc("close", (), wait_for_rpc_response=False)
        self._process.terminate()
        self._process_output_processing_thread.join()
        self._process = None
        self._client.shutdown()

    def _start_plot_process(self) -> None:
        """
        Start the plot in a new process.
        """
        self._start_update_script()
        # pylint: disable=subprocess-run-check
        config = self._client._service_config.redis
        monitor_module = importlib.import_module("bec_widgets.cli.server")
        monitor_path = monitor_module.__file__
        gui_class = self.__class__.__name__

        command = [
            sys.executable,
            "-u",
            monitor_path,
            "--id",
            self._gui_id,
            "--config",
            config,
            "--gui_class",
            gui_class,
        ]
        self._process = subprocess.Popen(
            command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self._process_output_processing_thread = threading.Thread(target=self._get_output)
        self._process_output_processing_thread.start()

    def print_log(self) -> None:
        """
        Print the log of the plot process.
        """
        if self._process is None:
            return
        print("".join(self.stderr_output))
        # Flush list
        self.stderr_output.clear()

    def _get_output(self) -> str:
        try:
            os.set_blocking(self._process.stdout.fileno(), False)
            os.set_blocking(self._process.stderr.fileno(), False)
            while self._process.poll() is None:
                readylist, _, _ = select.select(
                    [self._process.stdout, self._process.stderr], [], [], 1
                )
                if self._process.stdout in readylist:
                    output = self._process.stdout.read(1024)
                    if output:
                        print(output, end="")
                if self._process.stderr in readylist:
                    error_output = self._process.stderr.read(1024)
                    if error_output:
                        print(error_output, end="", file=sys.stderr)
                        self.stderr_output.append(error_output)
        except Exception as e:
            print(f"Error reading process output: {str(e)}")


class RPCResponseTimeoutError(Exception):
    """Exception raised when an RPC response is not received within the expected time."""

    def __init__(self, request_id, timeout):
        super().__init__(
            f"RPC response not received within {timeout} seconds for request ID {request_id}"
        )


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

    def _wait_for_response(self, request_id: str, timeout: int = 5):
        """
        Wait for the response from the server.

        Args:
            request_id(str): The request ID.
            timeout(int): The timeout in seconds.

        Returns:
            The response from the server.
        """
        start_time = time.time()
        response = None

        while response is None and self.gui_is_alive() and (time.time() - start_time) < timeout:
            response = self._client.connector.get(
                MessageEndpoints.gui_instruction_response(request_id)
            )
            QCoreApplication.processEvents()  # keep UI responsive (and execute signals/slots)
        if response is None and (time.time() - start_time) >= timeout:
            raise RPCResponseTimeoutError(request_id, timeout)

        return response

    def gui_is_alive(self):
        """
        Check if the GUI is alive.
        """
        heart = self._client.connector.get(MessageEndpoints.gui_heartbeat(self._root._gui_id))
        return heart is not None
