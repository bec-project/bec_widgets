from __future__ import annotations

import os
import random
import string
from typing import TYPE_CHECKING, Any

from bec_lib.logger import bec_logger
from bec_lib.service_config import ServiceConfig
from qtpy.QtCore import QSize
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QApplication

import bec_widgets
from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils.bec_dispatcher import BECDispatcher
from bec_widgets.utils.cli_server import CLIServer

logger = bec_logger.logger

MODULE_PATH = os.path.dirname(bec_widgets.__file__)


if TYPE_CHECKING:  # pragma: no cover
    from bec_lib.client import BECClient


class BECApplication:
    """
    Custom QApplication class for BEC applications.
    """

    gui_id: str
    dispatcher: BECDispatcher
    rpc_register: RPCRegister
    client: BECClient
    is_bec_app: bool
    cli_server: CLIServer

    _instance: BECApplication
    _initialized: bool

    def __init__(
        self,
        *args,
        client=None,
        config: str | ServiceConfig | None = None,
        gui_id: str | None = None,
        **kwargs,
    ):
        if self._initialized:
            return
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication([])
        self._initialize_bec_app(client, config, gui_id)
        self._initialized = True

    def _initialize_bec_app(
        self, client=None, config: str | ServiceConfig | None = None, gui_id: str | None = None
    ):
        """
        Initialize the BECApplication instance with the given client and configuration.

        Args:
            app: The QApplication instance to initialize.
            client: The BECClient instance to use for communication.
            config: The ServiceConfig instance to use for configuration.
            gui_id: The unique identifier for this application.
        """
        self.app.gui_id = gui_id or BECApplication.generate_unique_identifier()
        self.app.dispatcher = BECDispatcher(client=client, config=config)
        self.app.rpc_register = RPCRegister()
        self.app.client = self.app.dispatcher.client  # type: ignore
        self.app.is_bec_app = True
        self.app.aboutToQuit.connect(self.shutdown)

        self.setup_bec_icon()

    def __instancecheck__(self, instance: Any) -> bool:
        return isinstance(instance, (QApplication, BECApplication))

    def __getattr__(self, name: str) -> Any:
        if hasattr(self.app, name):
            return getattr(self.app, name)
        return super().__getattribute__(name)

    def __new__(cls, *args, **kwargs) -> BECApplication:
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls)
            cls._initialized = False
        return cls._instance

    @classmethod
    def from_qapplication(
        cls, client=None, config: str | ServiceConfig | None = None, gui_id: str | None = None
    ) -> BECApplication:
        """
        Create a BECApplication instance from an existing QApplication instance.
        """
        print("from_qapplication")
        app = QApplication.instance()
        if isinstance(app, BECApplication):
            return app

        return cls(client=client, config=config, gui_id=gui_id)

    def setup_bec_icon(self):
        """
        Set the BEC icon for the application
        """
        icon = QIcon()
        icon.addFile(
            os.path.join(MODULE_PATH, "assets", "app_icons", "bec_widgets_icon.png"),
            size=QSize(48, 48),
        )
        self.setWindowIcon(icon)

    @staticmethod
    def generate_unique_identifier(length: int = 4) -> str:
        """
        Generate a unique identifier for the application.

        Args:
            length: The length of the identifier. Defaults to 4.

        Returns:
            str: The unique identifier.
        """
        allowed_chars = string.ascii_lowercase + string.digits
        return "".join(random.choices(allowed_chars, k=length))

        # # TODO not sure if needed
        # def register_all(self):
        #     widgets = self.allWidgets()
        #     all_connections = self.rpc_register.list_all_connections()
        #     for widget in widgets:
        #         if not isinstance(widget, BECWidget):
        #             continue
        #         gui_id = getattr(widget, "gui_id", None)
        #         if gui_id and widget not in all_connections:
        #             self.rpc_register.add_rpc(widget)
        #             print(
        #                 f"[BECQApplication]: Registered widget {widget.__class__} with GUI ID: {gui_id}"
        #             )

        # # TODO not sure if needed
        # def list_all_bec_widgets(self):
        #     widgets = self.allWidgets()
        #     bec_widgets = []
        #     for widget in widgets:
        #         if isinstance(widget, BECWidget):
        #             bec_widgets.append(widget)
        #     return bec_widgets

        # def list_hierarchy(self, only_bec_widgets: bool = True, show_parent: bool = True):
        #     """
        #     List the hierarchy of all BECWidgets in this application.

        #     Args:
        #         only_bec_widgets (bool): If True, prints only BECWidgets. Non-BECWidgets are skipped but their children are still traversed.
        #         show_parent (bool): If True, displays the immediate BECWidget ancestor for each item.
        #     """
        #     bec_widgets = self.list_all_bec_widgets()
        #     # Identify top-level BECWidgets (whose parent is not another BECWidget)
        #     top_level = [
        #         w for w in bec_widgets if not isinstance(self._get_becwidget_ancestor(w), BECWidget)
        #     ]

        #     print("[BECQApplication]: Listing BECWidget hierarchy:")
        #     for widget in top_level:
        #         self._print_becwidget_hierarchy(
        #             widget, indent=0, only_bec_widgets=only_bec_widgets, show_parent=show_parent
        #         )

        # def _print_becwidget_hierarchy(self, widget, indent=0, only_bec_widgets=True, show_parent=True):
        #     # Decide if this widget should be printed
        #     is_bec = isinstance(widget, BECWidget)
        #     print_this = (not only_bec_widgets) or is_bec

        #     parent_info = ""
        #     if show_parent and is_bec:
        #         ancestor = self._get_becwidget_ancestor(widget)
        #         if ancestor is not None:
        #             parent_info = f" parent={ancestor.__class__.__name__}"
        #         else:
        #             parent_info = " parent=None"

        #     if print_this:
        #         prefix = " " * indent
        #         print(
        #             f"{prefix}- {widget.__class__.__name__} (objectName={widget.objectName()}){parent_info}"
        #         )

        #     # Always recurse so deeper BECWidgets aren't missed
        #     for child in widget.children():
        #         # Skip known non-BECWidgets if only_bec_widgets is True, but keep recursion
        #         # We'll still call _print_becwidget_hierarchy to discover any BECWidget descendants.
        #         self._print_becwidget_hierarchy(
        #             child, indent + 2, only_bec_widgets=only_bec_widgets, show_parent=show_parent
        #         )

        # def _get_becwidget_ancestor(self, widget):
        #     """
        #     Climb the .parent() chain until finding another BECWidget, or None.
        #     """
        #     p = widget.parent()
        #     while p is not None:
        #         if isinstance(p, BECWidget):
        #             return p
        #         p = p.parent()
        # return None

    def shutdown(self):
        self.dispatcher.disconnect_all()
        self.cli_server.shutdown()
        self.rpc_register.reset_singleton()
        delattr(self.app, "gui_id")
        delattr(self.app, "dispatcher")
        delattr(self.app, "rpc_register")
        delattr(self.app, "client")
        delattr(self.app, "is_bec_app")
        delattr(self.app, "cli_server")
        self._initialized = False
        self._instance = None
