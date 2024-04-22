import inspect
from typing import Literal

from bec_lib import MessageEndpoints, messages
from qtpy.QtCore import QTimer

from bec_widgets.utils import BECDispatcher
from bec_widgets.utils.bec_connector import BECConnector
from bec_widgets.widgets.dock.dock_area import BECDockArea
from bec_widgets.widgets.figure import BECFigure
from bec_widgets.widgets.plots import BECCurve, BECImageShow, BECWaveform


class BECWidgetsCLIServer:
    WIDGETS = [BECWaveform, BECFigure, BECCurve, BECImageShow]

    def __init__(
        self,
        gui_id: str = None,
        dispatcher: BECDispatcher = None,
        client=None,
        gui_class: BECFigure | BECDockArea = BECFigure,
    ) -> None:
        self.dispatcher = BECDispatcher() if dispatcher is None else dispatcher
        self.client = self.dispatcher.client if client is None else client
        self.client.start()
        self.gui_id = gui_id
        self.gui = gui_class(gui_id=self.gui_id)

        self.dispatcher.connect_slot(
            self.on_rpc_update, MessageEndpoints.gui_instructions(self.gui_id)
        )

        # Setup QTimer for heartbeat
        self._shutdown_event = False
        self._heartbeat_timer = QTimer()
        self._heartbeat_timer.timeout.connect(self.emit_heartbeat)
        self._heartbeat_timer.start(1000)  # Emit heartbeat every 1 seconds

    def on_rpc_update(self, msg: dict, metadata: dict):
        request_id = metadata.get("request_id")
        try:
            method = msg["action"]
            args = msg["parameter"].get("args", [])
            kwargs = msg["parameter"].get("kwargs", {})
            obj = self.get_object_from_config(msg["parameter"])
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
        # check if the object is the figure
        if gui_id == self.gui.gui_id:
            return self.gui
        # check if the object is a widget
        if gui_id in self.gui.containers:
            obj = self.gui.containers[config["gui_id"]]
            return obj
        if self.gui.containers:
            for widget in self.gui.containers.values():
                item = widget.find_widget_by_id(gui_id)
                if item:
                    return item

        raise ValueError(f"Object with gui_id {gui_id} not found")

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
        print("Heartbeat emitted")

    def shutdown(self):
        self._shutdown_event = True
        self._heartbeat_timer.stop()


if __name__ == "__main__":  # pragma: no cover
    import argparse
    import sys

    from qtpy.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("BEC Figure")
    win = QMainWindow()

    parser = argparse.ArgumentParser(description="BEC Widgets CLI Server")
    parser.add_argument("--id", type=str, help="The id of the server")
    parser.add_argument(
        "--gui_class",
        type=str,
        help="Name of the gui class to be rendered. Possible values: \n- BECFigure\n- BECDockArea",
    )

    args = parser.parse_args()

    if args.gui_class == "BECFigure":
        gui_class = BECFigure
    elif args.gui_class == "BECDockArea":
        gui_class = BECDockArea
    else:
        print(
            "Please specify a valid gui_class to run. Use -h for help."
            "\n Starting with default gui_class BECFigure."
        )
        gui_class = BECFigure

    # server = BECWidgetsCLIServer(gui_id=args.id, gui_class=gui_class)
    server = BECWidgetsCLIServer(gui_id="test", gui_class=gui_class)

    fig = server.gui
    win.setCentralWidget(fig)
    win.show()

    app.aboutToQuit.connect(server.shutdown)
    sys.exit(app.exec())
