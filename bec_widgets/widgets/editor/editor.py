import subprocess
import qdarktheme
from PyQt6.QtGui import QKeyEvent

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QSplitter
from qtpy.Qsci import QsciScintilla, QsciLexerPython, QsciAPIs
from qtpy.QtCore import QFile, QTextStream, Signal, QThread
from qtpy.QtGui import QColor, QFont
from qtpy.QtWidgets import (
    QApplication,
    QFileDialog,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from jedi import Script
from jedi.api import Completion

from bec_widgets.widgets import ModularToolBar


class AutoCompleter(QThread):
    def __init__(self, file_path, api):
        super(AutoCompleter, self).__init__(None)
        self.file_path = file_path
        self.script: Script = None
        self.api: QsciAPIs = api
        self.completions: list[Completion] = None
        self.line = 0
        self.index = 0
        self.text = ""

    def run(self):
        try:
            self.script = Script(self.text, path=self.file_path)
            self.completions = self.script.complete(self.line, self.index)
            self.load_autocomplete(self.completions)
        except Exception as err:
            print(err)

        self.finished.emit()

    def load_autocomplete(self, completions):
        self.api.clear()
        [self.api.add(i.name) for i in completions]
        self.api.prepare()

    def get_completions(self, line: int, index: int, text: str):
        self.line = line
        self.index = index
        self.text = text
        self.start()


class ScriptRunnerThread(QThread):
    outputSignal = Signal(str)

    def __init__(self, script):
        super().__init__()
        self.script = script

    def run(self):
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
    def __init__(self, toolbar_enabled=True):
        super().__init__()

        # Flag to check if the file is a python file #TODO just temporary solution, could be extended to other languages
        self.is_python_file = True

        # Initialize the editor and terminal
        self.editor = QsciScintilla()
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
        # self.splitter.setSizes([400, 100]) #TODO optional to set sizes

        # Add Splitter to layout
        self.layout.addWidget(self.splitter)
        self.setLayout(self.layout)

        self.setupEditor()

    def setupEditor(self):
        # Set the lexer for Python
        self.lexer = QsciLexerPython()
        self.editor.setLexer(self.lexer)

        # Enable features
        self.editor.setAutoIndent(True)
        self.editor.setIndentationsUseTabs(False)
        self.editor.setIndentationWidth(4)
        self.editor.setAutoCompletionSource(QsciScintilla.AutoCompletionSource.AcsAll)
        self.editor.setAutoCompletionThreshold(1)

        # Autocomplete for python file
        # Connect cursor position change signal for autocompletion
        self.editor.cursorPositionChanged.connect(self.onCursorPositionChanged)

        # if self.is_python_file: #TODO can be changed depending on supported languages
        self.__api = QsciAPIs(self.lexer)
        self.auto_completer = AutoCompleter(self.editor.text(), self.__api)
        self.auto_completer.finished.connect(self.loaded_autocomplete)

        # Enable line numbers in the margin
        self.editor.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
        self.editor.setMarginWidth(0, "0000")  # Adjust the width as needed

        # Additional UI elements like menu for load/save can be added here
        self.setEditorStyle()

    def onCursorPositionChanged(self, line, index):
        # if self.is_python_file: #TODO can be changed depending on supported languages
        self.auto_completer.get_completions(line + 1, index, self.editor.text())
        self.editor.autoCompleteFromAPIs()

    def loaded_autocomplete(self):
        # Placeholder for any action after autocompletion data is loaded
        pass

    def setEditorStyle(self):
        # Dracula Theme Colors
        backgroundColor = QColor("#282a36")
        textColor = QColor("#f8f8f2")
        keywordColor = QColor("#8be9fd")
        stringColor = QColor("#f1fa8c")
        commentColor = QColor("#6272a4")
        classFunctionColor = QColor("#50fa7b")

        # Set Font
        font = QFont()
        font.setFamily("Consolas")
        font.setPointSize(10)
        self.editor.setFont(font)
        self.editor.setMarginsFont(font)

        # Set Editor Colors
        self.editor.setMarginsBackgroundColor(backgroundColor)
        self.editor.setMarginsForegroundColor(textColor)
        self.editor.setCaretForegroundColor(textColor)
        self.editor.setCaretLineBackgroundColor(QColor("#44475a"))
        self.editor.setPaper(backgroundColor)  # Set the background color for the entire paper
        self.editor.setColor(textColor)
        #
        # Syntax Highlighting Colors
        lexer = self.editor.lexer()
        if lexer:
            lexer.setDefaultPaper(backgroundColor)  # Set the background color for the text area
            lexer.setDefaultColor(textColor)
            lexer.setColor(keywordColor, QsciLexerPython.Keyword)
            lexer.setColor(stringColor, QsciLexerPython.DoubleQuotedString)
            lexer.setColor(stringColor, QsciLexerPython.SingleQuotedString)
            lexer.setColor(commentColor, QsciLexerPython.Comment)
            lexer.setColor(classFunctionColor, QsciLexerPython.ClassName)
            lexer.setColor(classFunctionColor, QsciLexerPython.FunctionMethodName)

        # Set the style for all text to have a transparent background
        # TODO find better way how to do it!
        for style in range(
            128
        ):  # QsciScintilla supports 128 styles by default, this set all to transpatrent background
            self.lexer.setPaper(backgroundColor, style)

    def runScript(self):
        script = self.editor.text()
        self.scriptRunnerThread = ScriptRunnerThread(script)
        self.scriptRunnerThread.outputSignal.connect(self.updateTerminal)
        self.scriptRunnerThread.start()

    def updateTerminal(self, text):
        self.terminal.append(text)

    def openFile(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open file", "", "Python files (*.py)")
        if path:
            file = QFile(path)
            if file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
                text = QTextStream(file).readAll()
                self.editor.setText(text)
                file.close()

    def saveFile(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save file", "", "Python files (*.py)")
        if path:
            file = QFile(path)
            if file.open(QFile.OpenModeFlag.WriteOnly | QFile.OpenModeFlag.Text):
                text = self.editor.text()
                QTextStream(file) << text
                file.close()


if __name__ == "__main__":
    app = QApplication([])
    qdarktheme.setup_theme("auto")

    mainWin = BECEditor()

    mainWin.show()
    app.exec()
