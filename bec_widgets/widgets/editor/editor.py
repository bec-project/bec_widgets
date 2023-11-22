import subprocess

import qdarktheme
from jedi import Script
from jedi.api import Completion

# pylint: disable=no-name-in-module
from qtpy.Qsci import QsciScintilla, QsciLexerPython, QsciAPIs
from qtpy.QtCore import Qt
from qtpy.QtCore import Signal, QThread
from qtpy.QtGui import QColor, QFont
from qtpy.QtWidgets import (
    QApplication,
    QFileDialog,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qtpy.QtWidgets import QSplitter
from qtconsole.manager import QtKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget

from bec_widgets.widgets import ModularToolBar


class AutoCompleter(QThread):
    """Initializes the AutoCompleter thread for handling autocompletion and signature help.

    Args:
        file_path (str): The path to the file for which autocompletion is required.
        api (QsciAPIs): The QScintilla API instance used for managing autocompletions.
        enable_docstring (bool, optional): Flag to determine if docstrings should be included in the signatures.
    """

    def __init__(self, file_path: str, api: QsciAPIs, enable_docstring: bool = False):
        super().__init__(None)
        self.file_path = file_path
        self.script: Script = None
        self.api: QsciAPIs = api
        self.completions: list[Completion] = None
        self.line = 0
        self.index = 0
        self.text = ""

        # TODO so far disabled, quite buggy, docstring extraction has to be generalised
        self.enable_docstring = enable_docstring

    def update_script(self, text: str):
        """Updates the script for Jedi completion based on the current editor text.

        Args:
            text (str): The current text of the editor.
        """
        if self.script is None or self.script.path != text:
            self.script = Script(text, path=self.file_path)

    def run(self):
        """Runs the thread for generating autocompletions. Overrides QThread.run."""
        self.update_script(self.text)
        try:
            self.completions = self.script.complete(self.line, self.index)
            self.load_autocomplete(self.completions)
        except Exception as err:
            print(err)
        self.finished.emit()

    def get_function_signature(self, line: int, index: int, text: str) -> str:
        """Fetches the function signature for a given position in the text.

        Args:
            line (int): The line number in the editor.
            index (int): The index (column number) in the line.
            text (str): The current text of the editor.

        Returns:
            str: A string containing the function signature or an empty string if not available.
        """
        self.update_script(text)
        try:
            signatures = self.script.get_signatures(line, index)
            if signatures and self.enable_docstring is True:
                full_docstring = signatures[0].docstring(raw=True)
                compact_docstring = self.get_compact_docstring(full_docstring)
                return compact_docstring
            if signatures and self.enable_docstring is False:
                return signatures[0].to_string()
        except Exception as err:
            print(f"Signature Error:{err}")
        return ""

    def load_autocomplete(self, completions: list):
        """Loads the autocomplete suggestions into the QScintilla API.

        Args:
            completions (list[Completion]): A list of Completion objects to be added to the API.
        """
        self.api.clear()
        for i in completions:
            self.api.add(i.name)
        self.api.prepare()

    def get_completions(self, line: int, index: int, text: str):
        """Starts the autocompletion process for a given position in the text.

        Args:
            line (int): The line number in the editor.
            index (int): The index (column number) in the line.
            text (str): The current text of the editor.
        """
        self.line = line
        self.index = index
        self.text = text
        self.start()

    def get_compact_docstring(self, full_docstring):
        """Generates a compact version of a function's docstring.

        Args:
            full_docstring (str): The full docstring of a function.

        Returns:
            str: A compact version of the docstring.
        """
        lines = full_docstring.split("\n")
        # TODO make it also for different docstring styles, now it is only for numpy style
        cutoff_indices = [
            i
            for i, line in enumerate(lines)
            if line.strip().lower() in ["parameters", "returns", "examples", "see also", "warnings"]
        ]

        if cutoff_indices:
            lines = lines[: cutoff_indices[0]]

        compact_docstring = "\n".join(lines).strip()
        return compact_docstring


class ScriptRunnerThread(QThread):
    """Initializes the thread for running a Python script.

    Args:
        script (str): The script to be executed.
    """

    outputSignal = Signal(str)

    def __init__(self, script):
        super().__init__()
        self.script = script

    def run(self):
        """Executes the script in a subprocess and emits output through a signal. Overrides QThread.run."""
        process = subprocess.Popen(
            ["python", "-u", "-c", self.script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True,
            text=True,
        )

        while True:
            output = process.stdout.readline()
            if output == "" and process.poll() is not None:
                break
            if output:
                self.outputSignal.emit(output)
        error = process.communicate()[1]
        if error:
            self.outputSignal.emit(error)


class BECEditor(QWidget):
    """Initializes the BEC Editor widget.

    Args:
        toolbar_enabled (bool, optional): Determines if the toolbar should be enabled. Defaults to True.
    """

    def __init__(
        self, toolbar_enabled=True, jupyter_terminal_enabled=False, docstring_tooltip=False
    ):
        super().__init__()

        self.script_runner_thread = None
        self.file_path = None
        self.docstring_tooltip = docstring_tooltip
        self.jupyter_terminal_enabled = jupyter_terminal_enabled
        # TODO just temporary solution, could be extended to other languages
        self.is_python_file = True

        # Initialize the editor and terminal
        self.editor = QsciScintilla()
        if self.jupyter_terminal_enabled:
            self.terminal = self.make_jupyter_widget_with_kernel()
        else:
            self.terminal = QTextEdit()
            self.terminal.setReadOnly(True)

        # Layout
        self.layout = QVBoxLayout()

        # Initialize and add the toolbar if enabled
        if toolbar_enabled:
            self.toolbar = ModularToolBar(self)
            self.layout.addWidget(self.toolbar)

        # Initialize the splitter
        self.splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.splitter.addWidget(self.editor)
        self.splitter.addWidget(self.terminal)
        self.splitter.setSizes([400, 200])

        # Add Splitter to layout
        self.layout.addWidget(self.splitter)
        self.setLayout(self.layout)

        self.setup_editor()

    def setup_editor(self):
        """Sets up the editor with necessary configurations like lexer, auto indentation, and line numbers."""
        # Set the lexer for Python
        self.lexer = QsciLexerPython()
        self.editor.setLexer(self.lexer)

        # Enable auto indentation and competition within the editor
        self.editor.setAutoIndent(True)
        self.editor.setIndentationsUseTabs(False)
        self.editor.setIndentationWidth(4)
        self.editor.setAutoCompletionSource(QsciScintilla.AutoCompletionSource.AcsAll)
        self.editor.setAutoCompletionThreshold(1)

        # Autocomplete for python file
        # Connect cursor position change signal for autocompletion
        self.editor.cursorPositionChanged.connect(self.on_cursor_position_changed)

        # if self.is_python_file: #TODO can be changed depending on supported languages
        self.__api = QsciAPIs(self.lexer)
        self.auto_completer = AutoCompleter(
            self.editor.text(), self.__api, enable_docstring=self.docstring_tooltip
        )
        self.auto_completer.finished.connect(self.loaded_autocomplete)

        # Enable line numbers in the margin
        self.editor.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
        self.editor.setMarginWidth(0, "0000")  # Adjust the width as needed

        # Additional UI elements like menu for load/save can be added here
        self.set_editor_style()

    @staticmethod
    def make_jupyter_widget_with_kernel() -> object:
        """Start a kernel, connect to it, and create a RichJupyterWidget to use it"""
        kernel_manager = QtKernelManager(kernel_name="python3")
        kernel_manager.start_kernel()

        kernel_client = kernel_manager.client()
        kernel_client.start_channels()

        jupyter_widget = RichJupyterWidget()
        jupyter_widget.set_default_style("linux")
        jupyter_widget.kernel_manager = kernel_manager
        jupyter_widget.kernel_client = kernel_client
        return jupyter_widget

    def show_call_tip(self, position):
        """Shows a call tip at the given position in the editor.

        Args:
            position (int): The position in the editor where the call tip should be shown.
        """
        line, index = self.editor.lineIndexFromPosition(position)
        signature = self.auto_completer.get_function_signature(line + 1, index, self.editor.text())
        if signature:
            self.editor.showUserList(1, [signature])

    def on_cursor_position_changed(self, line, index):
        """Handles the event of cursor position change in the editor.

        Args:
            line (int): The current line number where the cursor is.
            index (int): The current column index where the cursor is.
        """
        # if self.is_python_file: #TODO can be changed depending on supported languages
        # Get completions
        self.auto_completer.get_completions(line + 1, index, self.editor.text())
        self.editor.autoCompleteFromAPIs()

        # Show call tip - signature
        position = self.editor.positionFromLineIndex(line, index)
        self.show_call_tip(position)

    def loaded_autocomplete(self):
        """Placeholder method for actions after autocompletion data is loaded."""

    def set_editor_style(self):
        """Sets the style and color scheme for the editor."""
        # Dracula Theme Colors
        background_color = QColor("#282a36")
        text_color = QColor("#f8f8f2")
        keyword_color = QColor("#8be9fd")
        string_color = QColor("#f1fa8c")
        comment_color = QColor("#6272a4")
        class_function_color = QColor("#50fa7b")

        # Set Font
        font = QFont()
        font.setFamily("Consolas")
        font.setPointSize(10)
        self.editor.setFont(font)
        self.editor.setMarginsFont(font)

        # Set Editor Colors
        self.editor.setMarginsBackgroundColor(background_color)
        self.editor.setMarginsForegroundColor(text_color)
        self.editor.setCaretForegroundColor(text_color)
        self.editor.setCaretLineBackgroundColor(QColor("#44475a"))
        self.editor.setPaper(background_color)  # Set the background color for the entire paper
        self.editor.setColor(text_color)

        # Set editor
        # Syntax Highlighting Colors
        lexer = self.editor.lexer()
        if lexer:
            lexer.setDefaultPaper(background_color)  # Set the background color for the text area
            lexer.setDefaultColor(text_color)
            lexer.setColor(keyword_color, QsciLexerPython.Keyword)
            lexer.setColor(string_color, QsciLexerPython.DoubleQuotedString)
            lexer.setColor(string_color, QsciLexerPython.SingleQuotedString)
            lexer.setColor(comment_color, QsciLexerPython.Comment)
            lexer.setColor(class_function_color, QsciLexerPython.ClassName)
            lexer.setColor(class_function_color, QsciLexerPython.FunctionMethodName)

        # Set the style for all text to have a transparent background
        # TODO find better way how to do it!
        for style in range(
            128
        ):  # QsciScintilla supports 128 styles by default, this set all to transparent background
            self.lexer.setPaper(background_color, style)

    def run_script(self):
        """Runs the current script in the editor."""
        if self.jupyter_terminal_enabled:
            script = self.editor.text()
            self.terminal.execute(script)

        else:
            script = self.editor.text()
            self.script_runner_thread = ScriptRunnerThread(script)
            self.script_runner_thread.outputSignal.connect(self.update_terminal)
            self.script_runner_thread.start()

    def update_terminal(self, text):
        """Updates the terminal with new text.

        Args:
            text (str): The text to be appended to the terminal.
        """
        self.terminal.append(text)

    def enable_docstring_tooltip(self):
        """Enables the docstring tooltip."""
        self.docstring_tooltip = True
        self.auto_completer.enable_docstring = True

    def open_file(self):
        """Opens a file dialog for selecting and opening a Python file in the editor."""
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open file", "", "Python files (*.py);;All Files (*)", options=options
        )

        if not file_path:
            return
        try:
            with open(file_path, "r") as file:
                text = file.read()
            self.editor.setText(text)
        except FileNotFoundError:
            print(f"The file {file_path} was not found.")
        except Exception as e:
            print(f"An error occurred while opening the file {file_path}: {e}")

    def save_file(self):
        """Opens a save file dialog for saving the current script in the editor."""
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save file", "", "Python files (*.py);;All Files (*)", options=options
        )

        if not file_path:
            return
        try:
            if not file_path.endswith(".py"):
                file_path += ".py"

            with open(file_path, "w") as file:
                text = self.editor.text()
                file.write(text)
                print(f"File saved to {file_path}")
        except Exception as e:
            print(f"An error occurred while saving the file to {file_path}: {e}")


if __name__ == "__main__":  # pragma: no cover
    app = QApplication([])
    qdarktheme.setup_theme("auto")

    mainWin = BECEditor(jupyter_terminal_enabled=True)

    mainWin.show()
    app.exec()
