"""
BECConsole is a Qt widget that runs a Bash shell. The widget can be used and
embedded like any other Qt widget.

BECConsole is powered by Pyte, a Python based terminal emulator
(https://github.com/selectel/pyte).
"""

import fcntl
import html
import os
import pty
import subprocess
import sys
import threading

import pyte
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QSize, QSocketNotifier, Qt
from qtpy.QtCore import Signal as pyqtSignal
from qtpy.QtCore import Slot as pyqtSlot
from qtpy.QtGui import QClipboard, QTextCursor
from qtpy.QtWidgets import QApplication, QHBoxLayout, QScrollBar, QSizePolicy

ansi_colors = {
    "black": "#000000",
    "red": "#CD0000",
    "green": "#00CD00",
    "brown": "#996633",  # Brown, replacing the yellow
    "blue": "#0000EE",
    "magenta": "#CD00CD",
    "cyan": "#00CDCD",
    "white": "#E5E5E5",
    "brightblack": "#7F7F7F",
    "brightred": "#FF0000",
    "brightgreen": "#00FF00",
    "brightyellow": "#FFFF00",
    "brightblue": "#5C5CFF",
    "brightmagenta": "#FF00FF",
    "brightcyan": "#00FFFF",
    "brightwhite": "#FFFFFF",
}

control_keys_mapping = {
    QtCore.Qt.Key_A: b"\x01",  # Ctrl-A
    QtCore.Qt.Key_B: b"\x02",  # Ctrl-B
    QtCore.Qt.Key_C: b"\x03",  # Ctrl-C
    QtCore.Qt.Key_D: b"\x04",  # Ctrl-D
    QtCore.Qt.Key_E: b"\x05",  # Ctrl-E
    QtCore.Qt.Key_F: b"\x06",  # Ctrl-F
    QtCore.Qt.Key_G: b"\x07",  # Ctrl-G (Bell)
    QtCore.Qt.Key_H: b"\x08",  # Ctrl-H (Backspace)
    QtCore.Qt.Key_I: b"\x09",  # Ctrl-I (Tab)
    QtCore.Qt.Key_J: b"\x0A",  # Ctrl-J (Line Feed)
    QtCore.Qt.Key_K: b"\x0B",  # Ctrl-K (Vertical Tab)
    QtCore.Qt.Key_L: b"\x0C",  # Ctrl-L (Form Feed)
    QtCore.Qt.Key_M: b"\x0D",  # Ctrl-M (Carriage Return)
    QtCore.Qt.Key_N: b"\x0E",  # Ctrl-N
    QtCore.Qt.Key_O: b"\x0F",  # Ctrl-O
    QtCore.Qt.Key_P: b"\x10",  # Ctrl-P
    QtCore.Qt.Key_Q: b"\x11",  # Ctrl-Q
    QtCore.Qt.Key_R: b"\x12",  # Ctrl-R
    QtCore.Qt.Key_S: b"\x13",  # Ctrl-S
    QtCore.Qt.Key_T: b"\x14",  # Ctrl-T
    QtCore.Qt.Key_U: b"\x15",  # Ctrl-U
    QtCore.Qt.Key_V: b"\x16",  # Ctrl-V
    QtCore.Qt.Key_W: b"\x17",  # Ctrl-W
    QtCore.Qt.Key_X: b"\x18",  # Ctrl-X
    QtCore.Qt.Key_Y: b"\x19",  # Ctrl-Y
    QtCore.Qt.Key_Z: b"\x1A",  # Ctrl-Z
    QtCore.Qt.Key_Escape: b"\x1B",  # Ctrl-Escape
    QtCore.Qt.Key_Backslash: b"\x1C",  # Ctrl-\
    QtCore.Qt.Key_Underscore: b"\x1F",  # Ctrl-_
}

