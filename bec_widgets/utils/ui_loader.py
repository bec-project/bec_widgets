from bec_lib.logger import bec_logger
from qtpy import PYSIDE6
from qtpy.QtCore import QFile, QIODevice

from bec_widgets.utils.plugin_utils import get_designer_plugin

logger = bec_logger.logger

if PYSIDE6:
    from qtpy.QtUiTools import QUiLoader

    class CustomUiLoader(QUiLoader):
        def __init__(self, baseinstance):
            super().__init__(baseinstance)
            self.baseinstance = baseinstance

        def createWidget(self, class_name, parent=None, name=""):
            widget = get_designer_plugin(class_name, raise_on_missing=False)
            if widget is not None:
                return widget(self.baseinstance)
            return super().createWidget(class_name, self.baseinstance, name)


class UILoader:
    """Universal UI loader for PyQt6 and PySide6."""

    def __init__(self, parent=None):
        self.parent = parent

        if not PYSIDE6:
            raise ImportError("No compatible Qt bindings found.")
        self.loader = self.load_ui_pyside6

    def load_ui_pyside6(self, ui_file, parent=None):
        """
        Specific loader for PySide6 using QUiLoader.
        Args:
            ui_file(str): Path to the .ui file.
            parent(QWidget): Parent widget.

        Returns:
            QWidget: The loaded widget.
        """
        parent = parent or self.parent
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
