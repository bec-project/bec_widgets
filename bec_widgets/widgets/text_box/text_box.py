import re

from qtpy.QtWidgets import QTextEdit

from bec_widgets.utils import BECConnector


class TextBox(BECConnector, QTextEdit):

    USER_ACCESS = ["set_color", "set_text", "set_font_size"]

    def __init__(self, text: str = "", parent=None, client=None, config=None, gui_id=None):
        super().__init__(client=client, config=config, gui_id=gui_id)
        QTextEdit.__init__(self, parent=parent)

        self.setReadOnly(True)
        self._background_color = "#FFF"
        self._font_color = "#000"
        self._font_size = 12
        self.set_color(self._background_color, self._font_color)
        self.setGeometry(self.rect())
        self._text = text
        self.set_text(text)

    def set_color(self, background_color: str, font_color: str) -> None:
        """Set the background color of the Widget.

        Args:
            background_color (str): The color to set the background in HEX.
            font_color (str): The color to set the font in HEX.

        """
        self._background_color = background_color
        self._font_color = font_color
        self._update_stylesheet()

    def set_font_size(self, size: int) -> None:
        """Set the font size of the text in the Widget."""
        self._font_size = size
        self._update_stylesheet()

    def _update_stylesheet(self):
        """Update the stylesheet of the widget."""
        self.setStyleSheet(
            f"background-color: {self._background_color}; color: {self._font_color}; font-size: {self._font_size}px"
        )

    def set_text(self, text: str) -> None:
        """Set the text of the Widget"""
        if self.is_html(text):
            self.setHtml(text)
        else:
            self.setPlainText(text)
        self._text = text

    def is_html(self, text: str) -> bool:
        """Check if the text contains HTML tags.

        Args:
            text (str): The text to check.

        Returns:
            bool: True if the text contains HTML tags, False otherwise.
        """
        return bool(re.search(r"<[a-zA-Z/][^>]*>", text))


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)

    widget = TextBox()
    widget.show()
    sys.exit(app.exec())
