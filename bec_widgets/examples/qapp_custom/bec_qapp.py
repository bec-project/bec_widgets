import os

from bec_widgets.utils.bec_widget import BECWidget
from qtpy.QtCore import QSize
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QApplication

import bec_widgets
from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils import BECDispatcher

MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class BECQApplication(QApplication):
    def __init__(self, client=None, gui_id: str | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = None
        self.rpc_register = None
        self.dispatcher = None
        self.is_bec_app = None
        self.bec_props = None
        self.gui_id = None
        self.setup_bec_features()

    def setup_bec_features(self):
        self.bec_props = {}
        self.is_bec_app = True
        self.dispatcher = BECDispatcher()
        self.rpc_register = RPCRegister()
        self.client = self.dispatcher.client
        self.gui_id = "1234"
        self.rpc_register.add_rpc(self)
        icon = QIcon()
        icon.addFile(
            os.path.join(MODULE_PATH, "assets", "app_icons", "bec_widgets_icon.png"),
            size=QSize(48, 48),
        )
        self.setWindowIcon(icon)
        # self.setup_icon()
        print("[BECQApplication]: Features initialized with BECDispatcher singleton.")

    def inject_property(self, name, value):
        self.bec_props[name] = value
        print(f"[BECQApplication]: Injected property '{name}' = {value}")

    def show_gui_id(self):
        print(f"[BECQApplication]: GUI ID: {self.gui_id}")

    def setup_icon(self):
        icon = QIcon()
        icon.addFile(
            os.path.join(MODULE_PATH, "assets", "app_icons", "bec_widgets_icon.png"),
            size=QSize(48, 48),
        )
        self.setWindowIcon(icon)
        print("[BECQApplication]: Window icon set.")

    def register_all(self):
        widgets = self.allWidgets()
        all_connections = self.rpc_register.list_all_connections()
        for widget in widgets:
            gui_id = getattr(widget, "gui_id", None)
            if gui_id and widget not in all_connections:
                self.rpc_register.add_rpc(widget)
                print(
                    f"[BECQApplication]: Registered widget {widget.__class__} with GUI ID: {gui_id}"
                )

    def list_all_bec_widgets(self):
        widgets = self.allWidgets()
        bec_widgets = []
        for widget in widgets:
            if isinstance(widget, BECWidget):
                bec_widgets.append(widget)
        return bec_widgets

    def shutdown(self):
        self.dispatcher.disconnect_all()
        super().shutdown()


def upgrade_to_becqapp():
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("No QApplication instance found!")

    if getattr(app, "is_bec_app", False):
        print("[BECQApplication]: Already upgraded.")
        return app

    # Only inject your explicitly defined Python methods
    methods_to_inject = ["setup_bec_features", "inject_property"]

    for method_name in methods_to_inject:
        method = getattr(BECQApplication, method_name)
        setattr(app, method_name, method.__get__(app, QApplication))

    app.setup_bec_features()
    print("[BECQApplication]: QApplication upgraded to BECQApplication.")
    return app
