import subprocess

import qdarktheme
from PyQt6.QtCore import QFile, QTextStream, pyqtSignal, QThread
from PyQt6.QtGui import QColor, QFont, QAction, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QFileDialog,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt6.Qsci import QsciScintilla, QsciLexerPython


class ScriptRunnerThread(QThread):
    outputSignal = pyqtSignal(str)

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
        self.runButton = QPushButton("Run Script")

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.editor)
        layout.addWidget(self.runButton)
        layout.addWidget(self.terminal)
        self.setLayout(layout)

        self.setupEditor()

        # Connect the run button
        self.runButton.clicked.connect(self.runScript)

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
        self.createActions()
        self.createMenus()

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

    def createMenus(self):
        ...
        # self.fileMenu = self.menuBar().addMenu("&File")
        # self.fileMenu.addAction(self.openAct)
        # self.fileMenu.addAction(self.saveAct)

    def createActions(self):
        self.openAct = QAction("&Open...", self, triggered=self.openFile)
        self.saveAct = QAction("&Save", self, triggered=self.saveFile)

        # Shortcuts
        self.openShortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        self.openShortcut.activated.connect(self.openFile)

        self.saveShortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.saveShortcut.activated.connect(self.saveFile)

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
