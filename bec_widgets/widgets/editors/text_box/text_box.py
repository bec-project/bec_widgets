"""Module for a text box widget that displays text in plain and HTML format and adheres to the BECWidget interface & style."""

import re
from html.parser import HTMLParser

from bec_lib.logger import bec_logger
from pydantic import Field
from qtpy.QtCore import Property, Slot
from qtpy.QtWidgets import QTextEdit, QVBoxLayout, QWidget

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget

logger = bec_logger.logger

DEFAULT_TEXT = "<h1>Welcome to the BEC Widget TextBox</h1><p>A widget that allows user to display text in plain and HTML format.</p><p>This is an example of displaying HTML text.</p>"


class TextBoxConfig(ConnectionConfig):
    """Configuration for the TextBox widget.

    Args:
        text (str, optional): The text to display in the widget. Defaults to None.
        is_html (bool, optional): Whether the text is in HTML format or not. Defaults to False.
    """

    text: str | None = Field(None, description="The text to display in the widget.")
    is_html: bool = Field(False, description="Whether the text is in HTML format or not.")


class TextBox(BECWidget, QWidget):
    """A widget that displays text in plain and HTML format

    Args:
        parent (QWidget, optional): The parent widget. Defaults to None.
        client ([type], optional): The client to use. Defaults to None.
        config ([type], optional): The config to use. Defaults to None.
        gui_id ([type], optional): The gui_id to use. Defaults to None.
    """

    PLUGIN = True
    USER_ACCESS = ["set_plain_text", "set_html_text"]
    ICON_NAME = "chat"

    def __init__(self, parent=None, client=None, config=None, gui_id=None):
        if config is None:
            config = TextBoxConfig(widget_class=self.__class__.__name__)
        else:
            if isinstance(config, dict):
                config = TextBoxConfig(**config)
            self.config = config
        super().__init__(client=client, config=config, gui_id=gui_id)
        QWidget.__init__(self, parent)
        self.layout = QVBoxLayout(self)
        self.text_box_text_edit = QTextEdit(parent=self)
        self.layout.addWidget(self.text_box_text_edit)
        self.setLayout(self.layout)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.config = config
        self.text_box_text_edit.setReadOnly(True)
        if self.config.text is not None:
            if self.config.is_html:
                self.set_html_text(self.config.text)
            else:
                self.set_plain_text(self.config.text)
        else:
            self.set_html_text(DEFAULT_TEXT)

    @Slot(str)
    def set_plain_text(self, text: str) -> None:
        """Set the plain text of the widget.

        Args:
            text (str): The text to set.
        """
        self.text_box_text_edit.setPlainText(text)
        self.config.text = text
        self.config.is_html = False

    @Slot(str)
    def set_html_text(self, text: str) -> None:
        """Set the HTML text of the widget.

        Args:
            text (str): The text to set.
        """
        self.text_box_text_edit.setHtml(text)
        self.config.text = text
        self.config.is_html = True

    @Property(str)
    def plain_text(self) -> str:
        """Get the text of the widget.

        Returns:
            str: The text of the widget.
        """
        return self.text_box_text_edit.toPlainText()

    @plain_text.setter
    def plain_text(self, text: str) -> None:
        """Set the text of the widget.

        Args:
            text (str): The text to set.
        """
        self.set_plain_text(text)

    @Property(str)
    def html_text(self) -> str:
        """Get the HTML text of the widget.

        Returns:
            str: The HTML text of the widget.
        """
        return self.text_box_text_edit.toHtml()

    @html_text.setter
    def html_text(self, text: str) -> None:
        """Set the HTML text of the widget.

        Args:
            text (str): The HTML text to set.
        """
        self.set_html_text(text)


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = TextBox()
    widget.show()
    sys.exit(app.exec())
