from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import PySide6QtAds as QtAds
import shiboken6
from bec_lib.logger import bec_logger
from qtpy.QtCore import QObject
from qtpy.QtWidgets import QApplication, QFileDialog, QWidget

from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils.bec_connector import BECConnector, ConnectionConfig
from bec_widgets.utils.error_popups import SafeConnect, SafeSlot
from bec_widgets.utils.rpc_decorator import rpc_timeout
from bec_widgets.utils.widget_io import WidgetHierarchy

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.widgets.containers.dock import BECDock

logger = bec_logger.logger


class BECWidget(BECConnector):
    """Mixin class for all BEC widgets, to handle cleanup"""

    # The icon name is the name of the icon in the icon theme, typically a name taken
    # from fonts.google.com/icons. Override this in subclasses to set the icon name.
    ICON_NAME = "widgets"
    USER_ACCESS = ["remove", "attach", "detach"]

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        client=None,
        config: ConnectionConfig = None,
        gui_id: str | None = None,
        theme_update: bool = False,
        start_busy: bool = False,
        busy_text: str = "Loading…",
        parent_dock: BECDock | None = None,  # TODO should go away -> issue created #473
        **kwargs,
    ):
        """
        Base class for all BEC widgets. This class should be used as a mixin class for all BEC widgets, e.g.:


        >>> class MyWidget(BECWidget, QWidget):
        >>>     def __init__(self, parent=None, client=None, config=None, gui_id=None):
        >>>         super().__init__(parent=parent, client=client, config=config, gui_id=gui_id)


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
        if theme_update:
            logger.debug(f"Subscribing to theme updates for {self.__class__.__name__}")
            self._connect_to_theme_change()

        # Initialize optional busy loader overlay utility (lazy by default)
        self._busy_overlay = None
        self._loading = False
        if start_busy and isinstance(self, QWidget):
            try:
                overlay = self._ensure_busy_overlay(busy_text=busy_text)
                if overlay is not None:
                    overlay.setGeometry(self.rect())
                    overlay.raise_()
                    overlay.show()
                    self._loading = True
            except Exception as exc:
                logger.debug(f"Busy loader init skipped: {exc}")

    def _connect_to_theme_change(self):
        """Connect to the theme change signal."""
        qapp = QApplication.instance()
        if hasattr(qapp, "theme"):
            SafeConnect(self, qapp.theme.theme_changed, self._update_theme)

    @SafeSlot(str)
    @SafeSlot()
    def _update_theme(self, theme: str | None = None):
        """Update the theme."""
        if theme is None:
            qapp = QApplication.instance()
            if hasattr(qapp, "theme"):
                theme = qapp.theme.theme
            else:
                theme = "dark"
        self._update_overlay_theme(theme)
        self.apply_theme(theme)

    def _ensure_busy_overlay(self, *, busy_text: str = "Loading…"):
        """Create the busy overlay on demand and cache it in _busy_overlay.
        Returns the overlay instance or None if not a QWidget.
        """
        if not isinstance(self, QWidget):
            return None
        overlay = getattr(self, "_busy_overlay", None)
        if overlay is None:
            from bec_widgets.utils.busy_loader import install_busy_loader

            overlay = install_busy_loader(self, text=busy_text, start_loading=False)
            self._busy_overlay = overlay
        return overlay

    def _init_busy_loader(self, *, start_busy: bool = False, busy_text: str = "Loading…") -> None:
        """Create and attach the loading overlay to this widget if QWidget is present."""
        if not isinstance(self, QWidget):
            return
        self._ensure_busy_overlay(busy_text=busy_text)
        if start_busy and self._busy_overlay is not None:
            self._busy_overlay.setGeometry(self.rect())
            self._busy_overlay.raise_()
            self._busy_overlay.show()

    def set_busy(self, enabled: bool, text: str | None = None) -> None:
        """
        Enable/disable the loading overlay. Optionally update the text.

        Args:
            enabled(bool): Whether to enable the loading overlay.
            text(str, optional): The text to display on the overlay. If None, the text is not changed.
        """
        if not isinstance(self, QWidget):
            return
        if getattr(self, "_busy_overlay", None) is None:
            self._ensure_busy_overlay(busy_text=text or "Loading…")
        if text is not None:
            self.set_busy_text(text)
        if enabled:
            self._busy_overlay.setGeometry(self.rect())
            self._busy_overlay.raise_()
            self._busy_overlay.show()
        else:
            self._busy_overlay.hide()
        self._loading = bool(enabled)

    def is_busy(self) -> bool:
        """
        Check if the loading overlay is enabled.

        Returns:
            bool: True if the loading overlay is enabled, False otherwise.
        """
        return bool(getattr(self, "_loading", False))

    def set_busy_text(self, text: str) -> None:
        """
        Update the text on the loading overlay.

        Args:
            text(str): The text to display on the overlay.
        """
        overlay = getattr(self, "_busy_overlay", None)
        if overlay is None:
            overlay = self._ensure_busy_overlay(busy_text=text)
        if overlay is not None:
            overlay.set_text(text)

    @SafeSlot(str)
    def apply_theme(self, theme: str):
        """
        Apply the theme to the widget.

        Args:
            theme(str, optional): The theme to be applied.
        """

    def _update_overlay_theme(self, theme: str):
        try:
            overlay = getattr(self, "_busy_overlay", None)
            if overlay is not None and hasattr(overlay, "update_palette"):
                overlay.update_palette()
        except Exception:
            logger.warning(f"Failed to apply theme {theme} to {self}")

    def get_help_md(self) -> str:
        """
        Method to override in subclasses to provide help text in markdown format.

        Returns:
            str: The help text in markdown format.
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

    def attach(self):
        dock = WidgetHierarchy.find_ancestor(self, QtAds.CDockWidget)
        if dock is None:
            return

        if not dock.isFloating():
            return
        dock.dockManager().addDockWidget(QtAds.DockWidgetArea.RightDockWidgetArea, dock)

    def detach(self):
        """
        Detach the widget from its parent dock widget (if widget is in the dock), making it a floating widget.
        """
        dock = WidgetHierarchy.find_ancestor(self, QtAds.CDockWidget)
        if dock is None:
            return
        if dock.isFloating():
            return
        dock.setFloating()

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

        # Tear down busy overlay explicitly to stop spinner and remove filters
        overlay = getattr(self, "_busy_overlay", None)
        if overlay is not None and shiboken6.isValid(overlay):
            try:
                overlay.hide()
                filt = getattr(overlay, "_filter", None)
                if filt is not None and shiboken6.isValid(filt):
                    try:
                        self.removeEventFilter(filt)
                    except Exception as exc:
                        logger.warning(f"Failed to remove event filter from busy overlay: {exc}")
                overlay.deleteLater()
            except Exception as exc:
                logger.warning(f"Failed to delete busy overlay: {exc}")
        self._busy_overlay = None

    def closeEvent(self, event):
        """Wrap the close even to ensure the rpc_register is cleaned up."""
        try:
            if not self._destroyed:
                self.cleanup()
                self._destroyed = True
        finally:
            super().closeEvent(event)  # pylint: disable=no-member
