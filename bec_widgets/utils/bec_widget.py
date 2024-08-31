from __future__ import annotations

from qtpy.QtCore import Slot
from qtpy.QtWidgets import QApplication, QWidget

from bec_widgets.utils.bec_connector import BECConnector, ConnectionConfig
from bec_widgets.utils.colors import set_theme


class BECWidget(BECConnector):
    """Mixin class for all BEC widgets, to handle cleanup"""

    # The icon name is the name of the icon in the icon theme, typically a name taken
    # from fonts.google.com/icons. Override this in subclasses to set the icon name.
    ICON_NAME = "widgets"

    def __init__(
        self,
        client=None,
        config: ConnectionConfig = None,
        gui_id: str = None,
        theme_update: bool = False,
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
        if not isinstance(self, QWidget):
            raise RuntimeError(f"{repr(self)} is not a subclass of QWidget")
        super().__init__(client, config, gui_id)

        # Set the theme to auto if it is not set yet
        app = QApplication.instance()
        if not hasattr(app, "theme"):
            set_theme("auto")

        if theme_update:
            self._connect_to_theme_change()

    def _connect_to_theme_change(self):
        """Connect to the theme change signal."""
        qapp = QApplication.instance()
        if hasattr(qapp, "theme_signal"):
            qapp.theme_signal.theme_updated.connect(self._update_theme)

    def _update_theme(self, theme: str):
        """Update the theme."""
        if theme is None:
            qapp = QApplication.instance()
            if hasattr(qapp, "theme"):
                theme = qapp.theme["theme"]
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

    def closeEvent(self, event):
        self.rpc_register.remove_rpc(self)
        try:
            self.cleanup()
        finally:
            super().closeEvent(event)
