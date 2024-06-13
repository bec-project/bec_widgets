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
from bec_lib.utils.import_utils import isinstance_based_on_class_name, lazy_import, lazy_import_from
from qtpy.QtCore import QEventLoop, QSocketNotifier, QTimer

import bec_widgets.cli.client as client
from bec_widgets.cli.auto_updates import AutoUpdates

if TYPE_CHECKING:
    from bec_lib.device import DeviceBase

    from bec_widgets.cli.client import BECDockArea, BECFigure

from bec_lib.serialization import MsgpackSerialization

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


def _get_output(process) -> None:
    try:
        os.set_blocking(process.stdout.fileno(), False)
        os.set_blocking(process.stderr.fileno(), False)
        while process.poll() is None:
            readylist, _, _ = select.select([process.stdout, process.stderr], [], [], 1)
            if process.stdout in readylist:
                output = process.stdout.read(1024)
                if output:
                    print(output, end="")
            if process.stderr in readylist:
                error_output = process.stderr.read(1024)
                if error_output:
                    print(error_output, end="", file=sys.stderr)
    except Exception as e:
        print(f"Error reading process output: {str(e)}")


def _start_plot_process(gui_id, gui_class, config) -> None:
    """
    Start the plot in a new process.
    """
    # pylint: disable=subprocess-run-check
    monitor_module = importlib.import_module("bec_widgets.cli.server")
    monitor_path = monitor_module.__file__

    command = [
        sys.executable,
        "-u",
        monitor_path,
        "--id",
        gui_id,
        "--config",
        config,
        "--gui_class",
        gui_class.__name__,
    ]
    process = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process_output_processing_thread = threading.Thread(target=_get_output, args=(process,))
    process_output_processing_thread.start()
    return process, process_output_processing_thread


class BECGuiClientMixin:
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._process = None
        self._process_output_processing_thread = None
        self.auto_updates = self._get_update_script()
        self._target_endpoint = MessageEndpoints.scan_status()
        self._selected_device = None
        self.stderr_output = []

    def _get_update_script(self) -> AutoUpdates | None:
        eps = imd.entry_points(group="bec.widgets.auto_updates")
        for ep in eps:
            if ep.name == "plugin_widgets_update":
                try:
                    return ep.load()(gui=self)
                except Exception as e:
                    print(f"Error loading auto update script from plugin: {str(e)}")
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
        if parent.auto_updates is not None:
            # pylint: disable=protected-access
            parent._update_script_msg_parser(msg.value)

    def _update_script_msg_parser(self, msg: messages.BECMessage) -> None:
        if isinstance(msg, messages.ScanStatusMessage):
            if not self.gui_is_alive():
                return
            self.auto_updates.run(msg)

    def show(self) -> None:
        """
        Show the figure.
        """
        if self._process is None or self._process.poll() is not None:
            self._start_update_script()
            self._process, self._process_output_processing_thread = _start_plot_process(
                self._gui_id, self.__class__, self._client._service_config.redis
            )
        while not self.gui_is_alive():
            print("Waiting for GUI to start...")
            time.sleep(1)

    def close(self) -> None:
        """
        Close the figure.
        """
        self._client.shutdown()
        if self._process:
            self._process.terminate()
            self._process_output_processing_thread.join()
            self._process = None

    def print_log(self) -> None:
        """
        Print the log of the plot process.
        """
        if self._process is None:
            return
        print("".join(self.stderr_output))
        # Flush list
        self.stderr_output.clear()


class RPCResponseTimeoutError(Exception):
    """Exception raised when an RPC response is not received within the expected time."""

    def __init__(self, request_id, timeout):
        super().__init__(
            f"RPC response not received within {timeout} seconds for request ID {request_id}"
        )


class QtRedisMessageWaiter:
    def __init__(self, redis_connector, message_to_wait):
        self.ev_loop = QEventLoop()
        self.response = None
        self.connector = redis_connector
        self.message_to_wait = message_to_wait
        self.pubsub = redis_connector._redis_conn.pubsub()
        self.pubsub.subscribe(self.message_to_wait.endpoint)
        fd = self.pubsub.connection._sock.fileno()
        self.notifier = QSocketNotifier(fd, QSocketNotifier.Read)
        self.notifier.activated.connect(self._pubsub_readable)

    def _msg_received(self, msg_obj):
        self.response = msg_obj.value
        self.ev_loop.quit()

    def wait(self, timeout=1):
        timer = QTimer()
        timer.singleShot(timeout * 1000, self.ev_loop.quit)
        self.ev_loop.exec_()
        timer.stop()
        self.notifier.setEnabled(False)
        self.pubsub.close()
        return self.response

    def _pubsub_readable(self, fd):
        while True:
            msg = self.pubsub.get_message()
            if msg:
                if msg["type"] == "subscribe":
                    # get_message buffers, so we may already have the answer
                    # let's check...
                    continue
                else:
                    break
            else:
                return
        channel = msg["channel"].decode()
        msg = MessageObject(topic=channel, value=MsgpackSerialization.loads(msg["data"]))
        self.connector._execute_callback(self._msg_received, msg, {})


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

    def _run_rpc(self, method, *args, wait_for_rpc_response=True, timeout=3, **kwargs):
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
        if wait_for_rpc_response:
            redis_msg = QtRedisMessageWaiter(
                self._client.connector, MessageEndpoints.gui_instruction_response(request_id)
            )

        self._client.connector.set_and_publish(MessageEndpoints.gui_instructions(receiver), rpc_msg)

        if wait_for_rpc_response:
            response = redis_msg.wait(timeout)

            if response is None:
                raise RPCResponseTimeoutError(request_id, timeout)

            # get class name
            if not response.accepted:
                raise ValueError(response.message["error"])
            msg_result = response.message.get("result")
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

    def gui_is_alive(self):
        """
        Check if the GUI is alive.
        """
        heart = self._client.connector.get(MessageEndpoints.gui_heartbeat(self._root._gui_id))
        return heart is not None
