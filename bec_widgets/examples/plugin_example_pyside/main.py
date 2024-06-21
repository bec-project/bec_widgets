# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

"""PySide6 port of the Qt Designer taskmenuextension example from Qt v6.x"""

import sys

from bec_ipython_client.main import BECIPythonClient
from qtpy.QtWidgets import QApplication
from tictactoe import TicTacToe

if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)
    window = TicTacToe()
    window.state = "-X-XO----"
    window.show()
    sys.exit(app.exec())
