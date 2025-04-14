import inspect

from bec_lib.logger import bec_logger
from qtpy import PYQT6, PYSIDE6, QT_VERSION
from qtpy.QtCore import QFile, QIODevice

from bec_widgets.utils.generate_designer_plugin import DesignerPluginInfo
from bec_widgets.utils.plugin_utils import get_custom_classes

logger = bec_logger.logger

if PYSIDE6:
    from PySide6.QtUiTools import QUiLoader

    class CustomUiLoader(QUiLoader):
        def __init__(self, baseinstance, custom_widgets: dict = None):
            super().__init__(baseinstance)
            self.custom_widgets = custom_widgets or {}

            self.baseinstance = baseinstance

        def createWidget(self, class_name, parent=None, name=""):
            if class_name in self.custom_widgets:
                widget = self.custom_widgets[class_name](self.baseinstance)
                return widget
            return super().createWidget(class_name, self.baseinstance, name)


class UILoader:
    """Universal UI loader for PyQt6 and PySide6."""

    def __init__(self, parent=None):
        self.parent = parent

        widgets = get_custom_classes("bec_widgets").classes

        self.custom_widgets = {widget.__name__: widget for widget in widgets}

        if PYSIDE6:
            self.loader = self.load_ui_pyside6
        elif PYQT6:
            self.loader = self.load_ui_pyqt6
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
        parent = parent or self.parent
        loader = CustomUiLoader(parent, self.custom_widgets)
        file = QFile(ui_file)
        if not file.open(QIODevice.ReadOnly):
            raise IOError(f"Cannot open file: {ui_file}")
        widget = loader.load(file, parent)
        file.close()
        return widget

    def load_ui_pyqt6(self, ui_file, parent=None):
        """
        Specific loader for PyQt6 using loadUi.
        Args:
            ui_file(str): Path to the .ui file.
            parent(QWidget): Parent widget.

        Returns:
            QWidget: The loaded widget.
        """
        from PyQt6.uic.Loader.loader import DynamicUILoader

        class CustomDynamicUILoader(DynamicUILoader):
            def __init__(self, package, custom_widgets: dict = None):
                super().__init__(package)
                self.custom_widgets = custom_widgets or {}

            def _handle_custom_widgets(self, el):
                """Handle the <customwidgets> element."""

                def header2module(header):
                    """header2module(header) -> string

                    Convert paths to C++ header files to according Python modules
                    >>> header2module("foo/bar/baz.h")
                    'foo.bar.baz'
                    """

                    if header.endswith(".h"):
                        header = header[:-2]

                    mpath = []
                    for part in header.split("/"):
                        # Ignore any empty parts or those that refer to the current
                        # directory.
                        if part not in ("", "."):
                            if part == "..":
                                # We should allow this for Python3.
                                raise SyntaxError(
                                    "custom widget header file name may not contain '..'."
                                )

                            mpath.append(part)

                    return ".".join(mpath)

                for custom_widget in el:
                    classname = custom_widget.findtext("class")
                    header = custom_widget.findtext("header")
                    if header:
                        header = self._translate_bec_widgets_header(header)
                    self.factory.addCustomWidget(
                        classname,
                        custom_widget.findtext("extends") or "QWidget",
                        header2module(header),
                    )

            def _translate_bec_widgets_header(self, header):
                for name, value in self.custom_widgets.items():
                    if header == DesignerPluginInfo.pascal_to_snake(name):
                        return value.__module__
                return header

        return CustomDynamicUILoader("", self.custom_widgets).loadUi(ui_file, parent)

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
