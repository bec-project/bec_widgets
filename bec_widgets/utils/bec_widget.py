from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import shiboken6
from bec_lib.logger import bec_logger
from qtpy.QtCore import QBuffer, QByteArray, QIODevice, QObject, Qt
from qtpy.QtGui import QFont, QPixmap
from qtpy.QtWidgets import QApplication, QFileDialog, QLabel, QVBoxLayout, QWidget

import bec_widgets.widgets.containers.qt_ads as QtAds
from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils.bec_connector import BECConnector, ConnectionConfig
from bec_widgets.utils.error_popups import SafeConnect, SafeSlot
from bec_widgets.utils.rpc_decorator import rpc_timeout
from bec_widgets.utils.widget_io import WidgetHierarchy
from bec_widgets.widgets.utility.spinner.spinner import SpinnerWidget

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.utils.busy_loader import BusyLoaderOverlay
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
        super().__init__(client=client, config=config, gui_id=gui_id, **kwargs)
        if not isinstance(self, QObject):
            raise RuntimeError(f"{repr(self)} is not a subclass of QWidget")
        if theme_update:
            logger.debug(f"Subscribing to theme updates for {self.__class__.__name__}")
            self._connect_to_theme_change()

        # Initialize optional busy loader overlay utility (lazy by default)
        self._busy_overlay: "BusyLoaderOverlay" | None = None
        self._busy_state_widget: QWidget | None = None

        self._loading = False
        if start_busy and isinstance(self, QWidget):
            self._busy_overlay = self._install_busy_loader()
            self._adjust_busy_overlay()
            self._loading = True

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

    def create_busy_state_widget(self) -> QWidget:
        """
        Method to create a custom busy state widget to be shown in the busy overlay.
        Child classes should overrid this method to provide a custom widget if desired.

        Returns:
            QWidget: The custom busy state widget.

        NOTE:
            The implementation here is a SpinnerWidget with a "Loading..." label. This is the default
            busy state widget for all BECWidgets. However, child classes with specific needs for the
            busy state can easily overrite this method to provide a custom widget. The signature of
            the method must be preserved to ensure compatibility with the busy overlay system. If
            the widget provides a 'cleanup' method, it will be called when the overlay is cleaned up.

            The widget may connect to the _busy_overlay signals foreground_color_changed and
            scrim_color_changed to update its colors when the theme changes.
        """

        # Widget
        class BusyStateWidget(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                # label
                label = QLabel("Loading...", self)
                label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
                f = QFont(label.font())
                f.setBold(True)
                f.setPointSize(f.pointSize() + 1)
                label.setFont(f)

                # spinner
                spinner = SpinnerWidget(self)
                spinner.setFixedSize(42, 42)

                # Layout
                lay = QVBoxLayout(self)
                lay.setContentsMargins(24, 24, 24, 24)
                lay.setSpacing(10)
                lay.addStretch(1)
                lay.addWidget(spinner, 0, Qt.AlignHCenter)
                lay.addWidget(label, 0, Qt.AlignHCenter)
                lay.addStretch(1)
                self.setLayout(lay)

            def showEvent(self, event):
                """Show event to start the spinner."""
                super().showEvent(event)
                for child in self.findChildren(SpinnerWidget):
                    child.start()

            def hideEvent(self, event):
                """Hide event to stop the spinner."""
                super().hideEvent(event)
                for child in self.findChildren(SpinnerWidget):
                    child.stop()

        widget = BusyStateWidget(self)

        return widget

    def _install_busy_loader(self) -> "BusyLoaderOverlay" | None:
        """
        Create the busy overlay on demand and cache it in _busy_overlay.
        Returns the overlay instance or None if not a QWidget.
        """
        if not isinstance(self, QWidget):
            return None
        overlay = getattr(self, "_busy_overlay", None)
        if overlay is None:
            from bec_widgets.utils.busy_loader import install_busy_loader

            overlay = install_busy_loader(self, start_loading=False)
            self._busy_overlay = overlay

        # Create and set the busy state widget
        self._busy_state_widget = self.create_busy_state_widget()
        self._busy_overlay.set_widget(self._busy_state_widget)
        return overlay

    def _adjust_busy_overlay(self) -> None:
        """Create and attach the loading overlay to this widget if QWidget is present."""
        if not isinstance(self, QWidget):
            return
        if self._busy_overlay is not None:
            self._busy_overlay.setGeometry(self.rect())  # pylint: disable=no-member
            self._busy_overlay.raise_()
            self._busy_overlay.show()

    def set_busy(self, enabled: bool) -> None:
        """
        Set the busy state of the widget. This will show or hide the loading overlay, which will
        block user interaction with the widget and show the busy_state_widget if provided. Per
        default, the busy state widget is a spinner with "Loading..." text.

        Args:
            enabled(bool): Whether to enable the busy state.
        """
        if not isinstance(self, QWidget):
            return
        # If not yet installed, install the busy overlay now together with the busy state widget
        if self._busy_overlay is None:
            self._busy_overlay = self._install_busy_loader()
        if enabled:
            self._adjust_busy_overlay()
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
            if overlay is not None:
                overlay._update_palette()
        except Exception:
            logger.warning(f"Failed to apply theme {theme} to {self}")

    def get_help_md(self) -> str:
        """
        Method to override in subclasses to provide help text in markdown format.

        Returns:
            str: The help text in markdown format.
        """
        return ""

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

    def screenshot_bytes(
        self,
        *,
        max_width: int | None = None,
        max_height: int | None = None,
        fmt: str = "PNG",
        quality: int = -1,
    ) -> QByteArray:
        """
        Grab this widget, optionally scale to a max size, and return encoded image bytes.

        If max_width/max_height are omitted (the default), capture at full resolution.

        Args:
            max_width(int, optional): Maximum width of the screenshot.
            max_height(int, optional): Maximum height of the screenshot.
            fmt(str, optional): Image format (e.g., "PNG", "JPEG").
            quality(int, optional): Image quality (0-100), -1 for default.

        Returns:
            QByteArray: The screenshot image bytes.
        """
        if not isinstance(self, QWidget):
            return QByteArray()

        if not hasattr(self, "grab"):
            raise RuntimeError(f"Cannot take screenshot of non-QWidget instance: {repr(self)}")

        pixmap: QPixmap = self.grab()
        if pixmap.isNull():
            return QByteArray()
        if max_width is not None or max_height is not None:
            w = max_width if max_width is not None else pixmap.width()
            h = max_height if max_height is not None else pixmap.height()
            pixmap = pixmap.scaled(
                w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.QSmoothTransformation
            )
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buf, fmt, quality)
        buf.close()
        return ba

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

                # Cleanup the overlay widget. This will call cleanup on the custom widget if present.

                overlay.cleanup()
                overlay.deleteLater()
            except Exception as exc:
                logger.warning(f"Failed to delete busy overlay: {exc}")

    def closeEvent(self, event):
        """Wrap the close even to ensure the rpc_register is cleaned up."""
        try:
            if not self._destroyed:
                self.cleanup()
                self._destroyed = True
        finally:
            super().closeEvent(event)  # pylint: disable=no-member
