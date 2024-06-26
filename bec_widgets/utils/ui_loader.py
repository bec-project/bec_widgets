from qtpy import PYQT6, PYSIDE6, QT_VERSION
from qtpy.QtCore import QFile, QIODevice

if PYSIDE6:
    from PySide6.QtUiTools import QUiLoader

    from bec_widgets.examples.plugin_example_pyside.tictactoe import TicTacToe
    from bec_widgets.utils.plugin_utils import get_rpc_classes

    class CustomUiLoader(QUiLoader):
        def __init__(self, baseinstance):
            super().__init__(baseinstance)
            widgets = get_rpc_classes("bec_widgets").get("top_level_classes", [])

            # remove this line once the plugin is not needed anymore
            widgets.append(TicTacToe)

            self.custom_widgets = {widget.__name__: widget for widget in widgets}

            self.baseinstance = baseinstance

        def createWidget(self, class_name, parent=None, name=""):
            if class_name in self.custom_widgets:
                widget = self.custom_widgets[class_name](parent)
                widget.setObjectName(name)
                return widget
            return super().createWidget(class_name, parent, name)


class UILoader:
    """Universal UI loader for PyQt5, PyQt6, PySide2, and PySide6."""

    def __init__(self, parent=None):
        self.parent = parent
        if QT_VERSION.startswith("5"):
            # PyQt5 or PySide2
            from qtpy import uic

            self.loader = uic.loadUi
        elif QT_VERSION.startswith("6"):
            # PyQt6 or PySide6
            if PYSIDE6:
                self.loader = self.load_ui_pyside6
            elif PYQT6:
                from PyQt6.uic import loadUi

                self.loader = loadUi
            else:
                raise ImportError("No compatible Qt bindings found.")

    def load_ui_pyside6(self, ui_file, parent=None):
        """
        Specific loader for PySide6 using QUiLoader.
        Args:
            ui_file(str): Path to the .ui file.
            parent(QWidget): Parent widget.

        Returns:
            QWidget: The loaded widget.
        """

        loader = CustomUiLoader(parent)
        file = QFile(ui_file)
        if not file.open(QIODevice.ReadOnly):
            raise IOError(f"Cannot open file: {ui_file}")
        widget = loader.load(file, parent)
        file.close()
        return widget

    def load_ui(self, ui_file, parent=None):
        """
        Universal UI loader method.
        Args:
            ui_file(str): Path to the .ui file.
            parent(QWidget): Parent widget.

        Returns:
            QWidget: The loaded widget.
        """
        if parent is None:
            parent = self.parent
        return self.loader(ui_file, parent)
