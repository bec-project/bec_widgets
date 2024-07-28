# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause

from qtpy.QtDesigner import QPyDesignerCustomWidgetCollection

from bec_widgets.examples.plugin_example_pyside.tictactoe import TicTacToe
from bec_widgets.examples.plugin_example_pyside.tictactoeplugin import TicTacToePlugin

# Set PYSIDE_DESIGNER_PLUGINS to point to this directory and load the plugin


if __name__ == "__main__":  # pragma: no cover
    QPyDesignerCustomWidgetCollection.addCustomWidget(TicTacToePlugin())
