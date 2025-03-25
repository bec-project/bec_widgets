from __future__ import annotations

import os
import random
import string
from typing import TYPE_CHECKING

from bec_lib import bec_logger
from bec_widgets.utils.bec_dispatcher import BECDispatcher
from bec_widgets.utils.bec_widget import BECWidget
from qtpy.QtCore import QSize
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QApplication

import collections
from collections.abc import Callable
from typing import TYPE_CHECKING, Union

import redis
from bec_lib.client import BECClient
from bec_lib.logger import bec_logger
from bec_lib.redis_connector import MessageObject, RedisConnector
from bec_lib.service_config import ServiceConfig
from qtpy.QtCore import QObject
from qtpy.QtCore import Signal
import bec_widgets
from bec_widgets.cli.rpc.rpc_register import RPCRegister

logger = bec_logger.logger

MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class BECApplication(QApplication):
    """
    Custom QApplication class for BEC applications.
    """

    def __init__(
        self,
        *args,
        client=None,
        config: str | ServiceConfig = None,
        gui_id: str | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.gui_id = gui_id or self.generate_unique_identifier()
        self.dispatcher = BECDispatcher(client=client, config=config)
        self.rpc_register = RPCRegister()
        self.client = self.dispatcher.client  # fetch client from Dispatcher

        # Indicate this is a BEC application
        self.is_bec_app = True

        self.setup_bec_icon()
        self.register_all()

    def setup_bec_icon(self):
        icon = QIcon()
        icon.addFile(
            os.path.join(MODULE_PATH, "assets", "app_icons", "bec_widgets_icon.png"),
            size=QSize(48, 48),
        )
        self.setWindowIcon(icon)

    @staticmethod
    def generate_unique_identifier(length: int = 4) -> str:
        allowed_chars = string.ascii_lowercase + string.digits
        return "".join(random.choices(allowed_chars, k=length))

    # TODO not sure if needed
    def register_all(self):
        widgets = self.allWidgets()
        all_connections = self.rpc_register.list_all_connections()
        for widget in widgets:
            if not isinstance(widget, BECWidget):
                continue
            gui_id = getattr(widget, "gui_id", None)
            if gui_id and widget not in all_connections:
                self.rpc_register.add_rpc(widget)
                print(
                    f"[BECQApplication]: Registered widget {widget.__class__} with GUI ID: {gui_id}"
                )

    # TODO not sure if needed
    def list_all_bec_widgets(self):
        widgets = self.allWidgets()
        bec_widgets = []
        for widget in widgets:
            if isinstance(widget, BECWidget):
                bec_widgets.append(widget)
        return bec_widgets

    def list_hierarchy(self, only_bec_widgets: bool = True, show_parent: bool = True):
        """
        List the hierarchy of all BECWidgets in this application.

        Args:
            only_bec_widgets (bool): If True, prints only BECWidgets. Non-BECWidgets are skipped but their children are still traversed.
            show_parent (bool): If True, displays the immediate BECWidget ancestor for each item.
        """
        bec_widgets = self.list_all_bec_widgets()
        # Identify top-level BECWidgets (whose parent is not another BECWidget)
        top_level = [
            w for w in bec_widgets if not isinstance(self._get_becwidget_ancestor(w), BECWidget)
        ]

        print("[BECQApplication]: Listing BECWidget hierarchy:")
        for widget in top_level:
            self._print_becwidget_hierarchy(
                widget, indent=0, only_bec_widgets=only_bec_widgets, show_parent=show_parent
            )

    def _print_becwidget_hierarchy(self, widget, indent=0, only_bec_widgets=True, show_parent=True):
        # Decide if this widget should be printed
        is_bec = isinstance(widget, BECWidget)
        print_this = (not only_bec_widgets) or is_bec

        parent_info = ""
        if show_parent and is_bec:
            ancestor = self._get_becwidget_ancestor(widget)
            if ancestor is not None:
                parent_info = f" parent={ancestor.__class__.__name__}"
            else:
                parent_info = " parent=None"

        if print_this:
            prefix = " " * indent
            print(
                f"{prefix}- {widget.__class__.__name__} (objectName={widget.objectName()}){parent_info}"
            )

        # Always recurse so deeper BECWidgets aren't missed
        for child in widget.children():
            # Skip known non-BECWidgets if only_bec_widgets is True, but keep recursion
            # We'll still call _print_becwidget_hierarchy to discover any BECWidget descendants.
            self._print_becwidget_hierarchy(
                child, indent + 2, only_bec_widgets=only_bec_widgets, show_parent=show_parent
            )

    def _get_becwidget_ancestor(self, widget):
        """
        Climb the .parent() chain until finding another BECWidget, or None.
        """
        p = widget.parent()
        while p is not None:
            if isinstance(p, BECWidget):
                return p
            p = p.parent()
        return None

    def shutdown(self):
        self.dispatcher.disconnect_all()
        super().shutdown()
