"""Client utilities for the BEC GUI."""

from __future__ import annotations

import json
import os
import select
import signal
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from threading import Lock
from typing import TYPE_CHECKING, Callable, Literal, TypeAlias, cast

from bec_lib.endpoints import EndpointInfo, MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.utils.import_utils import lazy_import, lazy_import_from
from rich.console import Console
from rich.table import Table

from bec_widgets.cli.rpc.rpc_base import RPCBase, RPCReference
from bec_widgets.utils.serialization import register_serializer_extension

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib.messages import GUIRegistryStateMessage

    import bec_widgets.cli.client as client
else:
    GUIRegistryStateMessage = lazy_import_from("bec_lib.messages", "GUIRegistryStateMessage")
    client = lazy_import("bec_widgets.cli.client")


logger = bec_logger.logger

IGNORE_WIDGETS = ["LaunchWindow"]
PROCESS_TERMINATION_TIMEOUT = 10
PROCESS_OUTPUT_THREAD_JOIN_TIMEOUT = 2
PROCESS_OUTPUT_SELECT_TIMEOUT = 0.2
GRACEFUL_SERVER_SHUTDOWN_RPC_TIMEOUT = 3
GRACEFUL_SERVER_SHUTDOWN_TIMEOUT = 5
OUTPUT_READER_STOP_EVENT_ATTR = "_bec_output_reader_stop_event"

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


def check_gui_display_available() -> tuple[bool, str | None]:
    """
    Check whether the current environment can launch the GUI.

    Returns:
        tuple[bool, str | None]:
            - ``True, None`` when a graphical display is available.
            - ``False, <message>`` when GUI startup should be blocked with a helpful message.
    """
    if os.name != "posix" or sys.platform == "darwin":
        return True, None

    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return True, None

    if (
        os.environ.get("SSH_CONNECTION")
        or os.environ.get("SSH_CLIENT")
        or os.environ.get("SSH_TTY")
    ):
        return (
            False,
            "Cannot start BEC GUI: no graphical display was detected for this SSH session. "
            "If you want to launch widgets remotely, reconnect with X11 forwarding enabled "
            "(for example `ssh -X` or `ssh -Y`) or start the GUI from a local graphical session.",
        )

    return (
        False,
        "Cannot start BEC GUI: no graphical display was detected. "
        "Set `DISPLAY` or `WAYLAND_DISPLAY`, or start the GUI from a graphical session.",
    )


def _get_output(process, logger, stop_event: threading.Event | None = None) -> None:
    log_func = {process.stdout: logger.debug, process.stderr: logger.info}
    stream_buffer = {process.stdout: [], process.stderr: []}
    try:
        os.set_blocking(process.stdout.fileno(), False)
        os.set_blocking(process.stderr.fileno(), False)
        while process.poll() is None and not (stop_event and stop_event.is_set()):
            readylist, _, _ = select.select(
                [process.stdout, process.stderr], [], [], PROCESS_OUTPUT_SELECT_TIMEOUT
            )
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


