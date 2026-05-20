from bec_lib.logger import bec_logger
from qtpy import PYSIDE6
from qtpy.QtCore import QEvent, QFile, QIODevice, QObject

from bec_widgets.utils.plugin_utils import get_designer_plugin

logger = bec_logger.logger

if PYSIDE6:
    from qtpy.QtUiTools import QUiLoader

    class _LoadedUiCloser(QObject):
        """Forward root close events to widgets instantiated by ``QUiLoader``.

        Destroying a parent widget does not guarantee ``closeEvent`` is delivered to
        every child widget. Some of our designer plugins rely on ``closeEvent`` /
        ``cleanup`` to unregister callbacks, so explicitly close loaded descendants
        when the loaded form itself is closed.
        """

        def __init__(self, root_widget):
            super().__init__(root_widget)
            self._root_widget = root_widget
            self._widgets = []
            root_widget.installEventFilter(self)

        def register_widget(self, widget):
            if widget is None or widget is self._root_widget:
                return
            self._widgets.append(widget)

        def eventFilter(self, watched, event):
            if watched is self._root_widget and event.type() == QEvent.Close:
                for widget in reversed(self._widgets):
                    try:
                        widget.close()
                    except RuntimeError:
                        continue
            return super().eventFilter(watched, event)

    class CustomUiLoader(QUiLoader):
        def __init__(self, baseinstance):
            super().__init__(baseinstance)
            self.baseinstance = baseinstance
            self._closer = _LoadedUiCloser(baseinstance) if baseinstance is not None else None

        def createWidget(self, class_name, parent=None, name=""):
            if parent is None and self.baseinstance is not None:
                return self.baseinstance

            widget_parent = parent if parent is not None else self.baseinstance
            widget = get_designer_plugin(class_name, raise_on_missing=False)
            if widget is not None:
                created_widget = widget(widget_parent)
                created_widget.setObjectName(name)
            else:
                created_widget = super().createWidget(class_name, widget_parent, name)

            if self._closer is not None:
                self._closer.register_widget(created_widget)
            return created_widget


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
