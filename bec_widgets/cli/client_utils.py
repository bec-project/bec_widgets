"""Client utilities for the BEC GUI."""

from __future__ import annotations

import json
import os
import select
import subprocess
import threading
import time
from contextlib import contextmanager
from threading import Lock
from typing import TYPE_CHECKING, Literal, TypeAlias, cast

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.utils.import_utils import lazy_import_from
from rich.console import Console
from rich.table import Table

import bec_widgets.cli.client as client
from bec_widgets.cli.rpc.rpc_base import RPCBase, RPCReference

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib.messages import GUIRegistryStateMessage
else:
    GUIRegistryStateMessage = lazy_import_from("bec_lib.messages", "GUIRegistryStateMessage")

logger = bec_logger.logger

IGNORE_WIDGETS = ["LaunchWindow"]

RegistryState: TypeAlias = dict[
    Literal["gui_id", "name", "widget_class", "config", "__rpc__", "container_proxy"],
    str | bool | dict,
]

# pylint: disable=redefined-outer-scope


def _filter_output(output: str) -> str:
    """
    Filter out the output from the process.
    """
    if "IMKClient" in output:
        # only relevant on macOS
        # see https://discussions.apple.com/thread/255761734?sortBy=rank
        return ""
    return output


def _get_output(process, logger) -> None:
    log_func = {process.stdout: logger.debug, process.stderr: logger.error}
    stream_buffer = {process.stdout: [], process.stderr: []}
    try:
        os.set_blocking(process.stdout.fileno(), False)
        os.set_blocking(process.stderr.fileno(), False)
        while process.poll() is None:
            readylist, _, _ = select.select([process.stdout, process.stderr], [], [], 1)
            for stream in (process.stdout, process.stderr):
                buf = stream_buffer[stream]
                if stream in readylist:
                    buf.append(stream.read(4096))
                output, _, remaining = "".join(buf).rpartition("\n")
                output = _filter_output(output)
                if output:
                    log_func[stream](output)
                    buf.clear()
                    buf.append(remaining)
    except Exception as e:
        logger.error(f"Error reading process output: {str(e)}")


def _start_plot_process(
    gui_id: str,
    gui_class_id: str,
    config: dict | str,
    gui_class: str = "dock_area",
    logger=None,  # FIXME change gui_class back to "launcher" later
) -> tuple[subprocess.Popen[str], threading.Thread | None]:
    """
    Start the plot in a new process.

    Logger must be a logger object with "debug" and "error" functions,
    or it can be left to "None" as default. None means output from the
    process will not be captured.
    """
    # pylint: disable=subprocess-run-check
    command = [
        "bec-gui-server",
        "--id",
        gui_id,
        "--gui_class",
        gui_class,
        "--gui_class_id",
        gui_class_id,
        "--hide",
    ]
    if config:
        if isinstance(config, dict):
            config = json.dumps(config)
        command.extend(["--config", str(config)])

    env_dict = os.environ.copy()
    env_dict["PYTHONUNBUFFERED"] = "1"

    if logger is None:
        stdout_redirect = subprocess.DEVNULL
        stderr_redirect = subprocess.DEVNULL
    else:
        stdout_redirect = subprocess.PIPE
        stderr_redirect = subprocess.PIPE

    process = subprocess.Popen(
        command,
        text=True,
        start_new_session=True,
        stdout=stdout_redirect,
        stderr=stderr_redirect,
        env=env_dict,
    )
    if logger is None:
        process_output_processing_thread = None
    else:
        process_output_processing_thread = threading.Thread(
            target=_get_output, args=(process, logger)
        )
        process_output_processing_thread.start()
    return process, process_output_processing_thread


class RepeatTimer(threading.Timer):
    """RepeatTimer class."""

    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)


# pylint: disable=protected-access
@contextmanager
def wait_for_server(client: BECGuiClient):
    """Context manager to wait for the server to start."""
    timeout = client._startup_timeout
    if not timeout:
        if client._gui_is_alive():
            # there is hope, let's wait a bit
            timeout = 1
        else:
            raise RuntimeError("GUI is not alive")
    try:
        if client._gui_started_event.wait(timeout=timeout):
            client._gui_started_timer.cancel()
            client._gui_started_timer.join()
        else:
            raise TimeoutError("Could not connect to GUI server")
    finally:
        # after initial waiting period, do not wait so much any more
        # (only relevant if GUI didn't start)
        client._startup_timeout = 0
    yield


class WidgetNameSpace:
    def __repr__(self):
        console = Console()
        table = Table(title="Available widgets for BEC CLI usage")
        table.add_column("Widget Name", justify="left", style="magenta")
        table.add_column("Description", justify="left")
        for attr, value in self.__dict__.items():
            docs = value.__doc__
            docs = docs if docs else "No description available"
            table.add_row(attr, docs)
        console.print(table)
        return ""


