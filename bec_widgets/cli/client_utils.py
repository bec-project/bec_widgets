import importlib
import select
import subprocess
import uuid

from functools import wraps

from qtpy.QtCore import QCoreApplication

import bec_widgets.cli.client as client
from bec_lib import MessageEndpoints, messages
from bec_widgets.utils.bec_dispatcher import BECDispatcher


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
        return self._run_rpc(func.__name__, *args, **kwargs)

    return wrapper


class BECFigureClientMixin:
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._process = None

    def show(self) -> None:
        """
        Show the figure.
        """
        if self._process is None or self._process.poll() is not None:
            self._start_plot_process()

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

    def __del__(self) -> None:
        self.close()


class RPCBase:
    def __init__(self, gui_id: str = None, config: dict = None, parent=None) -> None:
        self._client = BECDispatcher().client
        self._config = config if config is not None else {}
        self._gui_id = gui_id if gui_id is not None else str(uuid.uuid4())
        self._parent = parent
        super().__init__()
        print(f"RPCBase: {self._gui_id}")

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
        print(f"RPCBase: {rpc_msg}")
        # pylint: disable=protected-access
        receiver = self._root._gui_id
        self._client.connector.send(MessageEndpoints.gui_instructions(receiver), rpc_msg)

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
                return msg_result
            cls = msg_result.pop("widget_class", None)
            msg_result.pop("__rpc__", None)

            if not cls:
                return msg_result

            cls = getattr(client, cls)
            print(msg_result)
            return cls(parent=self, **msg_result)
        return msg_result

    def _wait_for_response(self, request_id):
        """
        Wait for the response from the server.
        """
        response = None
        while response is None:
            response = self._client.connector.get(
                MessageEndpoints.gui_instruction_response(request_id)
            )
            QCoreApplication.processEvents()  # keep UI responsive (and execute signals/slots)
        return response
