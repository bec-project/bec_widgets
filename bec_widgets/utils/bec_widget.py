from __future__ import annotations

from typing import TYPE_CHECKING

import darkdetect
from bec_lib.logger import bec_logger
from PySide6.QtCore import QObject
from qtpy.QtCore import Slot
from qtpy.QtWidgets import QApplication

from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils.bec_connector import BECConnector, ConnectionConfig
from bec_widgets.utils.colors import set_theme

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.widgets.containers.dock import BECDock

logger = bec_logger.logger


class BECWidget(BECConnector):
    """Mixin class for all BEC widgets, to handle cleanup"""

    # The icon name is the name of the icon in the icon theme, typically a name taken
    # from fonts.google.com/icons. Override this in subclasses to set the icon name.
    ICON_NAME = "widgets"
    USER_ACCESS = ["remove"]

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        client=None,
        config: ConnectionConfig = None,
        gui_id: str | None = None,
        theme_update: bool = False,
        parent_dock: BECDock | None = None,  # TODO should not be there
        parent_id: str | None = None,
        **kwargs,
    ):
        """
        Base class for all BEC widgets. This class should be used as a mixin class for all BEC widgets, e.g.:


        >>> class MyWidget(BECWidget, QWidget):
        >>>     def __init__(self, parent=None, client=None, config=None, gui_id=None):
        >>>         super().__init__(client=client, config=config, gui_id=gui_id)
        >>>         QWidget.__init__(self, parent=parent)


        Args:
            client(BECClient, optional): The BEC client.
            config(ConnectionConfig, optional): The connection configuration.
            gui_id(str, optional): The GUI ID.
            theme_update(bool, optional): Whether to subscribe to theme updates. Defaults to False. When set to True, the
                widget's apply_theme method will be called when the theme changes.
        """

        super().__init__(
            client=client,
            config=config,
            gui_id=gui_id,
            parent_dock=parent_dock,
            parent_id=parent_id,
            **kwargs,
        )
        if not isinstance(self, QObject):
            raise RuntimeError(f"{repr(self)} is not a subclass of QWidget")
        app = QApplication.instance()
        if not hasattr(app, "theme"):
            # DO NOT SET THE THEME TO AUTO! Otherwise, the qwebengineview will segfault
            # Instead, we will set the theme to the system setting on startup
            if darkdetect.isDark():
                set_theme("dark")
            else:
                set_theme("light")

        if theme_update:
            logger.debug(f"Subscribing to theme updates for {self.__class__.__name__}")
            self._connect_to_theme_change()

    def _ensure_bec_app(self):
        # pylint: disable=import-outside-toplevel
        from bec_widgets.utils.bec_qapp import BECApplication

        app = BECApplication.from_qapplication()
        return app

    def _connect_to_theme_change(self):
        """Connect to the theme change signal."""
        qapp = QApplication.instance()
        if hasattr(qapp, "theme_signal"):
            qapp.theme_signal.theme_updated.connect(self._update_theme)

    def _update_theme(self, theme: str | None = None):
        """Update the theme."""
        if theme is None:
            qapp = QApplication.instance()
            if hasattr(qapp, "theme"):
                theme = qapp.theme.theme
            else:
                theme = "dark"
        self.apply_theme(theme)

    @Slot(str)
    def apply_theme(self, theme: str):
        """
        Apply the theme to the widget.

        Args:
            theme(str, optional): The theme to be applied.
        """

    def cleanup(self):
        """Cleanup the widget."""
        with RPCRegister.delayed_broadcast():
            # All widgets need to call super().cleanup() in their cleanup method
            logger.info(f"Registry cleanup for widget {self.__class__.__name__}")
            self.rpc_register.remove_rpc(self)

    def closeEvent(self, event):
        """Wrap the close even to ensure the rpc_register is cleaned up."""
        try:
            self.cleanup()
        finally:
            super().closeEvent(event)  # pylint: disable=no-member