normal_keys_mapping = {
    QtCore.Qt.Key_Return: b"\n",
    QtCore.Qt.Key_Space: b" ",
    QtCore.Qt.Key_Enter: b"\n",
    QtCore.Qt.Key_Tab: b"\t",
    QtCore.Qt.Key_Backspace: b"\x08",
    QtCore.Qt.Key_Home: b"\x47",
    QtCore.Qt.Key_End: b"\x4f",
    QtCore.Qt.Key_Left: b"\x02",
    QtCore.Qt.Key_Up: b"\x10",
    QtCore.Qt.Key_Right: b"\x06",
    QtCore.Qt.Key_Down: b"\x0E",
    QtCore.Qt.Key_PageUp: b"\x49",
    QtCore.Qt.Key_PageDown: b"\x51",
    QtCore.Qt.Key_F1: b"\x1b\x31",
    QtCore.Qt.Key_F2: b"\x1b\x32",
    QtCore.Qt.Key_F3: b"\x1b\x33",
    QtCore.Qt.Key_F4: b"\x1b\x34",
    QtCore.Qt.Key_F5: b"\x1b\x35",
    QtCore.Qt.Key_F6: b"\x1b\x36",
    QtCore.Qt.Key_F7: b"\x1b\x37",
    QtCore.Qt.Key_F8: b"\x1b\x38",
    QtCore.Qt.Key_F9: b"\x1b\x39",
    QtCore.Qt.Key_F10: b"\x1b\x30",
    QtCore.Qt.Key_F11: b"\x45",
    QtCore.Qt.Key_F12: b"\x46",
}


def QtKeyToAscii(event):
    """
    Convert the Qt key event to the corresponding ASCII sequence for
    the terminal. This works fine for standard alphanumerical characters, but
    most other characters require terminal specific control sequences.

    The conversion below works for TERM="linux" terminals.
    """
    if sys.platform == "darwin":
        # special case for MacOS
        # /!\ Qt maps ControlModifier to CMD
        # CMD-C, CMD-V for copy/paste
        # CTRL-C and other modifiers -> key mapping
        if event.modifiers() == QtCore.Qt.MetaModifier:
            if event.key() == Qt.Key_Backspace:
                return control_keys_mapping.get(Qt.Key_W)
            return control_keys_mapping.get(event.key())
        elif event.modifiers() == QtCore.Qt.ControlModifier:
            if event.key() == Qt.Key_C:
                # copy
                return "copy"
            elif event.key() == Qt.Key_V:
                # paste
                return "paste"
            return None
        else:
            return normal_keys_mapping.get(event.key(), event.text().encode("utf8"))
    if event.modifiers() == QtCore.Qt.ControlModifier:
        return control_keys_mapping.get(event.key())
    else:
        return normal_keys_mapping.get(event.key(), event.text().encode("utf8"))


class Screen(pyte.HistoryScreen):
    def __init__(self, stdin_fd, numColumns, numLines, historyLength):
        super().__init__(numColumns, numLines, historyLength, ratio=1 / numLines)
        self._fd = stdin_fd

    def write_process_input(self, data):
        """Response to CPR request for example"""
        os.write(self._fd, data.encode("utf-8"))


class Backend(QtCore.QObject):
    """
    Poll Bash.

    This class will run as a qsocketnotifier (started in ``_TerminalWidget``) and poll the
    file descriptor of the Bash terminal.
    """

    # Signals to communicate with ``_TerminalWidget``.
    startWork = pyqtSignal()
    dataReady = pyqtSignal(object)

    def __init__(self, fd, numColumns, numLines):
        super().__init__()

        # File descriptor that connects to Bash process.
        self.fd = fd

        # Setup Pyte (hard coded display size for now).
        self.screen = Screen(self.fd, numColumns, numLines, 10000)
        self.stream = pyte.ByteStream()
        self.stream.attach(self.screen)

        self.notifier = QSocketNotifier(fd, QSocketNotifier.Read)
        self.notifier.activated.connect(self._fd_readable)

    def _fd_readable(self):
        """
        Poll the Bash output, run it through Pyte, and notify the main applet.
        """
        # Read the shell output until the file descriptor is closed.
        try:
            out = os.read(self.fd, 2**16)
        except OSError:
            return

        # Feed output into Pyte's state machine and send the new screen
        # output to the GUI
        self.stream.feed(out)
        self.dataReady.emit(self.screen)


class BECConsole(QtWidgets.QScrollArea):
    """Container widget for the terminal text area"""

    def __init__(self, parent=None, numLines=50, numColumns=125):
        super().__init__(parent)

        self.innerWidget = QtWidgets.QWidget(self)
        QHBoxLayout(self.innerWidget)
        self.innerWidget.layout().setContentsMargins(0, 0, 0, 0)

        self.term = _TerminalWidget(self.innerWidget, numLines, numColumns)
        self.term.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.innerWidget.layout().addWidget(self.term)

        self.scroll_bar = QScrollBar(Qt.Vertical, self.term)
        self.innerWidget.layout().addWidget(self.scroll_bar)

        self.term.set_scroll(self.scroll_bar)

        self.setWidget(self.innerWidget)

    def start(self, cmd=["bec", "--nogui"], deactivate_ctrl_d=True):
        self.term._cmd = cmd
        self.term.start(deactivate_ctrl_d=deactivate_ctrl_d)

    def push(self, text):
        """Push some text to the terminal"""
        return self.term.push(text)


