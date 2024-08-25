from bec_qthemes import material_icon
from qtpy.QtCore import Property, Qt, Slot
from qtpy.QtWidgets import QHBoxLayout, QPushButton, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import set_theme


class DarkModeButton(BECWidget, QWidget):
    USER_ACCESS = ["set_dark_mode_enabled"]

    def __init__(
        self, parent: QWidget | None = None, client=None, gui_id: str | None = None
    ) -> None:
        super().__init__(client=client, gui_id=gui_id)
        QWidget.__init__(self, parent)

        self._dark_mode_enabled = False
        self.layout = QHBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        icon = material_icon("dark_mode", size=(20, 20), convert_to_pixmap=False)
        self.mode_button = QPushButton(icon=icon)
        self.update_mode_button()
        self.mode_button.clicked.connect(self.set_dark_mode_enabled)
        self.layout.addWidget(self.mode_button)
        self.setLayout(self.layout)
        self.setFixedSize(40, 40)

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
    def set_dark_mode_enabled(self) -> None:
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
    from qtpy.QtWidgets import QApplication

    app = QApplication([])

    w = DarkModeButton()
    w.show()

    app.exec_()
