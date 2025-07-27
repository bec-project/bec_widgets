from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import darkdetect
import shiboken6
from bec_lib.logger import bec_logger
from qtpy.QtCore import QObject
from qtpy.QtWidgets import QApplication, QFileDialog, QWidget

from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils.bec_connector import BECConnector, ConnectionConfig
from bec_widgets.utils.colors import set_theme
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.rpc_decorator import rpc_timeout

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
        parent_dock: BECDock | None = None,  # TODO should go away -> issue created #473
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
            client=client, config=config, gui_id=gui_id, parent_dock=parent_dock, **kwargs
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

    @SafeSlot(str)
    def apply_theme(self, theme: str):
        """
        Apply the theme to the widget.

        Args:
            theme(str, optional): The theme to be applied.
        """

    @SafeSlot()
    @SafeSlot(str)
    @rpc_timeout(None)
    def screenshot(self, file_name: str | None = None):
        """
        Take a screenshot of the dock area and save it to a file.
        """
        if not isinstance(self, QWidget):
            logger.error("Cannot take screenshot of non-QWidget instance")
            return

        screenshot = self.grab()
        if file_name is None:
            file_name, _ = QFileDialog.getSaveFileName(
                self,
                "Save Screenshot",
                f"bec_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg);;All Files (*)",
            )
        if not file_name:
            return
        screenshot.save(file_name)
        logger.info(f"Screenshot saved to {file_name}")

    def cleanup(self):
        """Cleanup the widget."""
        with RPCRegister.delayed_broadcast():
            # All widgets need to call super().cleanup() in their cleanup method
            logger.info(f"Registry cleanup for widget {self.__class__.__name__}")
            self.rpc_register.remove_rpc(self)
        children = self.findChildren(BECWidget)
        for child in children:
            if not shiboken6.isValid(child):
                # If the child is not valid, it means it has already been deleted
                continue
            child.close()
            child.deleteLater()

    def closeEvent(self, event):
        """Wrap the close even to ensure the rpc_register is cleaned up."""
        try:
            if not self._destroyed:
                self.cleanup()
                self._destroyed = True
        finally:
            super().closeEvent(event)  # pylint: disable=no-member
