import inspect

from bec_lib import MessageEndpoints, messages

from bec_widgets.utils import BECDispatcher
from bec_widgets.widgets.figure import BECFigure
from bec_widgets.widgets.plots import BECPlotBase, BECWaveform1D, BECCurve


class BECWidgetsCLIServer:
    WIDGETS = [BECWaveform1D, BECFigure, BECCurve]

    def __init__(self, gui_id: str = None) -> None:
        self.dispatcher = BECDispatcher()
        self.client = self.dispatcher.client
        self.client.start()
        self.gui_id = gui_id
        self.fig = BECFigure(gui_id=self.gui_id)
        print(f"Server started with gui_id {self.gui_id}")

        self.dispatcher.connect_slot(
            self.on_rpc_update, MessageEndpoints.gui_instructions(self.gui_id)
        )
        self.fig.start()

    @staticmethod
    def _rpc_update_handler(msg, parent):
        parent.on_rpc_update(msg.value)

    def on_rpc_update(self, msg: dict, metadata: dict):
        try:
            method = msg["action"]
            args = msg["parameter"].get("args", [])
            kwargs = msg["parameter"].get("kwargs", {})
            request_id = metadata.get("request_id")
            obj = self.get_object_from_config(msg["parameter"])
            res = self.run_rpc(obj, method, args, kwargs)
            self.send_response(request_id, True, {"result": res})
        except Exception as e:
            print(e)
            self.send_response(request_id, False, {"error": str(e)})

    def send_response(self, request_id: str, accepted: bool, msg: dict):
        self.client.producer.set(
            MessageEndpoints.gui_instruction_response(request_id),
            messages.RequestResponseMessage(accepted=accepted, message=msg),
            expire=60,
        )

    def get_object_from_config(self, config: dict):
        gui_id = config.get("gui_id")
        if gui_id == self.fig.gui_id:
            return self.fig
        if gui_id in self.fig.widgets:
            obj = self.fig.widgets[config["gui_id"]]
            return obj
        raise ValueError(f"Object with gui_id {gui_id} not found")

    def run_rpc(self, obj, method, args, kwargs):
        method_obj = getattr(obj, method)
        # check if the method accepts args and kwargs
        sig = inspect.signature(method_obj)
        if sig.parameters:
            res = method_obj(*args, **kwargs)
        else:
            res = method_obj()
        if isinstance(res, BECPlotBase):
            res = {
                "gui_id": res.gui_id,
                "widget_class": res.__class__.__name__,
                "config": res.config.model_dump(),
            }
        return res


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BEC Widgets CLI Server")
    parser.add_argument("--id", type=str, help="The id of the server")

    args = parser.parse_args()

    server = BECWidgetsCLIServer(gui_id=args.id)
    # server = BECWidgetsCLIServer(gui_id="test")
