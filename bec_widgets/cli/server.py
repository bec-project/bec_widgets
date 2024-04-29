import inspect
import threading
import time

from bec_lib import MessageEndpoints, messages
from qtpy.QtCore import QTimer

from bec_widgets.cli.rpc_register import RPCRegister
from bec_widgets.utils import BECDispatcher
from bec_widgets.utils.bec_connector import BECConnector
from bec_widgets.widgets.figure import BECFigure
from bec_widgets.widgets.plots import BECCurve, BECImageShow, BECWaveform


class BECWidgetsCLIServer:
    WIDGETS = [BECWaveform, BECFigure, BECCurve, BECImageShow]

    def __init__(
        self, gui_id: str = None, dispatcher: BECDispatcher = None, client=None, config=None
    ) -> None:
        self.dispatcher = BECDispatcher(config=config) if dispatcher is None else dispatcher
        self.client = self.dispatcher.client if client is None else client
        self.client.start()
        self.gui_id = gui_id
        self.fig = BECFigure(gui_id=self.gui_id)
        self.rpc_register = RPCRegister()
        self.rpc_register.add_rpc(self.fig)

        self.dispatcher.connect_slot(
            self.on_rpc_update, MessageEndpoints.gui_instructions(self.gui_id)
        )

        # Setup QTimer for heartbeat
        self._shutdown_event = False
        self._heartbeat_timer = QTimer()
        self._heartbeat_timer.timeout.connect(self.emit_heartbeat)
        self._heartbeat_timer.start(200)  # Emit heartbeat every 1 seconds

    def on_rpc_update(self, msg: dict, metadata: dict):
        request_id = metadata.get("request_id")
        try:
            obj = self.get_object_from_config(msg["parameter"])
            method = msg["action"]
            args = msg["parameter"].get("args", [])
            kwargs = msg["parameter"].get("kwargs", {})
            res = self.run_rpc(obj, method, args, kwargs)
        except Exception as e:
            print(e)
            self.send_response(request_id, False, {"error": str(e)})
        else:
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
        method_obj = getattr(obj, method)
        # check if the method accepts args and kwargs
        if not callable(method_obj):
            res = method_obj
        else:
            sig = inspect.signature(method_obj)
            if sig.parameters:
                res = method_obj(*args, **kwargs)
            else:
                res = method_obj()

        if isinstance(res, list):
            res = [self.serialize_object(obj) for obj in res]
        elif isinstance(res, dict):
            res = {key: self.serialize_object(val) for key, val in res.items()}
        else:
            res = self.serialize_object(res)
        return res

    def serialize_object(self, obj):
        if isinstance(obj, BECConnector):
            return {
                "gui_id": obj.gui_id,
                "widget_class": obj.__class__.__name__,
                "config": obj.config.model_dump(),
                "__rpc__": True,
            }
        return obj

    def emit_heartbeat(self):
        if self._shutdown_event is False:
            self.client.connector.set(
                MessageEndpoints.gui_heartbeat(self.gui_id),
                messages.StatusMessage(name=self.gui_id, status=1, info={}),
                expire=10,
            )

    def shutdown(self):
        self._shutdown_event = True
        self._heartbeat_timer.stop()
        self.client.shutdown()


if __name__ == "__main__":  # pragma: no cover
    import argparse
    import sys

    from qtpy.QtCore import QSize
    from qtpy.QtGui import QIcon
    from qtpy.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("BEC Figure")
    icon = QIcon()
    icon.addFile("bec_widgets_icon.png", size=QSize(48, 48))
    app.setWindowIcon(icon)

    win = QMainWindow()
    win.setWindowTitle("BEC Widgets")

    parser = argparse.ArgumentParser(description="BEC Widgets CLI Server")
    parser.add_argument("--id", type=str, help="The id of the server")
    parser.add_argument("--config", type=str, help="Config to connect to redis.")

    args = parser.parse_args()

    server = BECWidgetsCLIServer(gui_id=args.id, config=args.config)
    # server = BECWidgetsCLIServer(gui_id="test",config="awi-bec-dev-01:6379")

    fig = server.fig
    win.setCentralWidget(fig)
    win.show()

    app.aboutToQuit.connect(server.shutdown)
    sys.exit(app.exec())
