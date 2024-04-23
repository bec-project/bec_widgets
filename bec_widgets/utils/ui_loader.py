from qtpy import QT_VERSION
from qtpy.QtCore import QFile, QIODevice


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
            try:
                from PySide6.QtUiTools import QUiLoader

                self.loader = self.load_ui_pyside6
            except ImportError:
                from PyQt6.uic import loadUi

                self.loader = loadUi

    def load_ui_pyside6(self, ui_file, parent=None):
        """
        Specific loader for PySide6 using QUiLoader.
        Args:
            ui_file(str): Path to the .ui file.
            parent(QWidget): Parent widget.

        Returns:
            QWidget: The loaded widget.
        """
        from PySide6.QtUiTools import QUiLoader

        loader = QUiLoader(parent)
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
