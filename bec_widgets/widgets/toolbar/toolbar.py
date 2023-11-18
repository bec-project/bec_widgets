from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QPushButton
from abc import ABC, abstractmethod

from PyQt6.QtWidgets import QHBoxLayout, QWidget

from bec_widgets.widgets.editor.editor import BECEditor


class AbstractToolbarButton(QPushButton):  # , ABC): #TODO decide if ABC useful for this case..
    def __init__(self, text, slot_name, parent=None):
        super().__init__(text, parent)
        self.slot_name = slot_name

    # @abstractmethod
    def setup_button(self):
        """
        Setup specific properties for the button.
        """
        pass

    def connect_to_widget(self, widget):
        slot_function = getattr(widget, self.slot_name, None)
        if slot_function and callable(slot_function):
            self.clicked.connect(slot_function)


class OpenFileButton(AbstractToolbarButton):
    def __init__(self, parent=None):
        super().__init__("Open File", "openFile", parent)
        self.setup_button()

    def setup_button(self):
        self.setText("Open File")
        # Add specific setup for Open File Button
        # pass


class SaveFileButton(AbstractToolbarButton):
    def __init__(self, parent=None):
        super().__init__("Save File", "saveFile", parent)
        self.setup_button()

    def setup_button(self):
        self.setText("Save File")
        # Add specific setup for Save File Button
        # pass


class RunScriptButton(AbstractToolbarButton):
    def __init__(self, parent=None):
        super().__init__("Run Script", "runScript", parent)
        self.setup_button()

    def setup_button(self):
        # Add specific setup for Run Script Button
        self.setText("Run Script")
        # pass


class ModularToolbar(QWidget):
    def __init__(self, parent=None, auto_init=False):
        super().__init__(parent)
        # self.layout = QHBoxLayout()
        # self.setLayout(self.layout)
        # self.initialized = False
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)
        self.current_widget = None
        self.auto_init = auto_init
        self.initialized = False
        if self.auto_init:
            QTimer.singleShot(0, self.detect_context_and_update_buttons)

    def set_target_widget(self, widget):
        self.current_widget = widget
        self.update_buttons()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.initialized:
            self.detect_context_and_update_buttons()
            self.initialized = True

    def detect_context_and_update_buttons(self):
        if not self.auto_init or self.initialized:
            return

        parent_widget = self.parent()
        if parent_widget is None:
            return

        for child in parent_widget.children():
            if isinstance(child, BECEditor):
                self.set_widget(child)
                print("BECEditor init success!")
                break
            else:
                print("no supported widget detected")

    def set_widget(self, widget):
        self.clear_buttons()
        self.add_buttons([OpenFileButton(), SaveFileButton(), RunScriptButton()])
        self.connectToWidget(widget)

    def update_buttons(self):
        if self.current_widget is None:
            return

        self.clear_buttons()
        # if isinstance(self.current_widget, BECEditor):
        self.add_buttons([OpenFileButton(), SaveFileButton(), RunScriptButton()])
        # Additional conditions for other widget types can be added here

    def clear_buttons(self):
        for button in self.findChildren(AbstractToolbarButton):
            self.layout.removeWidget(button)
            button.deleteLater()

    def add_buttons(self, buttons):
        for button in buttons:
            self.layout.addWidget(button)
            button.connect_to_widget(self.current_widget)

    def connectToWidget(self, target_widget):
        for button in self.findChildren(AbstractToolbarButton):
            button.connect_to_widget(target_widget)
