from qtpy.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty
from bec_widgets.widgets.containers.dock.dock import BECDock


class SignalDisplay(BECWidget, QWidget):
    def __init__(
        self,
        client=None,
        device: str = "",
        config: ConnectionConfig = None,
        gui_id: str | None = None,
        theme_update: bool = False,
        parent_dock: BECDock | None = None,
        **kwargs,
    ):
        super().__init__(client, config, gui_id, theme_update, parent_dock, **kwargs)
        self.get_bec_shortcuts()
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.addWidget(QLabel(f"Signals for {self.dev}:"))
        self.device = device


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import set_theme

    app = QApplication(sys.argv)
    set_theme("light")
    widget = SignalDisplay(device="samx")
    widget.show()
    sys.exit(app.exec_())
