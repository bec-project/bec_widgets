from __future__ import annotations

import importlib
import importlib.metadata as imd
import json
import os
import select
import subprocess
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.utils.import_utils import isinstance_based_on_class_name, lazy_import, lazy_import_from

import bec_widgets.cli.client as client
from bec_widgets.cli.auto_updates import AutoUpdates
from bec_widgets.cli.rpc.rpc_base import RPCBase

if TYPE_CHECKING:
    from bec_lib import messages
    from bec_lib.connector import MessageObject
    from bec_lib.device import DeviceBase

    from bec_widgets.utils.bec_dispatcher import BECDispatcher
else:
    messages = lazy_import("bec_lib.messages")
    # from bec_lib.connector import MessageObject
    MessageObject = lazy_import_from("bec_lib.connector", ("MessageObject",))
    BECDispatcher = lazy_import_from("bec_widgets.utils.bec_dispatcher", ("BECDispatcher",))

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


def _start_plot_process(gui_id: str, gui_class: type, config: dict | str, logger=None) -> None:
    """
    Start the plot in a new process.

    Logger must be a logger object with "debug" and "error" functions,
    or it can be left to "None" as default. None means output from the
    process will not be captured.
    """
    # pylint: disable=subprocess-run-check
    command = ["bec-gui-server", "--id", gui_id, "--gui_class", gui_class.__name__, "--hide"]
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
    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)


@contextmanager
def wait_for_server(client):
    timeout = client._startup_timeout
    if not timeout:
        if client.gui_is_alive():
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


### ----------------------------
### NOTE
### it is far easier to extend the 'delete' method on the client side,
### to know when the client is deleted, rather than listening to server
### to get notified. However, 'generate_cli.py' cannot add extra stuff
### in the generated client module. So, here a class with the same name
### is created, and client module is patched.
class BECDockArea(client.BECDockArea):
    def delete(self):
        if self is BECGuiClient._top_level["main"].widget:
            raise RuntimeError("Cannot delete main window")
        super().delete()
        try:
            del BECGuiClient._top_level[self._gui_id]
        except KeyError:
            # if a dock area is not at top level
            pass


client.BECDockArea = BECDockArea
### ----------------------------


@dataclass
class WidgetDesc:
    title: str
    widget: BECDockArea