def _process_group_snapshot(process) -> str:
    try:
        pgid = os.getpgid(process.pid)
    except ProcessLookupError:
        return "Process group snapshot unavailable: process already exited"
    try:
        result = subprocess.run(
            ["ps", "-o", "pid,ppid,pgid,stat,command", "-g", str(pgid)],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception as exc:
        return f"Process group snapshot unavailable: {exc}"
    output = result.stdout.strip()
    if not output:
        return f"Process group snapshot empty for pgid={pgid}"
    return output


def _terminate_plot_process(process, logger, timeout: float = PROCESS_TERMINATION_TIMEOUT) -> None:
    if process.poll() is not None:
        return

    process_info = f"pid={process.pid} command={process.args}"
    try:
        pgid = os.getpgid(process.pid)
        process_info = f"pid={process.pid} pgid={pgid} command={process.args}"
        logger.info(f"Terminating GUI process group {process_info}")
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait(timeout=timeout)
        return
    except Exception as exc:
        logger.warning("Failed to terminate GUI process group; terminating process only.")
        logger.info(f"GUI process termination failure details: {exc}. pid={process.pid}")
        process.terminate()

    try:
        process.wait(timeout=timeout)
        return
    except subprocess.TimeoutExpired:
        logger.warning(f"GUI process did not stop within {timeout}s; killing it.")
        logger.info(
            f"GUI process force-kill details: {process_info}\n"
            f"{_process_group_snapshot(process)}"
        )

    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except ProcessLookupError as e:
        logger.error(f"Failed to kill GUI process group: {e}")
        process.wait(timeout=timeout)
        return
    process.wait(timeout=timeout)


def _wait_for_process_exit(process, timeout: float) -> bool:
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        return False
    return True


def _join_process_output_thread(process, thread: threading.Thread | None, logger) -> None:
    if thread is None:
        return
    thread.join(timeout=PROCESS_OUTPUT_THREAD_JOIN_TIMEOUT)
    if not thread.is_alive():
        return

    if stop_event := getattr(thread, OUTPUT_READER_STOP_EVENT_ATTR, None):
        stop_event.set()

    for stream in (process.stdout, process.stderr):
        if stream is None:
            continue
        try:
            stream.close()
        except OSError as e:
            logger.error(f"Failed to close stream {str(e)}")
    thread.join(timeout=PROCESS_OUTPUT_THREAD_JOIN_TIMEOUT)
    if thread.is_alive():
        logger.warning("GUI process output reader thread did not stop after process shutdown.")
        logger.info(f"GUI process output reader thread details: pid={process.pid}")


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
        process_output_stop_event = threading.Event()
        process_output_processing_thread = threading.Thread(
            target=_get_output, args=(process, logger, process_output_stop_event)
        )
        setattr(
            process_output_processing_thread,
            OUTPUT_READER_STOP_EVENT_ATTR,
            process_output_stop_event,
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
            if client._gui_started_timer is not None:
                # cancel the timer, we are done
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
        register_serializer_extension()
        self._rpc_timeout = 60

    ####################
    #### Client API ####
    ####################

    @property
    def launcher(self) -> RPCBase:
        """The launcher object."""
        return RPCBase(gui_id=f"{self._gui_id}:launcher", parent=self, object_name="launcher")

    def set_rpc_timeout(self, timeout: float):
        """Set the timeout for RPC calls to the GUI server.

        Args:
            timeout(float): The timeout in seconds.
        """
        if not isinstance(timeout, (int, float)) or timeout < 0:
            raise ValueError("Timeout must be a non-negative number.")
        self._rpc_timeout = timeout

    def _safe_register_stream(self, endpoint: EndpointInfo, cb: Callable, **kwargs):
        """Check if already registered for registration in idempotent functions."""
        if not self._client.connector.any_stream_is_registered(endpoint, cb=cb):
            self._client.connector.register(endpoint, cb=cb, **kwargs)

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
        self._safe_register_stream(
            MessageEndpoints.gui_registry_state(self._gui_id),
            cb=self._handle_registry_update,
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
        logger.warning("Using <gui>.start() is deprecated, use <gui>.show() instead.")
        return self._start(wait=wait)

    def show(self, wait=True) -> None:
        """
        Show the GUI window.
        If the GUI server is not running, it will be started.

        Args:
            wait(bool): Whether to wait for the server to start. Defaults to True.
        """
        if self._check_if_server_is_alive():
            return self._show_all()
        return self._start(wait=wait)

    def hide(self):
        """Hide the GUI window."""
        return self._hide_all()

    def raise_window(self, wait: bool = True) -> None:
        """
        Bring GUI windows to the front.
        If the GUI server is not running, it will be started.

        Args:
            wait(bool): Whether to wait for the server to start. Defaults to True.
        """
        if self._check_if_server_is_alive():
            return self._raise_all()
        return self._start(wait=wait)

    def change_theme(self, theme: Literal["light", "dark"] | None = None) -> None:
        """
        Apply a GUI theme or toggle between dark and light.

        Args:
            theme(Literal["light", "dark"] | None): Theme to apply. If None, the current
                theme is fetched from the GUI and toggled.
        """
        if not self._check_if_server_is_alive():
            self._start(wait=True)

        with wait_for_server(self):
            if theme is None:
                current_theme = self.launcher._run_rpc("fetch_theme")
                next_theme = "light" if current_theme == "dark" else "dark"
            else:
                next_theme = theme
            self.launcher._run_rpc("change_theme", theme=next_theme)

    def new(
        self,
        name: str | None = None,
        wait: bool = True,
        geometry: tuple[int, int, int, int] | None = None,
        launch_script: str = "dock_area",
        startup_profile: str | Literal["restore", "skip"] | None = None,
        **kwargs,
    ) -> client.AdvancedDockArea:
        """Create a new top-level dock area.

        Args:
            name(str, optional): The name of the dock area. Defaults to None.
            wait(bool, optional): Whether to wait for the server to start. Defaults to True.
            geometry(tuple[int, int, int, int] | None): The geometry of the dock area (pos_x, pos_y, w, h).
            launch_script(str): The launch script to use. Defaults to "dock_area".
            startup_profile(str | Literal["restore", "skip"] | None): Startup mode for
                the dock area:
                  - None: start in transient empty workspace
                  - "restore": restore last-used profile
                  - "skip": skip profile initialization
                  - "<name>": load the named profile
            **kwargs: Additional keyword arguments passed to the dock area.

        Returns:
            client.AdvancedDockArea: The new dock area.

        Examples:
            >>> gui.new()  # Start with an empty unsaved workspace
            >>> gui.new(startup_profile="restore")  # Restore last profile
            >>> gui.new(startup_profile="my_profile")  # Load explicit profile
        """
        if "profile" in kwargs or "start_empty" in kwargs:
            raise TypeError(
                "gui.new() no longer accepts 'profile' or 'start_empty'. Use 'startup_profile' instead."
            )

        if not self._check_if_server_is_alive():
            self.show(wait=True)
        if wait:
            with wait_for_server(self):
                return self._new_impl(
                    name=name,
                    geometry=geometry,
                    launch_script=launch_script,
                    startup_profile=startup_profile,
                    **kwargs,
                )
        return self._new_impl(
            name=name,
            geometry=geometry,
            launch_script=launch_script,
            startup_profile=startup_profile,
            **kwargs,
        )

    def _new_impl(
        self,
        *,
        name: str | None,
        geometry: tuple[int, int, int, int] | None,
        launch_script: str,
        startup_profile: str | Literal["restore", "skip"] | None,
        **kwargs,
    ):
        if launch_script == "dock_area":
            try:
                return self.launcher._run_rpc(
                    "system.launch_dock_area",
                    name=name,
                    geometry=geometry,
                    startup_profile=startup_profile,
                    **kwargs,
                )
            except ValueError as exc:
                error = str(exc)
                if (
                    "Unknown system RPC method: system.launch_dock_area" not in error
                    and "has no attribute 'system.launch_dock_area'" not in error
                ):
                    raise
                logger.debug("Server does not support system.launch_dock_area; using launcher RPC")

        return self.launcher._run_rpc(
            "launch",
            launch_script=launch_script,
            name=name,
            geometry=geometry,
            startup_profile=startup_profile,
            **kwargs,
        )  # pylint: disable=protected-access

    def delete(self, name: str) -> None:
        """Delete a dock area and its parent window.

        Args:
            name(str): The name of the dock area.
        """
        widget = self.windows.get(name)
        if widget is None:
            raise ValueError(f"Dock area {name} not found.")

        # Get the container_proxy (parent window) gui_id from the server registry
        obj = self._server_registry.get(widget._gui_id)
        if obj is None:
            raise ValueError(f"Widget {name} not found in registry.")

        container_gui_id = obj.get("container_proxy")
        if container_gui_id:
            # Close the container window which will also clean up the dock area
            widget._run_rpc("close", gui_id=container_gui_id)  # pylint: disable=protected-access
        else:
            # Fallback: just close the dock area directly
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
            if not self._request_server_shutdown():
                _terminate_plot_process(self._process, logger)
            _join_process_output_thread(
                self._process, self._process_output_processing_thread, logger
            )
            self._process = None
            self._process_output_processing_thread = None

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

    def _request_server_shutdown(self) -> bool:
        if self._process is None or self._process.poll() is not None:
            return True
        process_details = f"pid={self._process.pid} command={self._process.args}"
        logger.info(f"Requesting graceful GUI shutdown {process_details}")
        try:
            self.launcher._run_rpc(  # pylint: disable=protected-access
                "system.shutdown",
                wait_for_rpc_response=True,
                timeout=GRACEFUL_SERVER_SHUTDOWN_RPC_TIMEOUT,
            )
        except Exception as exc:
            logger.warning(
                "Could not confirm graceful GUI shutdown via RPC; "
                "falling back to process termination."
            )
            logger.info(f"Graceful GUI shutdown RPC failure details: {exc}. {process_details}")
            return False
        if _wait_for_process_exit(self._process, GRACEFUL_SERVER_SHUTDOWN_TIMEOUT):
            logger.info(f"GUI server exited after graceful shutdown {process_details}")
            return True
        logger.warning(
            "GUI server did not exit after graceful shutdown request; "
            "falling back to process termination."
        )
        logger.info(
            f"Graceful GUI shutdown timeout details: {process_details}\n"
            f"{_process_group_snapshot(self._process)}"
        )
        return False

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
        start = time.monotonic()
        while time.monotonic() < start + timeout:
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
        if self._gui_is_alive():
            self._gui_started_event.set()
            return
        gui_available, error_message = check_gui_display_available()
        if not gui_available:
            logger.error(error_message)
            self._startup_timeout = 0
            return
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
        self._safe_register_stream(
            MessageEndpoints.gui_registry_state(self._gui_id), cb=self._handle_registry_update
        )
        return self._start_server(wait=wait)

    def _handle_registry_update(self, msg: dict[str, GUIRegistryStateMessage]) -> None:
        # This was causing a deadlock during shutdown, not sure why.
        # with self._lock:
        self._server_registry = cast(dict[str, RegistryState], msg["data"].state)
        self._update_dynamic_namespace(self._server_registry)

    def _do_show_all(self):
        if self.launcher and len(self._top_level) == 0:
            self.launcher._run_rpc("show")  # pylint: disable=protected-access
        for window in self._top_level.values():
            window.raise_window()

    def _show_all(self):
        with wait_for_server(self):
            return self._do_show_all()

    def _hide_all(self):
        with wait_for_server(self):
            if self._killed:
                return
            self.launcher._run_rpc("hide")
            for window in self._top_level.values():
                window.hide()

    def _do_raise_all(self):
        """Bring GUI windows to the front."""
        if self.launcher and len(self._top_level) == 0:
            self.launcher._run_rpc("raise")  # pylint: disable=protected-access
        for window in self._top_level.values():
            window.raise_window()

    def _raise_all(self):
        with wait_for_server(self):
            if self._killed:
                return
            return self._do_raise_all()

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

        gui.show(wait=True)
        gui.new().new(widget="Waveform")
        time.sleep(10)
    finally:
        gui.kill_server()