class AvailableWidgetsNamespace:
    """Namespace for available widgets in the BEC GUI."""

    def __init__(self):
        for widget in client.Widgets:
            name = widget.value
            if name in IGNORE_WIDGETS:
                continue
            setattr(self, name, name)

    def __repr__(self):
        console = Console()
        table = Table(title="Available widgets for BEC CLI usage")
        table.add_column("Widget Name", justify="left", style="magenta")
        table.add_column("Description", justify="left")
        for attr_name, _ in self.__dict__.items():
            docs = getattr(client, attr_name).__doc__
            docs = docs if docs else "No description available"
            table.add_row(attr_name, docs if len(docs.strip()) > 0 else "No description available")
        console.print(table)
        return ""


class BECGuiClient(RPCBase):
    """BEC GUI client class. Container for GUI applications within Python."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._lock = Lock()
        self._anchor_widget = "launcher"
        self._killed = False
        self._top_level: dict[str, RPCReference] = {}
        self._startup_timeout = 0
        self._gui_started_timer = None
        self._gui_started_event = threading.Event()
        self._process = None
        self._process_output_processing_thread = None
        self._server_registry: dict[str, RegistryState] = {}
        self._ipython_registry: dict[str, RPCReference] = {}
        self.available_widgets = AvailableWidgetsNamespace()

    ####################
    #### Client API ####
    ####################

    @property
    def launcher(self) -> RPCBase:
        """The launcher object."""
        return RPCBase(gui_id=f"{self._gui_id}:launcher", parent=self, object_name="launcher")

    def connect_to_gui_server(self, gui_id: str) -> None:
        """Connect to a GUI server"""
        # Unregister the old callback
        self._client.connector.unregister(
            MessageEndpoints.gui_registry_state(self._gui_id), cb=self._handle_registry_update
        )
        self._gui_id = gui_id

        # reset the namespace
        self._update_dynamic_namespace({})
        self._server_registry = {}
        self._top_level = {}
        self._ipython_registry = {}

        # Register the new callback
        self._client.connector.register(
            MessageEndpoints.gui_registry_state(self._gui_id),
            cb=self._handle_registry_update,
            parent=self,
            from_start=True,
        )

    @property
    def windows(self) -> dict:
        """Dictionary with dock areas in the GUI."""
        return {widget.object_name: widget for widget in self._top_level.values()}

    @property
    def window_list(self) -> list:
        """List with dock areas in the GUI."""
        return list(self._top_level.values())

    def start(self, wait: bool = False) -> None:
        """Start the GUI server."""
        return self._start(wait=wait)

    def show(self):
        """Show the GUI window."""
        if self._check_if_server_is_alive():
            return self._show_all()
        return self.start(wait=True)

    def hide(self):
        """Hide the GUI window."""
        return self._hide_all()

    def new(
        self,
        name: str | None = None,
        wait: bool = True,
        geometry: tuple[int, int, int, int] | None = None,
    ) -> client.BECDockArea:
        """Create a new top-level dock area.

        Args:
            name(str, optional): The name of the dock area. Defaults to None.
            wait(bool, optional): Whether to wait for the server to start. Defaults to True.
            geometry(tuple[int, int, int, int] | None): The geometry of the dock area (pos_x, pos_y, w, h)
        Returns:
            client.BECDockArea: The new dock area.
        """
        if not self._check_if_server_is_alive():
            self.start(wait=True)
        if wait:
            with wait_for_server(self):
                widget = self.launcher._run_rpc(
                    "launch", "dock_area", name, geometry
                )  # pylint: disable=protected-access
                return widget
        widget = self.launcher._run_rpc(
            "new_dock_area", name, geometry
        )  # pylint: disable=protected-access
        return widget

    def delete(self, name: str) -> None:
        """Delete a dock area.

        Args:
            name(str): The name of the dock area.
        """
        widget = self.windows.get(name)
        if widget is None:
            raise ValueError(f"Dock area {name} not found.")
        widget._run_rpc("close")  # pylint: disable=protected-access

    def delete_all(self) -> None:
        """Delete all dock areas."""
        for widget_name in self.windows:
            self.delete(widget_name)

    def kill_server(self) -> None:
        """Kill the GUI server."""
        # Unregister the registry state
        self._killed = True

        if self._gui_started_timer is not None:
            self._gui_started_timer.cancel()
            self._gui_started_timer.join()

        if self._process is None:
            return

        if self._process:
            logger.success("Stopping GUI...")
            self._process.terminate()
            if self._process_output_processing_thread:
                self._process_output_processing_thread.join()
            self._process.wait()
            self._process = None

        # Unregister the registry state
        self._client.connector.unregister(
            MessageEndpoints.gui_registry_state(self._gui_id), cb=self._handle_registry_update
        )
        # Remove all reference from top level
        self._top_level.clear()
        self._server_registry.clear()

    def close(self):
        """Deprecated. Use kill_server() instead."""
        # FIXME, deprecated in favor of kill, will be removed in the future
        self.kill_server()

    #########################
    #### Private methods ####
    #########################

    def _check_if_server_is_alive(self):
        """Checks if the process is alive"""
        if self._process is None:
            return False
        if self._process.poll() is not None:
            return False
        return True

    def _gui_post_startup(self):
        timeout = 60
        # Wait for 'bec' gui to be registered, this may take some time
        # After 60s timeout. Should this raise an exception on timeout?
        while time.time() < time.time() + timeout:
            if len(list(self._server_registry.keys())) < 2 or not hasattr(
                self, self._anchor_widget
            ):
                time.sleep(0.1)
            else:
                break

        self._gui_started_event.set()

    def _start_server(self, wait: bool = False) -> None:
        """
        Start the GUI server, and execute callback when it is launched
        """
        if self._process is None or self._process.poll() is not None:
            logger.success("GUI starting...")
            self._startup_timeout = 5
            self._gui_started_event.clear()
            self._process, self._process_output_processing_thread = _start_plot_process(
                self._gui_id,
                gui_class_id="bec",
                config=self._client._service_config.config,  # pylint: disable=protected-access
                logger=logger,
            )

            def gui_started_callback(callback):
                try:
                    if callable(callback):
                        callback()
                finally:
                    threading.current_thread().cancel()  # type: ignore

            self._gui_started_timer = RepeatTimer(
                0.5, lambda: self._gui_is_alive() and gui_started_callback(self._gui_post_startup)
            )
            self._gui_started_timer.start()

        if wait:
            self._gui_started_event.wait()

    def _start(self, wait: bool = False) -> None:
        self._killed = False
        self._client.connector.register(
            MessageEndpoints.gui_registry_state(self._gui_id),
            cb=self._handle_registry_update,
            parent=self,
        )
        return self._start_server(wait=wait)

    @staticmethod
    def _handle_registry_update(
        msg: dict[str, GUIRegistryStateMessage], parent: BECGuiClient
    ) -> None:
        # This was causing a deadlock during shutdown, not sure why.
        # with self._lock:
        self = parent
        self._server_registry = cast(dict[str, RegistryState], msg["data"].state)
        self._update_dynamic_namespace(self._server_registry)

    def _do_show_all(self):
        rpc_client = RPCBase(gui_id=f"{self._gui_id}:launcher", parent=self)
        rpc_client._run_rpc("show")  # pylint: disable=protected-access
        for window in self._top_level.values():
            window.show()

    def _show_all(self):
        with wait_for_server(self):
            return self._do_show_all()

    def _hide_all(self):
        with wait_for_server(self):
            rpc_client = RPCBase(gui_id=f"{self._gui_id}:launcher", parent=self)
            rpc_client._run_rpc("hide")  # pylint: disable=protected-access
            if not self._killed:
                for window in self._top_level.values():
                    window.hide()

    def _update_dynamic_namespace(self, server_registry: dict):
        """
        Update the dynamic name space with the given server registry.
        Setting the server registry to an empty dictionary will remove all widgets from the namespace.

        Args:
            server_registry (dict): The server registry
        """
        top_level_widgets: dict[str, RPCReference] = {}
        for gui_id, state in server_registry.items():
            widget = self._add_widget(state, self)
            if widget is None:
                # ignore widgets that are not supported
                continue
            # get all top-level widgets. These are widgets that have no parent
            if not state["config"].get("parent_id"):
                top_level_widgets[gui_id] = widget

        remove_from_registry = []
        for gui_id, widget in self._ipython_registry.items():
            if gui_id not in server_registry:
                remove_from_registry.append(gui_id)
        for gui_id in remove_from_registry:
            self._ipython_registry.pop(gui_id)

        removed_widgets = [
            widget.object_name for widget in self._top_level.values() if widget._is_deleted()
        ]

        for widget_name in removed_widgets:
            # the check is not strictly necessary, but better safe
            # than sorry; who knows what the user has done
            if hasattr(self, widget_name):
                delattr(self, widget_name)

        for gui_id, widget_ref in top_level_widgets.items():
            setattr(self, widget_ref.object_name, widget_ref)

        self._top_level = top_level_widgets

        for widget in self._ipython_registry.values():
            widget._refresh_references()

    def _add_widget(self, state: dict, parent: object) -> RPCReference | None:
        """Add a widget to the namespace

        Args:
            state (dict): The state of the widget from the _server_registry.
            parent (object): The parent object.
        """
        object_name = state["object_name"]
        gui_id = state["gui_id"]
        if state["widget_class"] in IGNORE_WIDGETS:
            return
        widget_class = getattr(client, state["widget_class"], None)
        if widget_class is None:
            return
        obj = self._ipython_registry.get(gui_id)
        if obj is None:
            widget = widget_class(gui_id=gui_id, object_name=object_name, parent=parent)
            self._ipython_registry[gui_id] = widget
        else:
            widget = obj
        obj = RPCReference(registry=self._ipython_registry, gui_id=gui_id)
        return obj


if __name__ == "__main__":  # pragma: no cover
    from bec_lib.client import BECClient
    from bec_lib.service_config import ServiceConfig

    try:
        config = ServiceConfig()
        bec_client = BECClient(config)
        bec_client.start()

        # Test the client_utils.py module
        gui = BECGuiClient()

        gui.start(wait=True)
        gui.new().new(widget="Waveform")
        time.sleep(10)
    finally:
        gui.kill_server()
