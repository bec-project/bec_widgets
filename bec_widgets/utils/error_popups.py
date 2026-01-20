import functools
import sys
import traceback
from typing import Any, Callable, Literal

import shiboken6
from bec_lib.logger import bec_logger
from louie.saferef import safe_ref
from qtpy.QtCore import Property, QObject, Qt, Signal, Slot
from qtpy.QtWidgets import (
    QApplication,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

logger = bec_logger.logger

RAISE_ERROR_DEFAULT = False


def SafeProperty(
    prop_type,
    *prop_args,
    popup_error: bool = False,
    default: Any = None,
    auto_emit: bool = False,
    emit_value: Literal["stored", "input"] | Callable[[object, object], object] = "stored",
    emit_on_change: bool = True,
    **prop_kwargs,
):
    """
    Decorator to create a Qt Property with safe getter and setter so that
    Qt Designer won't crash if an exception occurs in either method.

    Args:
        prop_type: The property type (e.g., str, bool, int, custom classes, etc.)
        popup_error (bool): If True, show a popup for any error; otherwise, ignore or log silently.
        default: Any default/fallback value to return if the getter raises an exception.
        auto_emit (bool): If True, automatically emit property_changed signal when setter is called.
                         Requires the widget to have a property_changed signal (str, object).
                         Note: This is different from Qt's 'notify' parameter which expects a Signal.
        emit_value: Controls which value is emitted when auto_emit=True.
            - "stored" (default): emit the value from the getter after setter runs
            - "input": emit the raw setter input
            - callable: called as emit_value(self_, value) after setter and must return the value to emit
        emit_on_change (bool): If True, emit only when the stored value changes.
        *prop_args, **prop_kwargs: Passed along to the underlying Qt Property constructor (check https://doc.qt.io/qt-6/properties.html).

    Usage:
        @SafeProperty(int, default=-1)
        def some_value(self) -> int:
            # your getter logic
            return ...   # if an exception is raised, returns -1

        @some_value.setter
        def some_value(self, val: int):
            # your setter logic
            ...

        # With auto-emit for toolbar sync:
        @SafeProperty(bool, auto_emit=True)
        def fft(self) -> bool:
            return self._fft

        @fft.setter
        def fft(self, value: bool):
            self._fft = value
            # property_changed.emit("fft", value) is called automatically

        # With custom emit modes:
        @SafeProperty(int, auto_emit=True, emit_value="stored")
        def precision_stored(self) -> int:
            return self._precision_stored

        @precision_stored.setter
        def precision_stored(self, value: int):
            self._precision_stored = max(0, int(value))

        @SafeProperty(int, auto_emit=True, emit_value="input")
        def precision_input(self) -> int:
            return self._precision_input

        @precision_input.setter
        def precision_input(self, value: int):
            self._precision_input = max(0, int(value))

    @SafeProperty(int, auto_emit=True, emit_value=lambda _self, v: int(v) * 10)
    def precision_callable(self) -> int:
        return self._precision_callable

        @precision_callable.setter
        def precision_callable(self, value: int):
            self._precision_callable = max(0, int(value))
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

        safe_getter.__is_safe_getter__ = True  # type: ignore[attr-defined]

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
                        before_value = None
                        if auto_emit and emit_on_change:
                            try:
                                before_value = self.getter_func(self_)
                            except Exception as e:
                                logger.warning(
                                    f"SafeProperty could not get 'before' value for change detection: {e}"
                                )
                                before_value = None

                        result = setter_func(self_, value)

                        # Auto-emit property_changed if auto_emit=True and signal exists
                        if auto_emit and hasattr(self_, "property_changed"):
                            prop_name = py_getter.__name__
                            try:
                                if callable(emit_value):
                                    emit_payload = emit_value(self_, value)
                                elif emit_value == "input":
                                    emit_payload = value
                                else:
                                    emit_payload = self.getter_func(self_)

                                if emit_on_change and before_value == emit_payload:
                                    return result

                                self_.property_changed.emit(prop_name, emit_payload)
                            except Exception as notify_error:
                                # Don't fail the setter if notification fails
                                logger.warning(
                                    f"SafeProperty auto_emit failed for '{prop_name}': {notify_error}"
                                )

                        return result
                    except Exception as e:
                        logger.warning(f"SafeProperty setter caught exception: {e}")
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


def _safe_connect_slot(weak_instance, weak_slot, *connect_args):
    """Internal function used by SafeConnect to handle weak references to slots."""
    instance = weak_instance()
    slot_func = weak_slot()

    # Check if the python object has already been garbage collected
    if instance is None or slot_func is None:
        return

    # Check if the python object has already been marked for deletion
    if getattr(instance, "_destroyed", False):
        return

    # Check if the C++ object is still valid
    if not shiboken6.isValid(instance):
        return

    if connect_args:
        slot_func(*connect_args)
    slot_func()


def SafeConnect(instance, signal, slot):  # pylint: disable=invalid-name
    """
    Method to safely handle Qt signal-slot connections. The python object is only forwarded
    as a weak reference to avoid stale objects.

    Args:
        instance: The instance to connect.
        signal: The signal to connect to.
        slot: The slot to connect.

    Example:
        >>> SafeConnect(self, qapp.theme.theme_changed, self._update_theme)

    """
    weak_instance = safe_ref(instance)
    weak_slot = safe_ref(slot)

    # Create a partial function that will check weak references before calling the actual slot
    safe_slot = functools.partial(_safe_connect_slot, weak_instance, weak_slot)

    # Connect the signal to the safe connect slot wrapper
    return signal.connect(safe_slot)


def SafeSlot(*slot_args, **slot_kwargs):  # pylint: disable=invalid-name
    """Function with args, acting like a decorator, applying "error_managed" decorator + Qt Slot
    to the passed function, to display errors instead of potentially raising an exception

    'popup_error' keyword argument can be passed with boolean value if a dialog should pop up,
    otherwise error display is left to the original exception hook
    'verify_sender' keyword argument can be passed with boolean value if the sender should be verified
    before executing the slot. If True, the slot will only execute if the sender is a QObject. This is
    useful to prevent function calls from already deleted objects.
    'raise_error' keyword argument can be passed with boolean value if the error should be raised
    after the error is displayed. This is useful to propagate the error to the caller but should be used
    with great care to avoid segfaults.

    The keywords above are stored in a container which can be overridden by passing
    '_override_slot_params' keyword argument with a dictionary containing the keywords to override.
    This is useful to override the default behavior of the decorator for a specific function call.

    """
    _slot_params = {
        "popup_error": bool(slot_kwargs.pop("popup_error", False)),
        "verify_sender": bool(slot_kwargs.pop("verify_sender", False)),
        "raise_error": bool(slot_kwargs.pop("raise_error", RAISE_ERROR_DEFAULT)),
    }

    def error_managed(method):
        @Slot(*slot_args, **slot_kwargs)
        @functools.wraps(method)
        def wrapper(*args, **kwargs):

            _override_slot_params = kwargs.pop("_override_slot_params", {})
            _slot_params.update(_override_slot_params)
            try:
                if not _slot_params["verify_sender"] or len(args) == 0:
                    return method(*args, **kwargs)

                _instance = args[0]
                if not isinstance(_instance, QObject):
                    return method(*args, **kwargs)
                sender = _instance.sender()
                if sender is None:
                    logger.info(
                        f"Sender is None for {method.__module__}.{method.__qualname__}, "
                        "skipping method call."
                    )
                    return
                return method(*args, **kwargs)

            except Exception:
                slot_name = f"{method.__module__}.{method.__qualname__}"
                error_msg = traceback.format_exc()
                if _slot_params["popup_error"]:
                    ErrorPopupUtility().custom_exception_hook(*sys.exc_info(), popup_error=True)
                logger.error(f"SafeSlot error in slot '{slot_name}':\n{error_msg}")
                if _slot_params["raise_error"]:
                    raise

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


class SafePropertyExampleWidget(QWidget):  # pragma: no cover
    """
    Example widget showcasing SafeProperty auto_emit modes.
    """

    property_changed = Signal(str, object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SafeProperty auto_emit example")
        self._precision_stored = 0
        self._precision_input = 0
        self._precision_callable = 0

        layout = QVBoxLayout(self)
        self.status = QLabel("last emit: <none>", self)

        self.spinbox_stored = QSpinBox(self)
        self.spinbox_stored.setRange(-5, 10)
        self.spinbox_stored.setValue(0)
        self.label_stored = QLabel("stored emit: <none>", self)

        self.spinbox_input = QSpinBox(self)
        self.spinbox_input.setRange(-5, 10)
        self.spinbox_input.setValue(0)
        self.label_input = QLabel("input emit: <none>", self)

        self.spinbox_callable = QSpinBox(self)
        self.spinbox_callable.setRange(-5, 10)
        self.spinbox_callable.setValue(0)
        self.label_callable = QLabel("callable emit: <none>", self)

        layout.addWidget(QLabel("stored emit (normalized value):", self))
        layout.addWidget(self.spinbox_stored)
        layout.addWidget(self.label_stored)

        layout.addWidget(QLabel("input emit (raw setter input):", self))
        layout.addWidget(self.spinbox_input)
        layout.addWidget(self.label_input)

        layout.addWidget(QLabel("callable emit (custom mapping):", self))
        layout.addWidget(self.spinbox_callable)
        layout.addWidget(self.label_callable)

        layout.addWidget(self.status)

        self.spinbox_stored.valueChanged.connect(self._on_spinbox_stored)
        self.spinbox_input.valueChanged.connect(self._on_spinbox_input)
        self.spinbox_callable.valueChanged.connect(self._on_spinbox_callable)
        self.property_changed.connect(self._on_property_changed)

    @SafeProperty(int, auto_emit=True, emit_value="stored", doc="Clamped precision value.")
    def precision_stored(self) -> int:
        return self._precision_stored

    @precision_stored.setter
    def precision_stored(self, value: int):
        self._precision_stored = max(0, int(value))

    @SafeProperty(int, auto_emit=True, emit_value="input", doc="Emit raw input value.")
    def precision_input(self) -> int:
        return self._precision_input

    @precision_input.setter
    def precision_input(self, value: int):
        self._precision_input = max(0, int(value))

    @SafeProperty(int, auto_emit=True, emit_value=lambda _self, v: int(v) * 10)
    def precision_callable(self) -> int:
        return self._precision_callable

    @precision_callable.setter
    def precision_callable(self, value: int):
        self._precision_callable = max(0, int(value))

    def _on_spinbox_stored(self, value: int):
        self.precision_stored = value

    def _on_spinbox_input(self, value: int):
        self.precision_input = value

    def _on_spinbox_callable(self, value: int):
        self.precision_callable = value

    def _on_property_changed(self, prop_name: str, value):
        self.status.setText(f"last emit: {prop_name}={value}")
        if prop_name == "precision_stored":
            self.label_stored.setText(f"stored emit: {value}")
        elif prop_name == "precision_input":
            self.label_input.setText(f"input emit: {value}")
        elif prop_name == "precision_callable":
            self.label_callable.setText(f"callable emit: {value}")


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
    tabs = QTabWidget()
    tabs.setWindowTitle("Error Popups & SafeProperty Examples")
    tabs.addTab(ExampleWidget(), "Error Popups")
    tabs.addTab(SafePropertyExampleWidget(), "SafeProperty auto_emit")
    tabs.resize(420, 520)
    tabs.show()
    sys.exit(app.exec_())
