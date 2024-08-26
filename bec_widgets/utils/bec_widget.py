from qtpy.QtWidgets import QApplication, QWidget

from bec_widgets.utils.bec_connector import BECConnector, ConnectionConfig
from bec_widgets.utils.colors import set_theme


class BECWidget(BECConnector):
    """Mixin class for all BEC widgets, to handle cleanup"""

    def __init__(self, client=None, config: ConnectionConfig = None, gui_id: str = None):
        if not isinstance(self, QWidget):
            raise RuntimeError(f"{repr(self)} is not a subclass of QWidget")
        super().__init__(client, config, gui_id)

        # Set the theme to auto if it is not set yet
        app = QApplication.instance()
        if not hasattr(app, "theme"):
            set_theme("dark")

    def cleanup(self):
        """Cleanup the widget."""

    def closeEvent(self, event):
        self.rpc_register.remove_rpc(self)
        try:
            self.cleanup()
        finally:
            super().closeEvent(event)