class BECGuiClient(RPCBase):
    _top_level = {}

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._auto_updates_enabled = True
        self._auto_updates = None
        self._startup_timeout = 0
        self._gui_started_timer = None
        self._gui_started_event = threading.Event()
        self._process = None
        self._process_output_processing_thread = None

    @property
    def windows(self):
        return self._top_level

    @property
    def auto_updates(self):
        if self._auto_updates_enabled:
            with wait_for_server(self):
                return self._auto_updates

    def _get_update_script(self) -> AutoUpdates | None:
        eps = imd.entry_points(group="bec.widgets.auto_updates")
        for ep in eps:
            if ep.name == "plugin_widgets_update":
                try:
                    spec = importlib.util.find_spec(ep.module)
                    # if the module is not found, we skip it
                    if spec is None:
                        continue
                    return ep.load()(gui=self._top_level["main"].widget)
                except Exception as e:
                    logger.error(f"Error loading auto update script from plugin: {str(e)}")
        return None

    @property
    def selected_device(self):
        """
        Selected device for the plot.
        """
        auto_update_config_ep = MessageEndpoints.gui_auto_update_config(self._gui_id)
        auto_update_config = self._client.connector.get(auto_update_config_ep)
        if auto_update_config:
            return auto_update_config.selected_device
        return None

    @selected_device.setter
    def selected_device(self, device: str | DeviceBase):
        if isinstance_based_on_class_name(device, "bec_lib.device.DeviceBase"):
            self._client.connector.set_and_publish(
                MessageEndpoints.gui_auto_update_config(self._gui_id),
                messages.GUIAutoUpdateConfigMessage(selected_device=device.name),
            )
        elif isinstance(device, str):
            self._client.connector.set_and_publish(
                MessageEndpoints.gui_auto_update_config(self._gui_id),
                messages.GUIAutoUpdateConfigMessage(selected_device=device),
            )
        else:
            raise ValueError("Device must be a string or a device object")

    def _start_update_script(self) -> None:
        self._client.connector.register(MessageEndpoints.scan_status(), cb=self._handle_msg_update)

    def _handle_msg_update(self, msg: MessageObject) -> None:
        if self.auto_updates is not None:
            # pylint: disable=protected-access
            return self._update_script_msg_parser(msg.value)

    def _update_script_msg_parser(self, msg: messages.BECMessage) -> None:
        if isinstance(msg, messages.ScanStatusMessage):
            if not self.gui_is_alive():
                return
            if self._auto_updates_enabled:
                return self.auto_updates.do_update(msg)

    def _gui_post_startup(self):
        self._top_level["main"] = WidgetDesc(
            title="BEC Widgets", widget=BECDockArea(gui_id=self._gui_id)
        )
        if self._auto_updates_enabled:
            if self._auto_updates is None:
                auto_updates = self._get_update_script()
                if auto_updates is None:
                    AutoUpdates.create_default_dock = True
                    AutoUpdates.enabled = True
                    auto_updates = AutoUpdates(self._top_level["main"].widget)
                if auto_updates.create_default_dock:
                    auto_updates.start_default_dock()
                self._start_update_script()
                self._auto_updates = auto_updates
        self._do_show_all()
        self._gui_started_event.set()

    def start_server(self, wait=False) -> None:
        """
        Start the GUI server, and execute callback when it is launched
        """
        if self._process is None or self._process.poll() is not None:
            logger.success("GUI starting...")
            self._startup_timeout = 5
            self._gui_started_event.clear()
            self._process, self._process_output_processing_thread = _start_plot_process(
                self._gui_id, self.__class__, self._client._service_config.config, logger=logger
            )

            def gui_started_callback(callback):
                try:
                    if callable(callback):
                        callback()
                finally:
                    threading.current_thread().cancel()

            self._gui_started_timer = RepeatTimer(
                0.5, lambda: self.gui_is_alive() and gui_started_callback(self._gui_post_startup)
            )
            self._gui_started_timer.start()

        if wait:
            self._gui_started_event.wait()

    def _dump(self):
        rpc_client = RPCBase(gui_id=f"{self._gui_id}:window", parent=self)
        return rpc_client._run_rpc("_dump")

    def start(self):
        return self.start_server()

    def _do_show_all(self):
        rpc_client = RPCBase(gui_id=f"{self._gui_id}:window", parent=self)
        rpc_client._run_rpc("show")
        for window in self._top_level.values():
            window.widget.show()

    def show_all(self):
        with wait_for_server(self):
            return self._do_show_all()

    def hide_all(self):
        with wait_for_server(self):
            rpc_client = RPCBase(gui_id=f"{self._gui_id}:window", parent=self)
            rpc_client._run_rpc("hide")
            for window in self._top_level.values():
                window.widget.hide()

    def show(self):
        if self._process is not None:
            return self.show_all()
        # backward compatibility: show() was also starting server
        return self.start_server(wait=True)

    def hide(self):
        return self.hide_all()

    @property
    def main(self):
        """Return client to main dock area (in main window)"""
        with wait_for_server(self):
            return self._top_level["main"].widget

    def new(self, title):
        """Ask main window to create a new top-level dock area"""
        with wait_for_server(self):
            rpc_client = RPCBase(gui_id=f"{self._gui_id}:window", parent=self)
            widget = rpc_client._run_rpc("new_dock_area", title)
            self._top_level[widget._gui_id] = WidgetDesc(title=title, widget=widget)
            return widget

    def close(self) -> None:
        """
        Close the gui window.
        """
        self._top_level.clear()

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
