from __future__ import annotations

import functools
import traceback
import types
from contextlib import contextmanager
from typing import TYPE_CHECKING

from bec_lib.client import BECClient
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.utils.import_utils import lazy_import
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QApplication
from redis.exceptions import RedisError

from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils import BECDispatcher
from bec_widgets.utils.bec_connector import BECConnector
from bec_widgets.utils.error_popups import ErrorPopupUtility
from bec_widgets.utils.widget_io import WidgetHierarchy
from bec_widgets.widgets.plots.plot_base import PlotBase

if TYPE_CHECKING:
    from bec_lib import messages
else:
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


class CLIServer:

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
                obj = self.get_object_from_config(msg["parameter"])
                method = msg["action"]
                args = msg["parameter"].get("args", [])
                kwargs = msg["parameter"].get("kwargs", {})
                res = self.run_rpc(obj, method, args, kwargs)
            except Exception as e:
                content = traceback.format_exc()
                logger.error(f"Error while executing RPC instruction: {content}")
                self.send_response(request_id, False, {"error": content})
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
            # Respect RPC = False
            if hasattr(obj, "RPC") and obj.RPC is False:
                return None
            return self._serialize_bec_connector(obj)
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

    # FIXME signature should be changed on all levels, connection dict is no longer needed
    def broadcast_registry_update(self, _):
        # 1) Gather ALL BECConnector-based widgets
        all_qwidgets = QApplication.allWidgets()
        bec_widgets = set(w for w in all_qwidgets if isinstance(w, BECConnector))
        bec_widgets = {
            c for c in bec_widgets if not (hasattr(c, "RPC") and c.RPC is False)
        }  # FIXME not needed

        # 2) Also gather BECConnector-based data items from PlotBase
        # TODO do we need to access plot data items in cli in namespace?
        for w in all_qwidgets:
            if isinstance(w, PlotBase) and hasattr(w, "plot_item"):
                if hasattr(w.plot_item, "listDataItems"):
                    for data_item in w.plot_item.listDataItems():
                        if isinstance(data_item, BECConnector):
                            bec_widgets.add(data_item)

        # 3) Convert each BECConnector to a JSON-like dict
        registry_data = {}
        for connector in bec_widgets:
            if not hasattr(connector, "config"):
                continue
            serialized = self._serialize_bec_connector(connector)
            registry_data[serialized["gui_id"]] = serialized

        # 4) Broadcast the final dictionary
        for callback in self._registry_update_callbacks:
            callback(registry_data)

        # FIXME this message is bugged and it was even before mine refactor of parent logic
        # logger.info(f"Broadcasting registry update: {registry_data} for {self.gui_id}")
        self.client.connector.xadd(
            MessageEndpoints.gui_registry_state(self.gui_id),
            msg_dict={"data": messages.GUIRegistryStateMessage(state=registry_data)},
            max_size=1,
        )

    def _serialize_bec_connector(self, connector: BECConnector) -> dict:
        """
        Create the serialization dict for a single BECConnector,
        setting 'parent_id' via the real nearest BECConnector parent.
        """

        parent_id = getattr(connector, "parent_id", None)
        if parent_id is None:
            parent = self._get_becwidget_ancestor(connector)
            parent_id = parent.gui_id if parent else None

        config_dict = connector.config.model_dump()
        config_dict["parent_id"] = parent_id

        return {
            "gui_id": connector.gui_id,
            "name": connector._name or connector.__class__.__name__,
            "widget_class": connector.__class__.__name__,
            "config": config_dict,
            "__rpc__": True,
        }

    @staticmethod
    def _get_becwidget_ancestor(widget):
        """
        Traverse up the parent chain to find the nearest BECConnector.
        Returns None if none is found.
        """
        from bec_widgets.utils import BECConnector

        parent = widget.parent()
        while parent is not None:
            if isinstance(parent, BECConnector):
                return parent
            parent = parent.parent()
        return None

    # Suppose clients register callbacks to receive updates
    def add_registry_update_callback(self, cb):
        self._registry_update_callbacks.append(cb)

    def shutdown(self):  # TODO not sure if needed when cleanup is done at level of BECConnector
        self.status = messages.BECStatus.IDLE
        self._heartbeat_timer.stop()
        self.emit_heartbeat()
        logger.info("Succeded in shutting down CLI server")
        self.client.shutdown()