class _TerminalWidget(QtWidgets.QPlainTextEdit):
    """
    Start ``Backend`` process and render Pyte output as text.
    """

    def __init__(self, parent, numColumns, numLines, **kwargs):
        super().__init__(parent)

        # file descriptor to communicate with the subprocess
        self.fd = None
        self.backend = None
        self.lock = threading.Lock()
        # command to execute
        self._cmd = None
        # should ctrl-d be deactivated ? (prevent Python exit)
        self._deactivate_ctrl_d = False

        # Specify the terminal size in terms of lines and columns.
        self.numLines = numLines
        self.numColumns = numColumns
        self.output = [""] * numLines

        # Use Monospace fonts and disable line wrapping.
        self.setFont(QtGui.QFont("Courier", 9))
        self.setFont(QtGui.QFont("Monospace"))
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)

        # Disable vertical scrollbar (we use our own, to be set via .set_scroll())
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        fmt = QtGui.QFontMetrics(self.font())
        self._char_width = fmt.width("w")
        self._char_height = fmt.height()
        self.setCursorWidth(self._char_width)
        # self.setStyleSheet("QPlainTextEdit { color: #ffff00; background-color: #303030; } ");

    def start(self, deactivate_ctrl_d=False):
        self._deactivate_ctrl_d = deactivate_ctrl_d

        # Start the Bash process
        self.fd = self.forkShell()

        # Create the ``Backend`` object
        self.backend = Backend(self.fd, self.numColumns, self.numLines)
        self.backend.dataReady.connect(self.dataReady)

    def minimumSizeHint(self):
        width = self._char_width * self.numColumns
        height = self._char_height * self.numLines
        return QSize(width, height + 20)

    def set_scroll(self, scroll):
        self.scroll = scroll
        self.scroll.setMinimum(0)
        self.scroll.valueChanged.connect(self.scroll_value_change)

    def scroll_value_change(self, value, old={"value": 0}):
        if value <= old["value"]:
            # scroll up
            # value is number of lines from the start
            nlines = old["value"] - value
            # history ratio gives prev_page == 1 line
            for i in range(nlines):
                self.backend.screen.prev_page()
        else:
            # scroll down
            nlines = value - old["value"]
            for i in range(nlines):
                self.backend.screen.next_page()
        old["value"] = value
        self.dataReady(self.backend.screen, reset_scroll=False)

    @pyqtSlot(object)
    def keyPressEvent(self, event):
        """
        Redirect all keystrokes to the terminal process.
        """
        # Convert the Qt key to the correct ASCII code.
        if (
            self._deactivate_ctrl_d
            and event.modifiers() == QtCore.Qt.ControlModifier
            and event.key() == QtCore.Qt.Key_D
        ):
            return None

        code = QtKeyToAscii(event)
        if code == "copy":
            # MacOS only: CMD-C handling
            self.copy()
        elif code == "paste":
            # MacOS only: CMD-V handling
            self._push_clipboard()
        elif code is not None:
            os.write(self.fd, code)

    def push(self, text):
        """
        Write 'text' to terminal
        """
        os.write(self.fd, text.encode("utf-8"))

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        for action in menu.actions():
            # remove all actions except copy and paste
            if "opy" in action.text():
                # redefine text without shortcut
                # since it probably clashes with control codes (like CTRL-C etc)
                action.setText("Copy")
                continue
            if "aste" in action.text():
                # redefine text without shortcut
                action.setText("Paste")
                # paste -> have to insert with self.push
                action.triggered.connect(self._push_clipboard)
                continue
            menu.removeAction(action)
        menu.exec_(event.globalPos())

    def _push_clipboard(self):
        clipboard = QApplication.instance().clipboard()
        self.push(clipboard.text())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            # push primary selection buffer ("mouse clipboard") to terminal
            clipboard = QApplication.instance().clipboard()
            if clipboard.supportsSelection():
                self.push(clipboard.text(QClipboard.Selection))
            return None
        elif event.button() == Qt.LeftButton:
            # left button click
            textCursor = self.textCursor()
            if textCursor.selectedText():
                # mouse was used to select text -> nothing to do
                pass
            else:
                # a simple 'click', make cursor going to end
                textCursor.setPosition(0)
                textCursor.movePosition(
                    QTextCursor.Down, QTextCursor.MoveAnchor, self.backend.screen.cursor.y
                )
                textCursor.movePosition(
                    QTextCursor.Right, QTextCursor.MoveAnchor, self.backend.screen.cursor.x
                )
                self.setTextCursor(textCursor)
                self.ensureCursorVisible()
                return None
        return super().mouseReleaseEvent(event)

    def dataReady(self, screenData, reset_scroll=True):
        """
        Render the new screen as text into the widget.

        This method is triggered via a signal from ``Backend``.
        """
        with self.lock:
            # Clear the widget
            self.clear()

            # Prepare the HTML output
            for line_no in screenData.dirty:
                line = text = ""
                style = old_style = ""
                for ch in screenData.buffer[line_no].values():
                    style = f"{'background-color:%s;' % ansi_colors.get(ch.bg, ansi_colors['black']) if ch.bg!='default' else ''}{'color:%s;' % ansi_colors.get(ch.fg, ansi_colors['white']) if ch.fg!='default' else ''}{'font-weight:bold;' if ch.bold else ''}{'font-style:italic;' if ch.italics else ''}"
                    if style != old_style:
                        if old_style:
                            line += f"<span style={repr(old_style)}>{html.escape(text, quote=True)}</span>"
                        else:
                            line += html.escape(text, quote=True)
                        text = ""
                        old_style = style
                    text += ch.data
                if style:
                    line += f"<span style={repr(style)}>{html.escape(text, quote=True)}</span>"
                else:
                    line += html.escape(text, quote=True)
                self.output[line_no] = line
            # fill the text area with HTML contents in one go
            self.appendHtml(f"<pre>{chr(10).join(self.output)}</pre>")
            # done updates, all clean
            screenData.dirty.clear()

            # Activate cursor
            textCursor = self.textCursor()
            textCursor.setPosition(0)
            textCursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor, screenData.cursor.y)
            textCursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, screenData.cursor.x)
            self.setTextCursor(textCursor)
            self.ensureCursorVisible()

            # manage scroll
            if reset_scroll:
                self.scroll.valueChanged.disconnect(self.scroll_value_change)
                tmp = len(self.backend.screen.history.top) + len(self.backend.screen.history.bottom)
                self.scroll.setMaximum(tmp if tmp > 0 else 0)
                self.scroll.setSliderPosition(len(self.backend.screen.history.top))
                self.scroll.valueChanged.connect(self.scroll_value_change)

    # def resizeEvent(self, event):
    #    with self.lock:
    #        self.numColumns = int(self.width() / self._char_width)
    #        self.numLines = int(self.height() / self._char_height)
    #        self.output = [""] * self.numLines
    #        print("RESIZING TO", self.numColumns, "x", self.numLines)
    #        self.backend.screen.resize(self.numLines, self.numColumns)

    def wheelEvent(self, event):
        y = event.angleDelta().y()
        if y > 0:
            self.backend.screen.prev_page()
        else:
            self.backend.screen.next_page()
        self.dataReady(self.backend.screen, reset_scroll=False)

    def forkShell(self):
        """
        Fork the current process and execute bec in shell.
        """
        try:
            pid, fd = pty.fork()
        except (IOError, OSError):
            return False
        if pid == 0:
            # Safe way to make it work under BSD and Linux
            try:
                ls = os.environ["LANG"].split(".")
            except KeyError:
                ls = []
            if len(ls) < 2:
                ls = ["en_US", "UTF-8"]
            try:
                os.putenv("COLUMNS", str(self.numColumns))
                os.putenv("LINES", str(self.numLines))
                os.putenv("TERM", "linux")
                os.putenv("LANG", ls[0] + ".UTF-8")
                if isinstance(self._cmd, str):
                    os.execvp(self._cmd, self._cmd)
                else:
                    os.execvp(self._cmd[0], self._cmd)
                # print "child_pid", child_pid, sts
            except (IOError, OSError):
                pass
            # self.proc_finish(sid)
            os._exit(0)
        else:
            # We are in the parent process.
            # Set file control
            fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)
            print("Spawned Bash shell (PID {})".format(pid))
            return fd


if __name__ == "__main__":
    import os
    import sys

    from qtpy import QtGui, QtWidgets

    # Terminal size in characters.
    numLines = 25
    numColumns = 100

    # Create the Qt application and QBash instance.
    app = QtWidgets.QApplication([])
    mainwin = QtWidgets.QMainWindow()
    title = "BECConsole ({}x{})".format(numColumns, numLines)
    mainwin.setWindowTitle(title)

    console = BECConsole(mainwin, numColumns, numLines)
    mainwin.setCentralWidget(console)
    console.start()

    # Show widget and launch Qt's event loop.
    mainwin.show()
    sys.exit(app.exec_())
