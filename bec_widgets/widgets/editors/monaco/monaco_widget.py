from typing import Literal

import qtmonaco
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_theme_name


class MonacoWidget(BECWidget, QWidget):
    """
    A simple Monaco editor widget
    """

    PLUGIN = True
    ICON_NAME = "code"
    USER_ACCESS = [
        "set_text",
        "get_text",
        "set_language",
        "get_language",
        "set_theme",
        "get_theme",
        "set_readonly",
        "set_cursor",
        "current_cursor",
        "set_minimap_enabled",
    ]

    def __init__(self, parent=None, config=None, client=None, gui_id=None, **kwargs):
        super().__init__(
            parent=parent, client=client, gui_id=gui_id, config=config, theme_update=True, **kwargs
        )
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.editor = qtmonaco.Monaco(self)
        layout.addWidget(self.editor)
        self.setLayout(layout)
        self.editor.initialized.connect(self.apply_theme)

    def apply_theme(self, theme: str | None = None) -> None:
        """
        Apply the current theme to the Monaco editor.

        Args:
            theme (str, optional): The theme to apply. If None, the current theme will be used.
        """
        if theme is None:
            theme = get_theme_name()
        editor_theme = "vs" if theme == "light" else "vs-dark"
        self.set_theme(editor_theme)

    def set_text(self, text: str) -> None:
        """
        Set the text in the Monaco editor.

        Args:
            text (str): The text to set in the editor.
        """
        self.editor.set_text(text)

    def get_text(self) -> str:
        """
        Get the current text from the Monaco editor.
        """
        return self.editor.get_text()

    def set_cursor(
        self,
        line: int,
        column: int = 1,
        move_to_position: Literal[None, "center", "top", "position"] = None,
    ) -> None:
        """
        Set the cursor position in the Monaco editor.

        Args:
            line (int): Line number (1-based).
            column (int): Column number (1-based), defaults to 1.
            move_to_position (Literal[None, "center", "top", "position"], optional): Position to move the cursor to.
        """
        self.editor.set_cursor(line, column, move_to_position)

    def current_cursor(self) -> dict[str, int]:
        """
        Get the current cursor position in the Monaco editor.

        Returns:
            dict[str, int]: A dictionary with keys 'line' and 'column' representing the cursor position.
        """
        return self.editor.current_cursor

    def set_language(self, language: str) -> None:
        """
        Set the programming language for syntax highlighting in the Monaco editor.

        Args:
            language (str): The programming language to set (e.g., "python", "javascript").
        """
        self.editor.set_language(language)

    def get_language(self) -> str:
        """
        Get the current programming language set in the Monaco editor.
        """
        return self.editor.get_language()

    def set_readonly(self, read_only: bool) -> None:
        """
        Set the Monaco editor to read-only mode.

        Args:
            read_only (bool): If True, the editor will be read-only.
        """
        self.editor.set_readonly(read_only)

    def set_theme(self, theme: str) -> None:
        """
        Set the theme for the Monaco editor.

        Args:
            theme (str): The theme to set (e.g., "vs-dark", "light").
        """
        self.editor.set_theme(theme)

    def get_theme(self) -> str:
        """
        Get the current theme of the Monaco editor.
        """
        return self.editor.get_theme()

    def set_minimap_enabled(self, enabled: bool) -> None:
        """
        Enable or disable the minimap in the Monaco editor.

        Args:
            enabled (bool): If True, the minimap will be enabled; otherwise, it will be disabled.
        """
        self.editor.set_minimap_enabled(enabled)

    def set_highlighted_lines(self, start_line: int, end_line: int) -> None:
        """
        Highlight a range of lines in the Monaco editor.

        Args:
            start_line (int): The starting line number (1-based).
            end_line (int): The ending line number (1-based).
        """
        self.editor.set_highlighted_lines(start_line, end_line)

    def clear_highlighted_lines(self) -> None:
        """
        Clear any highlighted lines in the Monaco editor.
        """
        self.editor.clear_highlighted_lines()


if __name__ == "__main__":  # pragma: no cover
    qapp = QApplication([])
    widget = MonacoWidget()
    # set the default size
    widget.resize(800, 600)
    widget.set_language("python")
    widget.set_theme("vs-dark")
    widget.editor.set_minimap_enabled(False)
    widget.set_text(
        """
import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bec_lib.devicemanager import DeviceContainer
    from bec_lib.scans import Scans
    dev: DeviceContainer
    scans: Scans

#######################################
########## User Script #####################
#######################################

# This is a comment
def hello_world():
    print("Hello, world!")
            """
    )
    widget.set_highlighted_lines(1, 3)
    widget.show()
    qapp.exec_()
