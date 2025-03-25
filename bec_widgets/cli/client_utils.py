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
from typing import TYPE_CHECKING, Any

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.utils.import_utils import lazy_import, lazy_import_from
from rich.console import Console
from rich.table import Table

import bec_widgets.cli.client as client
from bec_widgets.cli.rpc.rpc_base import RPCBase, RPCReference

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib.redis_connector import StreamMessage
else:
    StreamMessage = lazy_import_from("bec_lib.redis_connector", ("StreamMessage",))

logger = bec_logger.logger

IGNORE_WIDGETS = ["BECDockArea", "BECDock"]

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
    gui_id: str, gui_class: type, gui_class_id: str, config: dict | str, logger=None
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
        gui_class.__name__,
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
        self._default_dock_name = "bec"
        self._auto_updates_enabled = True
        self._auto_updates = None
        self._killed = False
        self._top_level: dict[str, RPCBase] = {}  # TODO should be more general than just DockArea
        self._startup_timeout = 0
        self._gui_started_timer = None
        self._gui_started_event = threading.Event()
        self._process = None
        self._process_output_processing_thread = None
        self._exposed_widgets = []
        self._server_registry = {}
        self._ipython_registry = {}
        self.available_widgets = AvailableWidgetsNamespace()

    ####################
    #### Client API ####
    ####################

    def connect_to_gui_server(self, gui_id: str) -> None:
        """Connect to a GUI server"""
        # Unregister the old callback
        self._client.connector.unregister(
            MessageEndpoints.gui_registry_state(self._gui_id), cb=self._handle_registry_update
        )
        self._gui_id = gui_id
        # Get the registry state
        msgs = self._client.connector.xread(
            MessageEndpoints.gui_registry_state(self._gui_id), count=1
        )
        if msgs:
            self._handle_registry_update(msgs[0])
        # Register the new callback
        self._client.connector.register(
            MessageEndpoints.gui_registry_state(self._gui_id), cb=self._handle_registry_update
        )
        self._update_dynamic_namespace()  # FIXME don't refresh the namespace
        # TODO do a cleanup of the previous server...

    @property
    def windows(self) -> dict:
        """Dictionary with dock areas in the GUI."""
        return self._top_level

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
                rpc_client = RPCBase(gui_id=f"{self._gui_id}:window", parent=self)
                widget = rpc_client._run_rpc(
                    "new_dock_area", name, geometry
                )  # pylint: disable=protected-access
                return widget
        rpc_client = RPCBase(gui_id=f"{self._gui_id}:window", parent=self)
        widget = rpc_client._run_rpc(
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
            if len(list(self._server_registry.keys())) == 0:
                time.sleep(0.1)
            else:
                break
        self._do_show_all()
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
                self.__class__,
                gui_class_id=self._default_dock_name,
                config=self._client._service_config.config,  # pylint: disable=protected-access
                logger=logger,
            )

            def gui_started_callback(callback):
                try:
                    if callable(callback):
                        callback()
                finally:
                    threading.current_thread().cancel()

            self._gui_started_timer = RepeatTimer(
                0.5, lambda: self._gui_is_alive() and gui_started_callback(self._gui_post_startup)
            )
            self._gui_started_timer.start()

        if wait:
            self._gui_started_event.wait()

    def _dump(self):
        rpc_client = RPCBase(gui_id=f"{self._gui_id}:window", parent=self)
        return rpc_client._run_rpc("_dump")

    def _start(self, wait: bool = False) -> None:
        self._killed = False
        self._client.connector.register(
            MessageEndpoints.gui_registry_state(self._gui_id), cb=self._handle_registry_update
        )
        return self._start_server(wait=wait)

    def _handle_registry_update(self, msg: StreamMessage) -> None:
        # This was causing a deadlock during shutdown, not sure why.
        # with self._lock:
        self._server_registry = msg["data"].state
        self._update_dynamic_namespace()

    def _do_show_all(self):
        rpc_client = RPCBase(gui_id=f"{self._gui_id}:window", parent=self)
        rpc_client._run_rpc("show")  # pylint: disable=protected-access
        for window in self._top_level.values():
            window.show()

    def _show_all(self):
        with wait_for_server(self):
            return self._do_show_all()

    def _hide_all(self):
        with wait_for_server(self):
            rpc_client = RPCBase(gui_id=f"{self._gui_id}:window", parent=self)
            rpc_client._run_rpc("hide")  # pylint: disable=protected-access
            if not self._killed:
                for window in self._top_level.values():
                    window.hide()

    def _update_dynamic_namespace(self):
        """Update the dynamic name space"""
        # Clear the top level
        self._top_level.clear()
        # First we update the name space based on the new registry state
        self._add_registry_to_namespace()
        # Then we clear the ipython registry from old objects
        self._cleanup_ipython_registry()

    def _cleanup_ipython_registry(self):
        """Cleanup the ipython registry"""
        names_in_registry = list(self._ipython_registry.keys())
        names_in_server_state = list(self._server_registry.keys())
        remove_ids = list(set(names_in_registry) - set(names_in_server_state))
        for widget_id in remove_ids:
            self._ipython_registry.pop(widget_id)
        self._cleanup_rpc_references_on_rpc_base(remove_ids)
        # Clear the exposed widgets
        self._exposed_widgets.clear()  # No longer needed I think

    def _cleanup_rpc_references_on_rpc_base(self, remove_ids: list[str]) -> None:
        """Cleanup the rpc references on the RPCBase object"""
        if not remove_ids:
            return
        for widget in self._ipython_registry.values():
            to_delete = []
            for attr_name, gui_id in widget._rpc_references.items():
                if gui_id in remove_ids:
                    to_delete.append(attr_name)
            for attr_name in to_delete:
                if hasattr(widget, attr_name):
                    delattr(widget, attr_name)
                if attr_name.startswith("elements."):
                    delattr(widget.elements, attr_name.split(".")[1])
                widget._rpc_references.pop(attr_name)

    def _set_dynamic_attributes(self, obj: object, name: str, value: Any) -> None:
        """Add an object to the namespace"""
        setattr(obj, name, value)

    def _update_rpc_references(self, widget: RPCBase, name: str, gui_id: str) -> None:
        """Update the RPC references"""
        widget._rpc_references[name] = gui_id

    def _add_registry_to_namespace(self) -> None:
        """Add registry to namespace"""
        # Add dock areas
        dock_area_states = [
            state
            for state in self._server_registry.values()
            if state["widget_class"] == "BECDockArea"
        ]
        for state in dock_area_states:
            dock_area_ref = self._add_widget(state, self)
            dock_area = self._ipython_registry.get(dock_area_ref._gui_id)
            if not hasattr(dock_area, "elements"):
                self._set_dynamic_attributes(dock_area, "elements", WidgetNameSpace())
            self._set_dynamic_attributes(self, dock_area.widget_name, dock_area_ref)
            # Keep track of rpc references on RPCBase object
            self._update_rpc_references(self, dock_area.widget_name, dock_area_ref._gui_id)
            # Add dock_area to the top level
            self._top_level[dock_area_ref.widget_name] = dock_area_ref
            self._exposed_widgets.append(dock_area_ref._gui_id)

            # Add docks
            dock_states = [
                state
                for state in self._server_registry.values()
                if state["config"].get("parent_id", "") == dock_area_ref._gui_id
            ]
            for state in dock_states:
                dock_ref = self._add_widget(state, dock_area)
                dock = self._ipython_registry.get(dock_ref._gui_id)
                self._set_dynamic_attributes(dock_area, dock_ref.widget_name, dock_ref)
                # Keep track of rpc references on RPCBase object
                self._update_rpc_references(dock_area, dock_ref.widget_name, dock_ref._gui_id)
                # Keep track of exposed docks
                self._exposed_widgets.append(dock_ref._gui_id)

                # Add widgets
                widget_states = [
                    state
                    for state in self._server_registry.values()
                    if state["config"].get("parent_id", "") == dock_ref._gui_id
                ]
                for state in widget_states:
                    widget_ref = self._add_widget(state, dock)
                    self._set_dynamic_attributes(dock, widget_ref.widget_name, widget_ref)
                    self._set_dynamic_attributes(
                        dock_area.elements, widget_ref.widget_name, widget_ref
                    )
                    # Keep track of rpc references on RPCBase object
                    self._update_rpc_references(
                        dock_area, f"elements.{widget_ref.widget_name}", widget_ref._gui_id
                    )
                    self._update_rpc_references(dock, widget_ref.widget_name, widget_ref._gui_id)
                    # Keep track of exposed widgets
                    self._exposed_widgets.append(widget_ref._gui_id)

    def _add_widget(self, state: dict, parent: object) -> RPCReference:
        """Add a widget to the namespace

        Args:
            state (dict): The state of the widget from the _server_registry.
            parent (object): The parent object.
        """
        name = state["name"]
        gui_id = state["gui_id"]
        widget_class = getattr(client, state["widget_class"])
        obj = self._ipython_registry.get(gui_id)
        if obj is None:
            widget = widget_class(gui_id=gui_id, name=name, parent=parent)
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
