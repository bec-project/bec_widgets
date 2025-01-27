from __future__ import annotations

from bec_lib import bec_logger
from qtpy.QtCore import QSettings
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

logger = bec_logger.logger


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
        Save the state of the widget to an INI file.

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
        Load the state of the widget from an INI file.

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
        if widget.property("skip_settings") is True:
            return

        meta = widget.metaObject()
        widget_name = self._get_full_widget_name(widget)
        settings.beginGroup(widget_name)
        for i in range(meta.propertyCount()):
            prop = meta.property(i)
            name = prop.name()
            if (
                name == "objectName"
                or not prop.isReadable()
                or not prop.isWritable()
                or not prop.isStored()  # can be extended to fine filter
            ):
                continue
            value = widget.property(name)
            settings.setValue(name, value)
        settings.endGroup()

        # Recursively process children (only if they aren't skipped)
        for child in widget.children():
            if (
                child.objectName()
                and child.property("skip_settings") is not True
                and not isinstance(child, QLabel)
            ):
                self._save_widget_state_qsettings(child, settings)

    def _load_widget_state_qsettings(self, widget: QWidget, settings: QSettings):
        """
        Load the state of the widget from QSettings.

        Args:
            widget(QWidget): The widget to load the state for.
            settings(QSettings): The QSettings object to load the state from.
        """
        if widget.property("skip_settings") is True:
            return

        meta = widget.metaObject()
        widget_name = self._get_full_widget_name(widget)
        settings.beginGroup(widget_name)
        for i in range(meta.propertyCount()):
            prop = meta.property(i)
            name = prop.name()
            if settings.contains(name):
                value = settings.value(name)
                widget.setProperty(name, value)
        settings.endGroup()

        # Recursively process children (only if they aren't skipped)
        for child in widget.children():
            if (
                child.objectName()
                and child.property("skip_settings") is not True
                and not isinstance(child, QLabel)
            ):
                self._load_widget_state_qsettings(child, settings)

    def _get_full_widget_name(self, widget: QWidget):
        """
        Get the full name of the widget including its parent names.

        Args:
            widget(QWidget): The widget to get the full name for.

        Returns:
            str: The full name of the widget.
        """
        name = widget.objectName()
        parent = widget.parent()
        while parent:
            obj_name = parent.objectName() or parent.metaObject().className()
            name = obj_name + "." + name
            parent = parent.parent()
        return name


class ExampleApp(QWidget):  # pragma: no cover:
    def __init__(self):
        super().__init__()
        self.setObjectName("MainWindow")
        self.setWindowTitle("State Manager Example")

        layout = QVBoxLayout(self)

        # A line edit to store some user text
        self.line_edit = QLineEdit(self)
        self.line_edit.setObjectName("MyLineEdit")
        self.line_edit.setPlaceholderText("Enter some text here...")
        layout.addWidget(self.line_edit)

        # A spin box to hold a numeric value
        self.spin_box = QSpinBox(self)
        self.spin_box.setObjectName("MySpinBox")
        self.spin_box.setRange(0, 100)
        layout.addWidget(self.spin_box)

        # A checkbox to hold a boolean value
        self.check_box = QCheckBox("Enable feature?", self)
        self.check_box.setObjectName("MyCheckBox")
        layout.addWidget(self.check_box)

        # A checkbox that we want to skip
        self.check_box_skip = QCheckBox("Enable feature - skip save?", self)
        self.check_box_skip.setProperty("skip_state", True)
        self.check_box_skip.setObjectName("MyCheckBoxSkip")
        layout.addWidget(self.check_box_skip)

        #  CREATE A "SIDE PANEL" with nested structure and skip all what is inside
        self.side_panel = QWidget(self)
        self.side_panel.setObjectName("SidePanel")
        self.side_panel.setProperty("skip_settings", True)  # skip the ENTIRE panel
        layout.addWidget(self.side_panel)

        # Put some sub-widgets inside side_panel
        panel_layout = QVBoxLayout(self.side_panel)
        self.panel_label = QLabel("Label in side panel", self.side_panel)
        self.panel_label.setObjectName("PanelLabel")
        panel_layout.addWidget(self.panel_label)

        self.panel_edit = QLineEdit(self.side_panel)
        self.panel_edit.setObjectName("PanelLineEdit")
        self.panel_edit.setPlaceholderText("I am inside side panel")
        panel_layout.addWidget(self.panel_edit)

        self.panel_checkbox = QCheckBox("Enable feature in side panel?", self.side_panel)
        self.panel_checkbox.setObjectName("PanelCheckBox")
        panel_layout.addWidget(self.panel_checkbox)

        # Save/Load buttons
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save State", self)
        self.load_button = QPushButton("Load State", self)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.load_button)
        layout.addLayout(button_layout)

        # Create the state manager
        self.state_manager = WidgetStateManager(self)

        # Connect buttons
        self.save_button.clicked.connect(lambda: self.state_manager.save_state())
        self.load_button.clicked.connect(lambda: self.state_manager.load_state())


if __name__ == "__main__":  # pragma: no cover:
    import sys

    app = QApplication(sys.argv)
    w = ExampleApp()
    w.show()
    sys.exit(app.exec_())
