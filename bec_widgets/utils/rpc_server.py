from __future__ import annotations

import functools
import traceback
import types
from contextlib import contextmanager
from typing import TYPE_CHECKING, Callable, Literal, TypeVar

from bec_lib.client import BECClient
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.utils.import_utils import lazy_import
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import QWidget
from redis.exceptions import RedisError

from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils import BECDispatcher
from bec_widgets.utils.bec_connector import BECConnector
from bec_widgets.utils.container_utils import WidgetContainerUtils
from bec_widgets.utils.error_popups import ErrorPopupUtility
from bec_widgets.utils.screen_utils import apply_window_geometry
from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow, BECMainWindowNoRPC

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib import messages
    from qtpy.QtCore import QObject
else:
    messages = lazy_import("bec_lib.messages")
logger = bec_logger.logger


T = TypeVar("T")


class RegistryNotReadyError(Exception):
    """Raised when trying to access an object from the RPC registry that is not yet registered."""


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


class SingleshotRPCRepeat:

    def __init__(self, max_delay: int = 2000):
        self.max_delay = max_delay
        self.accumulated_delay = 0

    def __iadd__(self, delay: int):
        self.accumulated_delay += delay
        if self.accumulated_delay > self.max_delay:
            raise RegistryNotReadyError("Max delay exceeded for RPC singleshot repeat")
        return self


