"""Client utilities for the BEC GUI."""

from __future__ import annotations

import importlib
import importlib.metadata as imd
import json
import os
import select
import subprocess
import threading
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.utils.import_utils import lazy_import, lazy_import_from
from rich.console import Console
from rich.table import Table

import bec_widgets.cli.client as client
from bec_widgets.cli.auto_updates import AutoUpdates
from bec_widgets.cli.rpc.rpc_base import RPCBase

if TYPE_CHECKING:
    from bec_lib import messages
    from bec_lib.connector import MessageObject
    from bec_lib.device import DeviceBase
    from bec_lib.redis_connector import StreamMessage
else:
    messages = lazy_import("bec_lib.messages")
    # from bec_lib.connector import MessageObject
    MessageObject = lazy_import_from("bec_lib.connector", ("MessageObject",))
    StreamMessage = lazy_import_from("bec_lib.redis_connector", ("StreamMessage",))

logger = bec_logger.logger


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
) -> None:
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
        return f""


class AvailableWidgetsNamespace:
    """Namespace for available widgets in the BEC GUI."""

    def __init__(self):
        for widget in client.Widgets:
            name = widget.value
            if name in ["BECDockArea", "BECDock"]:
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
        return ""  # f"<{self.__class__.__name__}>"


class BECDockArea(client.BECDockArea):
    """Extend the BECDockArea class and add namespaces to access widgets of docks."""

    def __init__(self, gui_id=None, config=None, name=None, parent=None):
        super().__init__(gui_id, config, name, parent)
        # Add namespaces for DockArea
        self.elements = WidgetNameSpace()

    def delete(self, dock_name):
        # Don't close the bec dock area
        if dock_name == "bec":
            raise ValueError("Cannot delete the bec dock area")
        super().delete(dock_name)

    def remove(self):
        if self._name == "bec":
            raise ValueError("Cannot delete the bec dock area")
        super().remove()


