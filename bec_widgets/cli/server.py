from __future__ import annotations

import functools
import json
import signal
import sys
import types
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from typing import Union

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.service_config import ServiceConfig
from bec_lib.utils.import_utils import lazy_import
from qtpy.QtCore import Qt, QTimer
from redis.exceptions import RedisError

from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.qt_utils.error_popups import ErrorPopupUtility
from bec_widgets.utils import BECDispatcher
from bec_widgets.utils.bec_connector import BECConnector
from bec_widgets.widgets.containers.dock import BECDockArea
from bec_widgets.widgets.containers.figure import BECFigure
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow

messages = lazy_import("bec_lib.messages")
logger = bec_logger.logger


@contextmanager
def rpc_exception_hook(err_func):
    """This context replaces the popup message box for error display with a specific hook"""
    # get error popup utility singleton
    popup = ErrorPopupUtility()
    # save current setting
    old_exception_hook = popup.custom_exception_hook

    # install err_func, if it is a callable
    # IMPORTANT, Keep self here, because this method is overwriting the custom_exception_hook
    # of the ErrorPopupUtility (popup instance) class.
    def custom_exception_hook(self, exc_type, value, tb, **kwargs):
        err_func({"error": popup.get_error_message(exc_type, value, tb)})

    popup.custom_exception_hook = types.MethodType(custom_exception_hook, popup)

    try:
        yield popup
    finally:
        # restore state of error popup utility singleton
        popup.custom_exception_hook = old_exception_hook


class BECWidgetsCLIServer:

    def __init__(
        self,
        gui_id: str,
        dispatcher: BECDispatcher = None,
        client=None,
        config=None,
        gui_class: Union[BECFigure, BECDockArea] = BECDockArea,
        gui_class_id: str = "bec",
    ) -> None:
        self.status = messages.BECStatus.BUSY
        self.dispatcher = BECDispatcher(config=config) if dispatcher is None else dispatcher
        self.client = self.dispatcher.client if client is None else client
        self.client.start()
        self.gui_id = gui_id
        # register broadcast callback
        self.rpc_register = RPCRegister()
        self.rpc_register.add_callback(self.broadcast_registry_update)

        self.dispatcher.connect_slot(
            self.on_rpc_update, MessageEndpoints.gui_instructions(self.gui_id)
        )

        # Setup QTimer for heartbeat
        self._heartbeat_timer = QTimer()
        self._heartbeat_timer.timeout.connect(self.emit_heartbeat)
        self._heartbeat_timer.start(200)

        self.status = messages.BECStatus.RUNNING
        with RPCRegister.delayed_broadcast():
            self.gui = gui_class(parent=None, name=gui_class_id, gui_id=gui_class_id)
        logger.success(f"Server started with gui_id: {self.gui_id}")
        # Create initial object -> BECFigure or BECDockArea

    def on_rpc_update(self, msg: dict, metadata: dict):
        request_id = metadata.get("request_id")
        logger.debug(f"Received RPC instruction: {msg}, metadata: {metadata}")
        with rpc_exception_hook(functools.partial(self.send_response, request_id, False)):
            try:
                obj = self.get_object_from_config(msg["parameter"])
                method = msg["action"]
                args = msg["parameter"].get("args", [])
                kwargs = msg["parameter"].get("kwargs", {})
                res = self.run_rpc(obj, method, args, kwargs)
            except Exception as e:
                logger.error(f"Error while executing RPC instruction: {e}")
                self.send_response(request_id, False, {"error": str(e)})
            else:
                logger.debug(f"RPC instruction executed successfully: {res}")
                self.send_response(request_id, True, {"result": res})

    def send_response(self, request_id: str, accepted: bool, msg: dict):
        self.client.connector.set_and_publish(
            MessageEndpoints.gui_instruction_response(request_id),
            messages.RequestResponseMessage(accepted=accepted, message=msg),
            expire=60,
        )

    def get_object_from_config(self, config: dict):
        gui_id = config.get("gui_id")
        obj = self.rpc_register.get_rpc_by_id(gui_id)
        if obj is None:
            raise ValueError(f"Object with gui_id {gui_id} not found")
        return obj

    def run_rpc(self, obj, method, args, kwargs):
        # Run with rpc registry broadcast, but only once
        with RPCRegister.delayed_broadcast():
            logger.debug(f"Running RPC instruction: {method} with args: {args}, kwargs: {kwargs}")
            method_obj = getattr(obj, method)
            # check if the method accepts args and kwargs
            if not callable(method_obj):
                if not args:
                    res = method_obj
                else:
                    setattr(obj, method, args[0])
                    res = None
            else:
                res = method_obj(*args, **kwargs)

            if isinstance(res, list):
                res = [self.serialize_object(obj) for obj in res]
            elif isinstance(res, dict):
                res = {key: self.serialize_object(val) for key, val in res.items()}
            else:
                res = self.serialize_object(res)
            return res

    def serialize_object(self, obj):
        if isinstance(obj, BECConnector):
            config = obj.config.model_dump()
            config["parent_id"] = obj.parent_id  # add parent_id to config
            return {
                "gui_id": obj.gui_id,
                "name": (
                    obj._name if hasattr(obj, "_name") else obj.__class__.__name__
                ),  # pylint: disable=protected-access
                "widget_class": obj.__class__.__name__,
                "config": config,
                "__rpc__": True,
            }
        return obj

    def emit_heartbeat(self):
        logger.trace(f"Emitting heartbeat for {self.gui_id}")
        try:
            self.client.connector.set(
                MessageEndpoints.gui_heartbeat(self.gui_id),
                messages.StatusMessage(name=self.gui_id, status=self.status, info={}),
                expire=10,
            )
        except RedisError as exc:
            logger.error(f"Error while emitting heartbeat: {exc}")

    def broadcast_registry_update(self, connections: dict):
        """
        Broadcast the updated registry to all clients.
        """

        # We only need to broadcast the dock areas
        data = {key: self.serialize_object(val) for key, val in connections.items()}
        self.client.connector.xadd(
            MessageEndpoints.gui_registry_state(self.gui_id),
            msg_dict={"data": messages.GUIRegistryStateMessage(state=data)},
            max_size=1,  # only single message in stream
        )

    def shutdown(self):  # TODO not sure if needed when cleanup is done at level of BECConnector
        self.status = messages.BECStatus.IDLE
        self._heartbeat_timer.stop()
        self.emit_heartbeat()
        logger.info("Succeded in shutting down gui")
        self.client.shutdown()


