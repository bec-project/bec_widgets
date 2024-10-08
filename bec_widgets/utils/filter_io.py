"""Module for handling filter I/O operations in BEC Widgets for input fields.
These operations include filtering device/signal names and/or device types.
"""

from abc import ABC, abstractmethod

from bec_lib.logger import bec_logger
from qtpy.QtCore import QStringListModel
from qtpy.QtWidgets import QComboBox, QCompleter, QLineEdit

logger = bec_logger.logger


class WidgetFilterHandler(ABC):
    """Abstract base class for widget filter handlers"""

    @abstractmethod
    def set_selection(self, widget, selection: list) -> None:
        """Set the filtered_selection for the widget

        Args:
            selection (list): Filtered selection of items
        """

    @abstractmethod
    def check_input(self, widget, text: str) -> bool:
        """Check if the input text is in the filtered selection

        Args:
            widget: Widget instance
            text (str): Input text

        Returns:
            bool: True if the input text is in the filtered selection
        """


class LineEditFilterHandler(WidgetFilterHandler):
    """Handler for QLineEdit widget"""

    def set_selection(self, widget: QLineEdit, selection: list) -> None:
        """Set the selection for the widget to the completer model

        Args:
            widget (QLineEdit): The QLineEdit widget
            selection (list): Filtered selection of items
        """
        if not isinstance(widget.completer, QCompleter):
            completer = QCompleter(widget)
            widget.setCompleter(completer)
        widget.completer.setModel(QStringListModel(selection, widget))

    def check_input(self, widget: QLineEdit, text: str) -> bool:
        """Check if the input text is in the filtered selection

        Args:
            widget (QLineEdit): The QLineEdit widget
            text (str): Input text

        Returns:
            bool: True if the input text is in the filtered selection
        """
        model = widget.completer.model()
        model_data = [model.data(model.index(i)) for i in range(model.rowCount())]
        return text in model_data


class ComboBoxFilterHandler(WidgetFilterHandler):
    """Handler for QComboBox widget"""

    def set_selection(self, widget: QComboBox, selection: list) -> None:
        """Set the selection for the widget to the completer model

        Args:
            widget (QComboBox): The QComboBox widget
            selection (list): Filtered selection of items
        """
        widget.clear()
        widget.addItems(selection)

    def check_input(self, widget: QComboBox, text: str) -> bool:
        """Check if the input text is in the filtered selection

        Args:
            widget (QComboBox): The QComboBox widget
            text (str): Input text

        Returns:
            bool: True if the input text is in the filtered selection
        """
        return text in [widget.itemText(i) for i in range(widget.count())]


class FilterIO:
    """Public interface to set filters for input widgets.
    It supports the list of widgets stored in class attribute _handlers.
    """

    _handlers = {QLineEdit: LineEditFilterHandler, QComboBox: ComboBoxFilterHandler}

    @staticmethod
    def set_selection(widget, selection: list, ignore_errors=False):
        """
        Retrieve value from the widget instance.

        Args:
            widget: Widget instance.
            selection(list): List of filtered selection items.
            ignore_errors(bool, optional): Whether to ignore if no handler is found.
        """
        handler_class = FilterIO._find_handler(widget)
        if handler_class:
            return handler_class().set_selection(widget=widget, selection=selection)
        if not ignore_errors:
            raise ValueError(
                f"No matching handler for widget type: {type(widget)} in handler list {FilterIO._handlers}"
            )
        return None

    @staticmethod
    def check_input(widget, text: str, ignore_errors=False):
        """
        Check if the input text is in the filtered selection.

        Args:
            widget: Widget instance.
            text(str): Input text.
            ignore_errors(bool, optional): Whether to ignore if no handler is found.

        Returns:
            bool: True if the input text is in the filtered selection.
        """
        handler_class = FilterIO._find_handler(widget)
        if handler_class:
            return handler_class().check_input(widget=widget, text=text)
        if not ignore_errors:
            raise ValueError(
                f"No matching handler for widget type: {type(widget)} in handler list {FilterIO._handlers}"
            )
        return None

    @staticmethod
    def _find_handler(widget):
        """
        Find the appropriate handler for the widget by checking its base classes.

        Args:
            widget: Widget instance.

        Returns:
            handler_class: The handler class if found, otherwise None.
        """
        for base in type(widget).__mro__:
            if base in FilterIO._handlers:
                return FilterIO._handlers[base]
        return None
