import inspect
import threading
import time

from bec_lib import MessageEndpoints, messages

from bec_widgets.utils import BECDispatcher
from bec_widgets.utils.bec_connector import BECConnector
from bec_widgets.widgets.figure import BECFigure
from bec_widgets.widgets.plots import BECCurve, BECImageShow, BECWaveform1D


class BECWidgetsCLIServer:
    WIDGETS = [BECWaveform1D, BECFigure, BECCurve, BECImageShow]

    def __init__(self, gui_id: str = None, dispatcher: BECDispatcher = None) -> None:
        self.dispatcher = BECDispatcher() if dispatcher is None else dispatcher
        self.client = self.dispatcher.client
        self.client.start()
        self.gui_id = gui_id
        self.fig = BECFigure(gui_id=self.gui_id)
        # print(f"Server started with gui_id {self.gui_id}")
        self._shutdown_event = threading.Event()
        self.dispatcher.connect_slot(
            self.on_rpc_update, MessageEndpoints.gui_instructions(self.gui_id)
        )
        self._heartbeat = threading.Thread(target=self.start_heartbeat, daemon=True)
        self._heartbeat.start()

    def start(self):
        """Start the figure window."""
        self.fig.start()

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
        if gui_id == self.fig.gui_id:
            return self.fig
        # check if the object is a widget
        if gui_id in self.fig._widgets:
            obj = self.fig._widgets[config["gui_id"]]
            return obj
        if self.fig._widgets:
            for widget in self.fig._widgets.values():
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

    def start_heartbeat(self):
        while not self._shutdown_event.is_set():
            self.client.connector.set(
                MessageEndpoints.gui_heartbeat(self.gui_id),
                messages.StatusMessage(name=self.gui_id, status=1, info={}),
                expire=10,
            )
            time.sleep(3)


if __name__ == "__main__":  # pragma: no cover
    import argparse
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)

    parser = argparse.ArgumentParser(description="BEC Widgets CLI Server")
    parser.add_argument("--id", type=str, help="The id of the server")

    args = parser.parse_args()

    server = BECWidgetsCLIServer(gui_id=args.id)
    # server = BECWidgetsCLIServer(gui_id="test")
    server.start()
    sys.exit(app.exec())
