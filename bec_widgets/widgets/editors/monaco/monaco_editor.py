import os

from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.editors.monaco.core.monaco_widget import MonacoWidget as MonacoEditor


class MonacoWidget(BECWidget, QWidget):
    """
    A simple Monaco editor widget
    """

    PLUGIN = True
    ICON_NAME = "code"
    USER_ACCESS = ["set_text", "get_text", "set_language", "set_theme"]

    def __init__(self, parent=None, config=None, client=None, gui_id=None, **kwargs):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.editor = MonacoEditor(self)
        layout.addWidget(self.editor)
        self.setLayout(layout)

    def set_text(self, text: str) -> None:
        self.editor.setText(text)

    def get_text(self) -> str:
        return self.editor.text()

    def set_language(self, language: str) -> None:
        self.editor.setLanguage(language)

    def set_theme(self, theme: str) -> None:
        self.editor.setTheme(theme)


if __name__ == "__main__":
    qapp = QApplication([])
    widget = MonacoWidget()
    widget.set_language("python")
    widget.set_theme("vs-dark")
    widget.set_text(
        """
        # This is a comment
        def hello_world():
            print("Hello, world!")
        """
    )

    widget.show()
    qapp.exec_()
