import re

from pydantic import Field, field_validator
from qtpy.QtWidgets import QTextEdit

from bec_widgets.utils.bec_connector import BECConnector, ConnectionConfig
from bec_widgets.utils.colors import Colors


class TextBoxConfig(ConnectionConfig):

    theme: str = Field("dark", description="The theme of the figure widget.")
    font_color: str = Field("#FFF", description="The font color of the text")
    background_color: str = Field("#000", description="The background color of the widget.")
    font_size: int = Field(16, description="The font size of the text in the widget.")
    text: str = Field("", description="The text to display in the widget.")

    @classmethod
    @field_validator("theme")
    def validate_theme(cls, v):
        """Validate the theme of the figure widget."""
        if v not in ["dark", "light"]:
            raise ValueError("Theme must be either 'dark' or 'light'")
        return v

    _validate_font_color = field_validator("font_color")(Colors.validate_color)
    _validate_background_color = field_validator("background_color")(Colors.validate_color)


class TextBox(BECConnector, QTextEdit):

    USER_ACCESS = ["set_color", "set_text", "set_font_size"]

    def __init__(self, parent=None, text: str = "", client=None, config=None, gui_id=None):
        if config is None:
            config = TextBoxConfig(widget_class=self.__class__.__name__)
        else:
            if isinstance(config, dict):
                config = TextBoxConfig(**config)
            self.config = config
        super().__init__(client=client, config=config, gui_id=gui_id)
        QTextEdit.__init__(self, parent=parent)

        self.config = config
        self.setReadOnly(True)
        self.setGeometry(self.rect())
        self.set_color(self.config.background_color, self.config.font_color)
        if not text:
            text = "<h1>Welcome to the BEC Widget TextBox</h1><p>A widget that allows user to display text in plain and HTML format.</p><p>This is an example of displaying HTML text.</p>"
        self.set_text(text)

    def change_theme(self) -> None:
        """
        Change the theme of the figure widget.
        """
        if self.config.theme == "dark":
            theme = "light"
            font_color = "#000"
            background_color = "#FFF"
        else:
            theme = "dark"
            font_color = "#FFF"
            background_color = "#000"
        self.config.theme = theme
        self.set_color(background_color, font_color)

    def set_color(self, background_color: str, font_color: str) -> None:
        """Set the background color of the widget.

        Args:
            background_color (str): The color to set the background in HEX.
            font_color (str): The color to set the font in HEX.

        """
        self.config.background_color = background_color
        self.config.font_color = font_color
        self._update_stylesheet()

    def set_font_size(self, size: int) -> None:
        """Set the font size of the text in the widget.

        Args:
            size (int): The font size to set.
        """
        self.config.font_size = size
        self._update_stylesheet()

    def _update_stylesheet(self):
        """Update the stylesheet of the widget."""
        self.setStyleSheet(
            f"background-color: {self.config.background_color}; color: {self.config.font_color}; font-size: {self.config.font_size}px"
        )

    def set_text(self, text: str) -> None:
        """Set the text of the widget.

        Args:
            text (str): The text to set.
        """
        if self.is_html(text):
            self.setHtml(text)
        else:
            self.setPlainText(text)
        self.config.text = text

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
