import subprocess

import qdarktheme
from qtpy.Qsci import QsciScintilla, QsciLexerPython
from qtpy.QtCore import QFile, QTextStream, Signal, QThread
from qtpy.QtGui import QColor, QFont
from qtpy.QtWidgets import (
    QApplication,
    QFileDialog,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


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
    def __init__(self):
        super().__init__()

        # Initialize the editor and terminal
        self.editor = QsciScintilla()
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)

        # Layout
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.editor)
        self.layout.addWidget(self.terminal)
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

        # Enable line numbers in the margin
        self.editor.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
        self.editor.setMarginWidth(0, "0000")  # Adjust the width as needed

        # Additional UI elements like menu for load/save can be added here
        self.setEditorStyle()

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
        self.editor.setPaper(backgroundColor)
        self.editor.setColor(textColor)

        # Syntax Highlighting Colors
        lexer = self.editor.lexer()
        if lexer:
            lexer.setDefaultPaper(backgroundColor)
            lexer.setDefaultColor(textColor)
            lexer.setColor(keywordColor, QsciLexerPython.Keyword)
            lexer.setColor(stringColor, QsciLexerPython.DoubleQuotedString)
            lexer.setColor(stringColor, QsciLexerPython.SingleQuotedString)
            lexer.setColor(commentColor, QsciLexerPython.Comment)
            lexer.setColor(classFunctionColor, QsciLexerPython.ClassName)
            lexer.setColor(classFunctionColor, QsciLexerPython.FunctionMethodName)

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
    from bec_widgets.widgets.toolbar.toolbar import ModularToolBar

    app = QApplication([])
    qdarktheme.setup_theme("auto")

    mainWin = BECEditor()

    toolbar_manual = ModularToolBar()
    toolbar_manual.set_target_widget(mainWin)

    mainWin.layout.insertWidget(0, toolbar_manual)
    mainWin.show()
    app.exec()
