import logging
import platform
import sys

import termqt
from qtpy.QtCore import Qt
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QApplication, QHBoxLayout, QScrollBar, QWidget
from termqt import Terminal


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
        if self.platform in ["Linux", "Darwin"]:
            bin = "/bin/bash"
            from termqt import TerminalPOSIXExecIO

            self.terminal_io = TerminalPOSIXExecIO(
                self.terminal_widget.terminal.row_len,
                self.terminal_widget.terminal.col_len,
                bin,
                logger=self.logger,
            )
        elif self.platform == "Windows":
            bin = "cmd"
            from termqt import TerminalWinptyIO

            self.terminal_io = TerminalWinptyIO(
                self.terminal_widget.terminal.row_len,
                self.terminal_widget.terminal.col_len,
                bin,
                logger=self.logger,
            )
            self.auto_wrap_enabled = False
        else:
            self.logger.error(f"Not supported platform: {self.platform}")
            sys.exit(-1)

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
