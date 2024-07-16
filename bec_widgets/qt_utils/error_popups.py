import sys
import traceback

from qtpy.QtCore import QObject, Qt, Signal, Slot
from qtpy.QtWidgets import QApplication, QMessageBox, QPushButton, QVBoxLayout, QWidget


class WarningPopupUtility(QObject):
    """
    Utility class to show warning popups in the application.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

    @Slot(str, str, str, QWidget)
    def show_warning_message(self, title, message, detailed_text, widget):
        msg = QMessageBox(widget)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setDetailedText(detailed_text)
        msg.exec_()

    def show_warning(self, title: str, message: str, detailed_text: str, widget: QWidget = None):
        """
        Show a warning message with the given title, message, and detailed text.

        Args:
            title (str): The title of the warning message.
            message (str): The main text of the warning message.
            detailed_text (str): The detailed text to show when the user expands the message.
            widget (QWidget): The parent widget for the message box.
        """
        self.show_warning_message(title, message, detailed_text, widget)


class ErrorPopupUtility(QObject):
    """
    Utility class to manage error popups in the application to show error messages to the users.
    This class is singleton and the error popup can be enabled or disabled globally or attach to widget methods with decorator @error_managed.
    """

    error_occurred = Signal(str, str, QWidget)

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ErrorPopupUtility, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, parent=None):
        if not self._initialized:
            super().__init__(parent=parent)
            self.error_occurred.connect(self.show_error_message)
            self.enable_error_popup = False
            self.original_excepthook = sys.excepthook
            self._initialized = True

    @Slot(str, str, QWidget)
    def show_error_message(self, title, message, widget):
        detailed_text = self.format_traceback(message)
        error_message = self.parse_error_message(detailed_text)

        msg = QMessageBox(widget)
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle(title)
        msg.setText(error_message)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setDetailedText(detailed_text)
        msg.setTextInteractionFlags(Qt.TextSelectableByMouse)
        msg.setMinimumWidth(600)
        msg.setMinimumHeight(400)
        msg.exec_()

    def format_traceback(self, traceback_message: str) -> str:
        """
        Format the traceback message to be displayed in the error popup by adding indentation to each line.

        Args:
            traceback_message(str): The traceback message to be formatted.

        Returns:
            str: The formatted traceback message.
        """
        formatted_lines = []
        lines = traceback_message.split("\n")
        for line in lines:
            formatted_lines.append("    " + line)  # Add indentation to each line
        return "\n".join(formatted_lines)

    def parse_error_message(self, traceback_message):
        lines = traceback_message.split("\n")
        error_message = "Error occurred. See details."
        capture = False
        captured_message = []

        for line in lines:
            if "raise" in line:
                capture = True
                continue
            if capture:
                if line.strip() and not line.startswith("  File "):
                    captured_message.append(line.strip())
                else:
                    break

        if captured_message:
            error_message = " ".join(captured_message)
        return error_message

    def custom_exception_hook(self, exctype, value, tb):
        if self.enable_error_popup:
            error_message = traceback.format_exception(exctype, value, tb)
            self.error_occurred.emit("Application Error", "".join(error_message), self.parent())
        else:
            self.original_excepthook(exctype, value, tb)  # Call the original excepthook

    def enable_global_error_popups(self, state: bool):
        """
        Enable or disable global error popups for all applications.

        Args:
            state(bool): True to enable error popups, False to disable error popups.
        """
        self.enable_error_popup = bool(state)
        if self.enable_error_popup:
            sys.excepthook = self.custom_exception_hook
        else:
            sys.excepthook = self.original_excepthook

    @classmethod
    def reset_singleton(cls):
        """
        Reset the singleton instance.
        """
        cls._instance = None
        cls._initialized = False


def error_managed(method):
    """Decorator to manage errors with the ErrorPopupUtility"""

    def wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            error_message = traceback.format_exception(exc_type, exc_value, exc_traceback)
            ErrorPopupUtility().error_occurred.emit("Error in Method", "".join(error_message), None)
            if not ErrorPopupUtility()._instance.enable_error_popup:
                raise

    return wrapper


class ExampleWidget(QWidget):  # pragma: no cover
    """
    Example widget to demonstrate error handling with the ErrorPopupUtility.

    Warnings -> This example works properly only with PySide6, PyQt6 has a bug with the error handling.
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.init_ui()
        self.warning_utility = WarningPopupUtility(self)

    def init_ui(self):
        self.layout = QVBoxLayout(self)

        # Button to trigger method with error handling
        self.error_button = QPushButton("Trigger Handled Error", self)
        self.error_button.clicked.connect(self.method_with_error_handling)
        self.layout.addWidget(self.error_button)

        # Button to trigger method without error handling
        self.normal_button = QPushButton("Trigger Normal Error", self)
        self.normal_button.clicked.connect(self.method_without_error_handling)
        self.layout.addWidget(self.normal_button)

        # Button to trigger warning popup
        self.warning_button = QPushButton("Trigger Warning", self)
        self.warning_button.clicked.connect(self.trigger_warning)
        self.layout.addWidget(self.warning_button)

    @error_managed
    def method_with_error_handling(self):
        """This method raises an error and the exception is handled by the decorator."""
        raise ValueError("This is a handled error.")

    def method_without_error_handling(self):
        """This method raises an error and the exception is not handled here."""
        raise ValueError("This is an unhandled error.")

    def trigger_warning(self):
        """Trigger a warning using the WarningPopupUtility."""
        self.warning_utility.show_warning(
            title="Warning",
            message="This is a warning message.",
            detailed_text="This is the detailed text of the warning message.",
            widget=self,
        )


if __name__ == "__main__":  # pragma: no cover

    app = QApplication(sys.argv)
    widget = ExampleWidget()
    widget.show()
    sys.exit(app.exec_())