class SimpleFileLikeFromLogOutputFunc:
    def __init__(self, log_func):
        self._log_func = log_func
        self._buffer = []

    def write(self, buffer):
        self._buffer.append(buffer)

    def flush(self):
        lines, _, remaining = "".join(self._buffer).rpartition("\n")
        if lines:
            self._log_func(lines)
        self._buffer = [remaining]

    def close(self):
        return


def _start_server(
    gui_id: str,
    gui_class: Union[BECFigure, BECDockArea],
    gui_class_id: str = "bec",
    config: str | None = None,
):
    if config:
        try:
            config = json.loads(config)
            service_config = ServiceConfig(config=config)
        except (json.JSONDecodeError, TypeError):
            service_config = ServiceConfig(config_path=config)
    else:
        # if no config is provided, use the default config
        service_config = ServiceConfig()

    # bec_logger.configure(
    #     service_config.redis,
    #     QtRedisConnector,
    #     service_name="BECWidgetsCLIServer",
    #     service_config=service_config.service_config,
    # )
    server = BECWidgetsCLIServer(
        gui_id=gui_id, config=service_config, gui_class=gui_class, gui_class_id=gui_class_id
    )
    return server


def main():
    import argparse
    import os

    from qtpy.QtCore import QSize
    from qtpy.QtGui import QIcon
    from qtpy.QtWidgets import QApplication

    import bec_widgets

    parser = argparse.ArgumentParser(description="BEC Widgets CLI Server")
    parser.add_argument("--id", type=str, default="test", help="The id of the server")
    parser.add_argument(
        "--gui_class",
        type=str,
        help="Name of the gui class to be rendered. Possible values: \n- BECFigure\n- BECDockArea",
    )
    parser.add_argument(
        "--gui_class_id",
        type=str,
        default="bec",
        help="The id of the gui class that is added to the QApplication",
    )
    parser.add_argument("--config", type=str, help="Config file or config string.")
    parser.add_argument("--hide", action="store_true", help="Hide on startup")

    args = parser.parse_args()

    bec_logger.level = bec_logger.LOGLEVEL.INFO
    if args.hide:
        # pylint: disable=protected-access
        bec_logger._stderr_log_level = bec_logger.LOGLEVEL.ERROR
        bec_logger._update_sinks()

    if args.gui_class == "BECDockArea":
        gui_class = BECDockArea
    elif args.gui_class == "BECFigure":
        gui_class = BECFigure
    else:
        print(
            "Please specify a valid gui_class to run. Use -h for help."
            "\n Starting with default gui_class BECFigure."
        )
        gui_class = BECDockArea

    with redirect_stdout(SimpleFileLikeFromLogOutputFunc(logger.info)):
        with redirect_stderr(SimpleFileLikeFromLogOutputFunc(logger.error)):
            app = QApplication(sys.argv)
            # set close on last window, only if not under control of client ;
            # indeed, Qt considers a hidden window a closed window, so if all windows
            # are hidden by default it exits
            app.setQuitOnLastWindowClosed(not args.hide)
            module_path = os.path.dirname(bec_widgets.__file__)
            icon = QIcon()
            icon.addFile(
                os.path.join(module_path, "assets", "app_icons", "bec_widgets_icon.png"),
                size=QSize(48, 48),
            )
            app.setWindowIcon(icon)
            # store gui id within QApplication object, to make it available to all widgets
            app.gui_id = args.id

            # args.id = "abff6"
            server = _start_server(args.id, gui_class, args.gui_class_id, args.config)

            win = BECMainWindow(gui_id=f"{server.gui_id}:window")
            win.setAttribute(Qt.WA_ShowWithoutActivating)
            win.setWindowTitle("BEC")

            RPCRegister().add_rpc(win)
            gui = server.gui
            win.setCentralWidget(gui)
            if not args.hide:
                win.show()

            app.aboutToQuit.connect(server.shutdown)

            def sigint_handler(*args):
                # display message, for people to let it terminate gracefully
                print("Caught SIGINT, exiting")
                # Widgets should be all closed.
                with RPCRegister.delayed_broadcast():
                    for widget in QApplication.instance().topLevelWidgets():
                        widget.close()
                app.quit()

            # gui.bec.close()
            # win.shutdown()
            signal.signal(signal.SIGINT, sigint_handler)
            signal.signal(signal.SIGTERM, sigint_handler)

            sys.exit(app.exec())


if __name__ == "__main__":
    main()
