from __future__ import annotations

from qtpy.QtCore import QSettings
from qtpy.QtWidgets import QFileDialog, QWidget


class WidgetStateManager:
    """
    A class to manage the state of a widget by saving and loading the state to and from a INI file.

    Args:
        widget(QWidget): The widget to manage the state for.
    """

    def __init__(self, widget):
        self.widget = widget

    def save_state(self, filename: str = None):
        """
        Save the state of the widget to a INI file.

        Args:
            filename(str): The filename to save the state to.
        """
        if not filename:
            filename, _ = QFileDialog.getSaveFileName(
                self.widget, "Save Settings", "", "INI Files (*.ini)"
            )
        if filename:
            settings = QSettings(filename, QSettings.IniFormat)
            self._save_widget_state_qsettings(self.widget, settings)

    def load_state(self, filename: str = None):
        """
        Load the state of the widget from a INI file.

        Args:
            filename(str): The filename to load the state from.
        """
        if not filename:
            filename, _ = QFileDialog.getOpenFileName(
                self.widget, "Load Settings", "", "INI Files (*.ini)"
            )
        if filename:
            settings = QSettings(filename, QSettings.IniFormat)
            self._load_widget_state_qsettings(self.widget, settings)

    def _save_widget_state_qsettings(self, widget: QWidget, settings: QSettings):
        """
        Save the state of the widget to QSettings.

        Args:
            widget(QWidget): The widget to save the state for.
            settings(QSettings): The QSettings object to save the state to.
        """
        meta = widget.metaObject()
        settings.beginGroup(widget.objectName())
        for i in range(meta.propertyCount()):
            prop = meta.property(i)
            name = prop.name()
            value = widget.property(name)
            settings.setValue(name, value)
        settings.endGroup()

        # Recursively save child widgets
        for child in widget.findChildren(QWidget):
            if child.objectName():
                self._save_widget_state_qsettings(child, settings)

    def _load_widget_state_qsettings(self, widget: QWidget, settings: QSettings):
        """
        Load the state of the widget from QSettings.

        Args:
            widget(QWidget): The widget to load the state for.
            settings(QSettings): The QSettings object to load the state from.
        """
        meta = widget.metaObject()
        settings.beginGroup(widget.objectName())
        for i in range(meta.propertyCount()):
            prop = meta.property(i)
            name = prop.name()
            if settings.contains(name):
                value = settings.value(name)
                widget.setProperty(name, value)
        settings.endGroup()

        # Recursively load child widgets
        for child in widget.findChildren(QWidget):
            if child.objectName():
                self._load_widget_state_qsettings(child, settings)