class RPCServer:

    client: BECClient

    def __init__(
        self,
        gui_id: str,
        dispatcher: BECDispatcher | None = None,
        client: BECClient | None = None,
        config=None,
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
        self._registry_update_callbacks = []
        self._broadcasted_data = {}
        self._rpc_singleshot_repeats: dict[str, SingleshotRPCRepeat] = {}

        self.status = messages.BECStatus.RUNNING
        logger.success(f"Server started with gui_id: {self.gui_id}")

    def on_rpc_update(self, msg: dict, metadata: dict):
        request_id = metadata.get("request_id")
        if request_id is None:
            logger.error("Received RPC instruction without request_id")
            return
        logger.debug(f"Received RPC instruction: {msg}, metadata: {metadata}")
        with rpc_exception_hook(functools.partial(self.send_response, request_id, False)):
            try:
                method = msg["action"]
                args = msg["parameter"].get("args", [])
                kwargs = msg["parameter"].get("kwargs", {})
                if method.startswith("system."):
                    res = self.run_system_rpc(method, args, kwargs)
                else:
                    obj = self.get_object_from_config(msg["parameter"])
                    res = self.run_rpc(obj, method, args, kwargs)
            except Exception:
                content = traceback.format_exc()
                logger.error(f"Error while executing RPC instruction: {content}")
                self.send_response(request_id, False, {"error": content})
            else:
                logger.debug(f"RPC instruction executed successfully: {res}")
                self._rpc_singleshot_repeats[request_id] = SingleshotRPCRepeat()
                QTimer.singleShot(0, lambda: self.serialize_result_and_send(request_id, res))

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
            if method == "raise" and hasattr(
                obj, "setWindowState"
            ):  # special case for raising windows, should work even if minimized
                # this is a special case for raising windows for gnome on rethat 9 systems where changing focus is supressed by default
                # The procedure is as follows:
                # 1. Get the current window state to check if the window is minimized and remove minimized flag
                # 2. Then in order to force gnome to raise the window, we set the window to stay on top temporarily
                #    and call raise_() and activateWindow()
                #    This forces gnome to raise the window even if focus stealing is prevented
                # 3. Flag for stay on top is removed again to restore the original window state
                # 4. Finally, we call show() to ensure the window is visible

                state = getattr(obj, "windowState", lambda: Qt.WindowNoState)()
                target_state = state | Qt.WindowActive
                if state & Qt.WindowMinimized:
                    target_state &= ~Qt.WindowMinimized
                obj.setWindowState(target_state)
                if hasattr(obj, "showNormal") and state & Qt.WindowMinimized:
                    obj.showNormal()
                if hasattr(obj, "raise_"):
                    obj.setWindowFlags(obj.windowFlags() | Qt.WindowStaysOnTopHint)
                    obj.raise_()
                if hasattr(obj, "activateWindow"):
                    obj.activateWindow()
                obj.setWindowFlags(obj.windowFlags() & ~Qt.WindowStaysOnTopHint)
                obj.show()
                res = None
            else:
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
        return res

    def run_system_rpc(self, method: str, args: list, kwargs: dict):
        if method == "system.launch_dock_area":
            return self._launch_dock_area(*args, **kwargs)
        if method == "system.list_capabilities":
            return {"system.launch_dock_area": True}
        raise ValueError(f"Unknown system RPC method: {method}")

    @staticmethod
    def _launch_dock_area(
        name: str | None = None,
        geometry: tuple[int, int, int, int] | None = None,
        startup_profile: str | Literal["restore", "skip"] | None = None,
    ) -> QWidget | None:
        from bec_widgets.applications import bw_launch

        with RPCRegister.delayed_broadcast() as rpc_register:
            existing_dock_areas = rpc_register.get_names_of_rpc_by_class_type(BECDockArea)
            if name is not None:
                WidgetContainerUtils.raise_for_invalid_name(name)
                if name in existing_dock_areas:
                    name = WidgetContainerUtils.generate_unique_name(name, existing_dock_areas)
            else:
                name = WidgetContainerUtils.generate_unique_name("dock_area", existing_dock_areas)

            result_widget = bw_launch.dock_area(object_name=name, startup_profile=startup_profile)
            result_widget.window().setWindowTitle(f"BEC - {name}")

            if isinstance(result_widget, BECMainWindow):
                apply_window_geometry(result_widget, geometry)
                result_widget.show()
            else:
                window = BECMainWindowNoRPC()
                window.setCentralWidget(result_widget)
                window.setWindowTitle(f"BEC - {result_widget.objectName()}")
                apply_window_geometry(window, geometry)
                window.show()
            return result_widget

    def serialize_result_and_send(self, request_id: str, res: object):
        """
        Serialize the result of an RPC call and send it back to the client.

        Note: If the object is not yet registered in the RPC registry, this method
        will retry serialization after a short delay, up to a maximum delay. In order
        to avoid processEvents calls in the middle of serialization, QTimer.singleShot is used.
        This allows the target event to 'float' to the next event loop iteration until the
        object is registered.
        The 'jump' to the next event loop is indicated by raising a RegistryNotReadyError, see
        _serialize_bec_connector.

        Args:
            request_id (str): The ID of the request.
            res (object): The result of the RPC call.
        """
        retry_delay = 100
        try:
            if isinstance(res, list):
                res = [self.serialize_object(obj) for obj in res]
            elif isinstance(res, dict):
                res = {key: self.serialize_object(val) for key, val in res.items()}
            else:
                res = self.serialize_object(res)
        except RegistryNotReadyError:
            try:
                self._rpc_singleshot_repeats[request_id] += retry_delay
                QTimer.singleShot(
                    retry_delay, lambda: self.serialize_result_and_send(request_id, res)
                )
            except RegistryNotReadyError:
                logger.error(
                    f"Max delay exceeded for RPC request {request_id}, sending error response"
                )
                self.send_response(
                    request_id,
                    False,
                    {
                        "error": f"Max delay exceeded for RPC request {request_id}, object not registered in time."
                    },
                )
                self._rpc_singleshot_repeats.pop(request_id, None)
            return
        except Exception as exc:
            logger.error(f"Error while serializing RPC result: {exc}")
            self.send_response(
                request_id,
                False,
                {"error": f"Error while serializing RPC result: {exc}\n{traceback.format_exc()}"},
            )
        else:
            self.send_response(request_id, True, {"result": res})
        self._rpc_singleshot_repeats.pop(request_id, None)

    def serialize_object(self, obj: T) -> None | dict | T:
        """
        Serialize all BECConnector objects.

        Args:
            obj: The object to be serialized.

        Returns:
            None | dict | T: The serialized object or None if the object is not a BECConnector.
        """
        if not isinstance(obj, BECConnector):
            return obj
        # Respect RPC = False
        if getattr(obj, "RPC", True) is False:
            return None
        # Respect rpc_exposed = False
        if getattr(obj, "rpc_exposed", True) is False:
            return None
        return self._serialize_bec_connector(obj, wait=True)

    def emit_heartbeat(self) -> None:
        """
        Emit a heartbeat message to the GUI server.
        This method is called periodically to indicate that the server is still running.
        """
        logger.trace(f"Emitting heartbeat for {self.gui_id}")
        try:
            self.client.connector.set(
                MessageEndpoints.gui_heartbeat(self.gui_id),
                messages.StatusMessage(name=self.gui_id, status=self.status, info={}),
                expire=10,
            )
        except RedisError as exc:
            logger.error(f"Error while emitting heartbeat: {exc}")

    def broadcast_registry_update(self, connections: dict) -> None:
        """
        Broadcast the registry update to all the callbacks.
        This method is called whenever the registry is updated.
        """
        data = {}
        for key, val in connections.items():
            if not isinstance(val, BECConnector):
                continue
            if not getattr(val, "RPC", True):
                continue
            if not getattr(val, "rpc_exposed", True):
                continue
            data[key] = self._serialize_bec_connector(val)
        if self._broadcasted_data == data:
            return
        self._broadcasted_data = data

        logger.debug(f"Broadcasting registry update: {data} for {self.gui_id}")
        self.client.connector.xadd(
            MessageEndpoints.gui_registry_state(self.gui_id),
            msg_dict={"data": messages.GUIRegistryStateMessage(state=data)},
            max_size=1,
            expire=60,
        )

    def _serialize_bec_connector(self, connector: BECConnector, wait=False) -> dict:
        """
        Create the serialization dict for a single BECConnector.

        Args:
            connector (BECConnector): The BECConnector to serialize.
            wait (bool): If True, wait until the object is registered in the RPC register.

        Returns:
            dict: The serialized BECConnector object.
        """

        config_dict = connector.config.model_dump()
        config_dict["parent_id"] = getattr(connector, "parent_id", None)

        try:
            parent = connector.parent()
            if isinstance(parent, BECMainWindow):
                container_proxy = parent.gui_id
            else:
                container_proxy = None
        except Exception:
            container_proxy = None

        if wait and not self.rpc_register.object_is_registered(connector):
            raise RegistryNotReadyError(f"Connector {connector} not registered yet")

        widget_class = getattr(connector, "rpc_widget_class", None)
        if not widget_class:
            widget_class = connector.__class__.__name__

        return {
            "gui_id": connector.gui_id,
            "object_name": connector.object_name or connector.__class__.__name__,
            "widget_class": widget_class,
            "config": config_dict,
            "container_proxy": container_proxy,
            "__rpc__": getattr(connector, "rpc_exposed", True),
        }

    # Suppose clients register callbacks to receive updates
    def add_registry_update_callback(self, cb: Callable) -> None:
        """
        Add a callback to be called whenever the registry is updated.
        The specified callback is called whenever the registry is updated.

        Args:
            cb (Callable): The callback to be added. It should accept a dictionary of all the
            registered RPC objects as an argument.
        """
        self._registry_update_callbacks.append(cb)

    def shutdown(self):  # TODO not sure if needed when cleanup is done at level of BECConnector
        self.status = messages.BECStatus.IDLE
        self._heartbeat_timer.stop()
        self.emit_heartbeat()
        logger.info("Succeded in shutting down CLI server")
        self.client.shutdown()