class BECGuiClient(RPCBase):
    """BEC GUI client class. Container for GUI applications within Python."""

    _top_level = {}

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._default_dock_name = "bec"
        self._auto_updates_enabled = True
        self._auto_updates = None
        self._killed = False
        self._startup_timeout = 0
        self._gui_started_timer = None
        self._gui_started_event = threading.Event()
        self._process = None
        self._process_output_processing_thread = None
        self._exposed_dock_areas = []
        self._registry_state = {}
        self.available_widgets = AvailableWidgetsNamespace()

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

    @property
    def windows(self) -> dict:
        """Dictionary with dock ares in the GUI."""
        return self._top_level

    @property
    def window_list(self) -> list:
        """List with dock areas in the GUI."""
        return list(self._top_level.values())

    # FIXME AUTO UPDATES
    # @property
    # def auto_updates(self):
    #     if self._auto_updates_enabled:
    #         with wait_for_server(self):
    #             return self._auto_updates

    def _get_update_script(self) -> AutoUpdates | None:
        eps = imd.entry_points(group="bec.widgets.auto_updates")
        for ep in eps:
            if ep.name == "plugin_widgets_update":
                try:
                    spec = importlib.util.find_spec(ep.module)
                    # if the module is not found, we skip it
                    if spec is None:
                        continue
                    return ep.load()(gui=self._top_level["main"])
                except Exception as e:
                    logger.error(f"Error loading auto update script from plugin: {str(e)}")
        return None

    # FIME AUTO UPDATES
    # @property
    # def selected_device(self) -> str | None:
    #     """
    #     Selected device for the plot.
    #     """
    #     auto_update_config_ep = MessageEndpoints.gui_auto_update_config(self._gui_id)
    #     auto_update_config = self._client.connector.get(auto_update_config_ep)
    #     if auto_update_config:
    #         return auto_update_config.selected_device
    #     return None

    # @selected_device.setter
    # def selected_device(self, device: str | DeviceBase):
    #     if isinstance_based_on_class_name(device, "bec_lib.device.DeviceBase"):
    #         self._client.connector.set_and_publish(
    #             MessageEndpoints.gui_auto_update_config(self._gui_id),
    #             messages.GUIAutoUpdateConfigMessage(selected_device=device.name),
    #         )
    #     elif isinstance(device, str):
    #         self._client.connector.set_and_publish(
    #             MessageEndpoints.gui_auto_update_config(self._gui_id),
    #             messages.GUIAutoUpdateConfigMessage(selected_device=device),
    #         )
    #     else:
    #         raise ValueError("Device must be a string or a device object")

    # FIXME AUTO UPDATES
    # def _start_update_script(self) -> None:
    #     self._client.connector.register(MessageEndpoints.scan_status(), cb=self._handle_msg_update)

    # def _handle_msg_update(self, msg: StreamMessage) -> None:
    #     if self.auto_updates is not None:
    #         # pylint: disable=protected-access
    #         return self._update_script_msg_parser(msg.value)

    # def _update_script_msg_parser(self, msg: messages.BECMessage) -> None:
    #     if isinstance(msg, messages.ScanStatusMessage):
    #         if not self._gui_is_alive():
    #             return
    #         if self._auto_updates_enabled:
    #             return self.auto_updates.do_update(msg)

    def _gui_post_startup(self):
        timeout = 10
        while time.time() < time.time() + timeout:
            if len(list(self._registry_state.keys())) == 0:
                time.sleep(0.1)
            else:
                break
        # FIXME AUTO UPDATES
        # if self._auto_updates_enabled:
        #     if self._auto_updates is None:
        #         auto_updates = self._get_update_script()
        #         if auto_updates is None:
        #             AutoUpdates.create_default_dock = True
        #             AutoUpdates.enabled = True
        #             auto_updates = AutoUpdates(self._top_level[name])
        #         if auto_updates.create_default_dock:
        #             auto_updates.start_default_dock()
        #         self._start_update_script()
        #         self._auto_updates = auto_updates
        self._do_show_all()
        self._gui_started_event.set()

    def _start_server(self, wait=False) -> None:
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

    def _start(self):
        self._killed = False
        self._client.connector.register(
            MessageEndpoints.gui_registry_state(self._gui_id), cb=self._handle_registry_update
        )
        return self._start_server()

    def start(self):
        """Start the GUI server."""
        return self._start()

    def _handle_registry_update(self, msg: StreamMessage) -> None:
        self._registry_state = msg["data"].state
        self._update_dynamic_namespace()
        # self._update_dynamic_namespace()
        # FIXME logic to update namespace

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
            # because of the registry callbacks, we may have
            # dock areas that are already killed, but not yet
            # removed from the registry state
            if not self._killed:
                for window in self._top_level.values():
                    window.hide()

    def show(self):
        """Show the GUI window."""
        if self._process is not None:
            return self._show_all()
        # backward compatibility: show() was also starting server
        return self._start_server(wait=True)

    def hide(self):
        """Hide the GUI window."""
        return self._hide_all()

    def new(self, name: str | None = None, wait: bool = True) -> BECDockArea:
        """Create a new top-level dock area.

        Args:
            name(str, optional): The name of the dock area. Defaults to None.
            wait(bool, optional): Whether to wait for the server to start. Defaults to True.
        Returns:
            BECDockArea: The new dock area.
        """
        if wait:
            with wait_for_server(self):
                rpc_client = RPCBase(gui_id=f"{self._gui_id}:window", parent=self)
                widget = rpc_client._run_rpc(
                    "new_dock_area", name
                )  # pylint: disable=protected-access
                return widget
        rpc_client = RPCBase(gui_id=f"{self._gui_id}:window", parent=self)
        widget = rpc_client._run_rpc("new_dock_area", name)  # pylint: disable=protected-access
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
        for widget_name in self.windows.keys():
            self.delete(widget_name)

    def _clear_top_level_widgets(self):
        self._top_level.clear()
        for widget_id in self._exposed_dock_areas:
            delattr(self, widget_id)
        self._exposed_dock_areas.clear()

    def _add_dock_areas_from_registry(self):
        for dock_area_info in self._registry_state.values():
            name = dock_area_info["name"]
            gui_id = dock_area_info["gui_id"]

            dock_area = BECDockArea(gui_id=gui_id, name=name, parent=self)
            self._top_level[name] = dock_area
            self._exposed_dock_areas.append(name)
            setattr(self, name, dock_area)

            dock_info = dock_area_info["config"].get("docks", None)
            if dock_info:
                self._add_docks_from_registry(dock_info, dock_area)

    def _add_docks_from_registry(self, dock_info: dict[str, dict], dock_area: BECDockArea):
        for dock_name, info in dock_info.items():
            dock = client.BECDock(gui_id=info["gui_id"], name=dock_name, parent=dock_area)
            setattr(dock_area, dock_name, dock)
            widget_info = info["widgets"]
            if widget_info:
                self._add_widgets_from_registry(
                    widget_info=widget_info, dock_area=dock_area, dock=dock
                )

    def _add_widgets_from_registry(
        self, widget_info: dict[str, dict], dock_area: client.BECDockArea, dock: client.BECDock
    ):
        for widget_name, info in widget_info.items():
            # FIXME use widget_handler instead
            # widget_class = widget_handler.widget_classes[info["widget_class"]]
            widget_class = getattr(client, info["widget_class"])
            widget = widget_class(gui_id=info["gui_id"], name=widget_name, parent=dock)
            obj = getattr(dock_area, "elements")
            setattr(obj, widget_name, widget)
            setattr(dock, widget_name, widget)

    def _update_dynamic_namespace(self):
        """Update the dynamic name space"""
        self._clear_top_level_widgets()
        self._add_dock_areas_from_registry()

    def close(self):
        """Deprecated. Use kill_server() instead."""
        # FIXME, deprecated in favor of kill, will be removed in the future
        self.kill_server()

    def kill_server(self) -> None:
        """Kill the GUI server."""
        self._top_level.clear()
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
