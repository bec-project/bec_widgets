import logging
import os
import platform
import sys

import termqt
from qtpy.QtCore import QSocketNotifier, Qt
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QApplication, QHBoxLayout, QScrollBar, QWidget
from termqt import Terminal

try:
    from qtpy.QtCore import pyqtRemoveInputHook

    pyqtRemoveInputHook()
except ImportError:
    pass

if platform.system() in ["Linux", "Darwin"]:
    terminal_cmd = os.environ["SHELL"]

    from termqt import TerminalPOSIXExecIO

    class TerminalExecIO(TerminalPOSIXExecIO):
        def _read_loop(self):
            pass

        def find_utf8_split(self, data):
            """UTF-8 characters can be 1-4 bytes long, this finds first index which is not mid character

            Character lengths include:
              1 Bytes: 0xxxxxxx
              2 Bytes: 110xxxxx 10xxxxxx
              3 Bytes: 1110xxxx 10xxxxxx 10xxxxxx
              4 bytes: 11110xxx 10xxxxxx 10xxxxxx 10xxxxxx
              Source: https://en.wikipedia.org/wiki/UTF-8#Encoding

            Start at end of chunk moving backwards, find first UTF-8 start byte:
              1 Bytes: 0xxxxxxx - 0x80 == 0x00
              2 Bytes: 110xxxxx - 0xE0 == 0xC0
              3 Bytes: 1110xxxx - 0xF0 == 0xE0
              4 bytes: 11110xxx - 0xF8 == 0xF0

            Parameters:
              data (bytes) - buffer to be evaluated

            Returns:
              (int) - last position of complete UTF-8 character
            """
            pos = 0
            for i, c in enumerate(reversed(data)):
                if c & 0x80 == 0x00 or c & 0xE0 == 0xC0 or c & 0xF0 == 0xE0 or c & 0xF8 == 0xF0:
                    pos = i
                    break
            return len(data) - pos

        def _read(self, fd):
            try:
                data = os.read(fd, 2**16)  # read as much as possible
            except OSError:
                data = b""

            if data:
                self._read_buf += data
                i = self.find_utf8_split(self._read_buf)
                output = self._read_buf[:i]
                self._read_buf = self._read_buf[i:]
                self.stdout_callback(output)
            else:
                self.logger.info("Spawned process has been killed")
                if self.running:
                    self.running = False
                    self.terminated_callback()
                    os.close(fd)

        def spawn(self):
            super().spawn()
            self._read_notifier = QSocketNotifier(self.fd, QSocketNotifier.Read)
            self._read_notifier.activated.connect(self._read)

        def write(self, buffer):
            # same as original method, but without logging and without assert (unneeded)
            if not self.running:
                return
            try:
                os.write(self.fd, buffer)
            except OSError:
                self.running = False
                self.terminated_callback()

else:
    terminal_cmd = "cmd.exe"
    from termqt import TerminalWinptyIO as TerminalExecIO


class TerminalWidget(QWidget):
    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        self.terminal = Terminal(800, 600, logger=self.logger)
        self.terminal.set_font()
        self.terminal.maximum_line_history = 2000
        self.scroll = QScrollBar(Qt.Vertical, self.terminal)
        self.terminal.connect_scroll_bar(self.scroll)

        layout = QHBoxLayout()
        layout.addWidget(self.terminal)
        layout.addWidget(self.scroll)
        layout.setSpacing(0)
        self.setLayout(layout)


class BECConsole(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"termqt on {platform.system()}")
        self.logger = self.setup_logger()

        self.terminal_widget = TerminalWidget(self.logger)

        layout = QHBoxLayout()
        layout.addWidget(self.terminal_widget)
        self.setLayout(layout)

        self.auto_wrap_enabled = True
        self.platform = platform.system()

        self.setup_terminal_io()

    def setup_logger(self):
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(asctime)s] > [%(filename)s:%(lineno)d] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def setup_terminal_io(self):
        self.terminal_io = TerminalExecIO(
            self.terminal_widget.terminal.row_len,
            self.terminal_widget.terminal.col_len,
            terminal_cmd,
            logger=self.logger,
        )
        self.auto_wrap_enabled = False

        self.terminal_widget.terminal.enable_auto_wrap(self.auto_wrap_enabled)
        self.terminal_io.stdout_callback = self.terminal_widget.terminal.stdout
        self.terminal_widget.terminal.stdin_callback = self.terminal_io.write
        self.terminal_widget.terminal.resize_callback = self.terminal_io.resize
        self.terminal_io.spawn()


if __name__ == "__main__":
    app = QApplication([])
    main_window = BECConsole()
    main_window.show()
    sys.exit(app.exec())
