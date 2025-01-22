import functools
import sys
import traceback

from bec_lib.logger import bec_logger
from qtpy.QtCore import Property, QObject, Qt, Signal, Slot
from qtpy.QtWidgets import QApplication, QMessageBox, QPushButton, QVBoxLayout, QWidget

logger = bec_logger.logger


def SafeProperty(prop_type, *prop_args, popup_error: bool = False, default=None, **prop_kwargs):
    """
    Decorator to create a Qt Property with safe getter and setter so that
    Qt Designer won't crash if an exception occurs in either method.

    Args:
        prop_type: The property type (e.g., str, bool, int, custom classes, etc.)
        popup_error (bool): If True, show a popup for any error; otherwise, ignore or log silently.
        default: Any default/fallback value to return if the getter raises an exception.
        *prop_args, **prop_kwargs: Passed along to the underlying Qt Property constructor.

    Usage:
        @SafeProperty(int, default=-1)
        def some_value(self) -> int:
            # your getter logic
            return ...   # if an exception is raised, returns -1

        @some_value.setter
        def some_value(self, val: int):
            # your setter logic
            ...
    """

    def decorator(py_getter):
        """Decorator for the user's property getter function."""

        @functools.wraps(py_getter)
        def safe_getter(self_):
            try:
                return py_getter(self_)
            except Exception:
                # Identify which property function triggered error
                prop_name = f"{py_getter.__module__}.{py_getter.__qualname__}"
                error_msg = traceback.format_exc()

                if popup_error:
                    ErrorPopupUtility().custom_exception_hook(*sys.exc_info(), popup_error=True)
                logger.error(f"SafeProperty error in GETTER of '{prop_name}':\n{error_msg}")
                return default

        class PropertyWrapper:
            """
            Intermediate wrapper used so that the user can optionally chain .setter(...).
            """

            def __init__(self, getter_func):
                # We store only our safe_getter in the wrapper
                self.getter_func = safe_getter

            def setter(self, setter_func):
                """Wraps the user-defined setter to handle errors safely."""

                @functools.wraps(setter_func)
                def safe_setter(self_, value):
                    try:
                        return setter_func(self_, value)
                    except Exception:
                        prop_name = f"{setter_func.__module__}.{setter_func.__qualname__}"
                        error_msg = traceback.format_exc()

                        if popup_error:
                            ErrorPopupUtility().custom_exception_hook(
                                *sys.exc_info(), popup_error=True
                            )
                        logger.error(f"SafeProperty error in SETTER of '{prop_name}':\n{error_msg}")
                        return

                # Return the full read/write Property
                return Property(prop_type, self.getter_func, safe_setter, *prop_args, **prop_kwargs)

            def __call__(self):
                """
                If user never calls `.setter(...)`, produce a read-only property.
                """
                return Property(prop_type, self.getter_func, None, *prop_args, **prop_kwargs)

        return PropertyWrapper(py_getter)

    return decorator


def SafeSlot(*slot_args, **slot_kwargs):  # pylint: disable=invalid-name
    """Function with args, acting like a decorator, applying "error_managed" decorator + Qt Slot
    to the passed function, to display errors instead of potentially raising an exception

    'popup_error' keyword argument can be passed with boolean value if a dialog should pop up,
    otherwise error display is left to the original exception hook
    """
    popup_error = bool(slot_kwargs.pop("popup_error", False))

    def error_managed(method):
        @Slot(*slot_args, **slot_kwargs)
        @functools.wraps(method)
        def wrapper(*args, **kwargs):
            try:
                return method(*args, **kwargs)
            except Exception:
                slot_name = f"{method.__module__}.{method.__qualname__}"
                error_msg = traceback.format_exc()
                if popup_error:
                    ErrorPopupUtility().custom_exception_hook(
                        *sys.exc_info(), popup_error=popup_error
                    )
                logger.error(f"SafeSlot error in slot '{slot_name}':\n{error_msg}")

        return wrapper

    return error_managed


class WarningPopupUtility(QObject):
    """
    Utility class to show warning popups in the application.
    """

    @SafeSlot(str, str, str, QWidget)
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


_popup_utility_instance = None


class _ErrorPopupUtility(QObject):
    """
    Utility class to manage error popups in the application to show error messages to the users.
    This class is singleton and the error popup can be enabled or disabled globally or attach to widget methods with decorator @error_managed.
    """

    error_occurred = Signal(str, str, QWidget)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.error_occurred.connect(self.show_error_message)
        self.enable_error_popup = False
        self._initialized = True
        sys.excepthook = self.custom_exception_hook

    @SafeSlot(str, str, QWidget)
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

    def show_property_error(self, title, message, widget):
        """
        Show a property-specific error message.
        """
        self.error_occurred.emit(title, message, widget)

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

    def get_error_message(self, exctype, value, tb):
        return "".join(traceback.format_exception(exctype, value, tb))

    def custom_exception_hook(self, exctype, value, tb, popup_error=False):
        if popup_error or self.enable_error_popup:
            self.error_occurred.emit(
                "Method error" if popup_error else "Application Error",
                self.get_error_message(exctype, value, tb),
                self.parent(),
            )
        else:
            sys.__excepthook__(exctype, value, tb)  # Call the original excepthook

    def enable_global_error_popups(self, state: bool):
        """
        Enable or disable global error popups for all applications.

        Args:
            state(bool): True to enable error popups, False to disable error popups.
        """
        self.enable_error_popup = bool(state)


def ErrorPopupUtility():
    global _popup_utility_instance
    if not _popup_utility_instance:
        _popup_utility_instance = _ErrorPopupUtility()
    return _popup_utility_instance


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

    @SafeSlot(popup_error=True)
    def method_with_error_handling(self):
        """This method raises an error and the exception is handled by the decorator."""
        raise ValueError("This is a handled error.")

    @SafeSlot()
    def method_without_error_handling(self):
        """This method raises an error and the exception is not handled here."""
        raise ValueError("This is an unhandled error.")

    @SafeSlot()
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
