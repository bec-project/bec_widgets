from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import Property, Qt, Slot
from qtpy.QtWidgets import QApplication, QHBoxLayout, QPushButton, QToolButton, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import set_theme


class DarkModeButton(BECWidget, QWidget):

    ICON_NAME = "dark_mode"
    PLUGIN = True
    RPC = False

    def __init__(
        self,
        parent: QWidget | None = None,
        client=None,
        gui_id: str | None = None,
        toolbar: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(client=client, gui_id=gui_id, theme_update=True, **kwargs)
        QWidget.__init__(self, parent)

        self._dark_mode_enabled = False
        self.layout = QHBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        if toolbar:
            self.mode_button = QToolButton()
        else:
            self.mode_button = QPushButton()

        self.dark_mode_enabled = self._get_qapp_dark_mode_state()
        self.update_mode_button()
        self.mode_button.clicked.connect(self.toggle_dark_mode)
        self.layout.addWidget(self.mode_button)
        self.setLayout(self.layout)
        self.setFixedSize(40, 40)

    @Slot(str)
    def apply_theme(self, theme: str):
        """
        Apply the theme to the widget.

        Args:
            theme(str, optional): The theme to be applied.
        """
        self.dark_mode_enabled = theme == "dark"
        self.update_mode_button()

    def _get_qapp_dark_mode_state(self) -> bool:
        """
        Get the dark mode state from the QApplication.

        Returns:
            bool: True if dark mode is enabled, False otherwise.
        """
        qapp = QApplication.instance()
        if hasattr(qapp, "theme") and qapp.theme.theme == "dark":
            return True

        return False

    @Property(bool)
    def dark_mode_enabled(self) -> bool:
        """
        The dark mode state. If True, dark mode is enabled. If False, light mode is enabled.
        """
        return self._dark_mode_enabled

    @dark_mode_enabled.setter
    def dark_mode_enabled(self, state: bool) -> None:
        self._dark_mode_enabled = state

    @Slot()
    def toggle_dark_mode(self) -> None:
        """
        Toggle the dark mode state. This will change the theme of the entire
        application to dark or light mode.
        """
        self.dark_mode_enabled = not self.dark_mode_enabled
        self.update_mode_button()
        set_theme("dark" if self.dark_mode_enabled else "light")

    def update_mode_button(self):
        icon = material_icon(
            "light_mode" if self.dark_mode_enabled else "dark_mode",
            size=(20, 20),
            convert_to_pixmap=False,
        )
        self.mode_button.setIcon(icon)
        self.mode_button.setToolTip("Set Light Mode" if self.dark_mode_enabled else "Set Dark Mode")


if __name__ == "__main__":

    app = QApplication([])
    set_theme("auto")
    w = DarkModeButton()
    w.show()

    app.exec_()
