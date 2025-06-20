"""Module for handling filter I/O operations in BEC Widgets for input fields.
These operations include filtering device/signal names and/or device types.
"""

from abc import ABC, abstractmethod

from bec_lib.logger import bec_logger
from qtpy.QtCore import QStringListModel
from qtpy.QtWidgets import QComboBox, QCompleter, QLineEdit

from bec_widgets.utils.ophyd_kind_util import Kind

logger = bec_logger.logger


class WidgetFilterHandler(ABC):
    """Abstract base class for widget filter handlers"""

    @abstractmethod
    def set_selection(self, widget, selection: list[str | tuple]) -> None:
        """Set the filtered_selection for the widget

        Args:
            widget: Widget instance
            selection (list[str | tuple]): Filtered selection of items.
                If tuple, it contains (text, data) pairs.
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

    @abstractmethod
    def update_with_kind(
        self, kind: Kind, signal_filter: set, device_info: dict, device_name: str
    ) -> list[str | tuple]:
        """Update the selection based on the kind of signal.

        Args:
            kind (Kind): The kind of signal to filter.
            signal_filter (set): Set of signal kinds to filter.
            device_info (dict): Dictionary containing device information.
            device_name (str): Name of the device.

        Returns:
            list[str | tuple]: A list of filtered signals based on the kind.
        """
        # This method should be implemented in subclasses or extended as needed


class LineEditFilterHandler(WidgetFilterHandler):
    """Handler for QLineEdit widget"""

    def set_selection(self, widget: QLineEdit, selection: list[str | tuple]) -> None:
        """Set the selection for the widget to the completer model

        Args:
            widget (QLineEdit): The QLineEdit widget
            selection (list[str | tuple]): Filtered selection of items. If tuple, it contains (text, data) pairs.
        """
        if isinstance(selection, tuple):
            # If selection is a tuple, it contains (text, data) pairs
            selection = [text for text, _ in selection]
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

    def update_with_kind(
        self, kind: Kind, signal_filter: set, device_info: dict, device_name: str
    ) -> list[str | tuple]:
        """Update the selection based on the kind of signal.

        Args:
            kind (Kind): The kind of signal to filter.
            signal_filter (set): Set of signal kinds to filter.
            device_info (dict): Dictionary containing device information.
            device_name (str): Name of the device.

        Returns:
            list[str | tuple]: A list of filtered signals based on the kind.
        """

        return [
            signal
            for signal, signal_info in device_info.items()
            if kind in signal_filter and (signal_info.get("kind_str", None) == str(kind.name))
        ]


class ComboBoxFilterHandler(WidgetFilterHandler):
    """Handler for QComboBox widget"""

    def set_selection(self, widget: QComboBox, selection: list[str | tuple]) -> None:
        """Set the selection for the widget to the completer model

        Args:
            widget (QComboBox): The QComboBox widget
            selection (list[str | tuple]): Filtered selection of items. If tuple, it contains (text, data) pairs.
        """
        widget.clear()
        if len(selection) == 0:
            return
        for element in selection:
            if isinstance(element, str):
                widget.addItem(element)
            elif isinstance(element, tuple):
                # If element is a tuple, it contains (text, data) pairs
                widget.addItem(*element)

    def check_input(self, widget: QComboBox, text: str) -> bool:
        """Check if the input text is in the filtered selection

        Args:
            widget (QComboBox): The QComboBox widget
            text (str): Input text

        Returns:
            bool: True if the input text is in the filtered selection
        """
        return text in [widget.itemText(i) for i in range(widget.count())]

    def update_with_kind(
        self, kind: Kind, signal_filter: set, device_info: dict, device_name: str
    ) -> list[str | tuple]:
        """Update the selection based on the kind of signal.

        Args:
            kind (Kind): The kind of signal to filter.
            signal_filter (set): Set of signal kinds to filter.
            device_info (dict): Dictionary containing device information.
            device_name (str): Name of the device.

        Returns:
            list[str | tuple]: A list of filtered signals based on the kind.
        """
        out = []
        for signal, signal_info in device_info.items():
            if kind not in signal_filter or (signal_info.get("kind_str", None) != str(kind.name)):
                continue
            obj_name = signal_info.get("obj_name", "")
            component_name = signal_info.get("component_name", "")
            signal_wo_device = obj_name.removeprefix(f"{device_name}_")
            if not signal_wo_device:
                signal_wo_device = obj_name

            if signal_wo_device != signal and component_name.replace(".", "_") != signal_wo_device:
                # If the object name is not the same as the signal name, we use the object name
                # to display in the combobox.
                out.append((f"{signal_wo_device} ({signal})", signal_info))
            else:
                # If the object name is the same as the signal name, we do not change it.
                out.append((signal, signal_info))

        return out


class FilterIO:
    """Public interface to set filters for input widgets.
    It supports the list of widgets stored in class attribute _handlers.
    """

    _handlers = {QLineEdit: LineEditFilterHandler, QComboBox: ComboBoxFilterHandler}

    @staticmethod
    def set_selection(widget, selection: list[str | tuple], ignore_errors=True):
        """
        Retrieve value from the widget instance.

        Args:
            widget: Widget instance.
            selection (list[str | tuple]): Filtered selection of items.
                If tuple, it contains (text, data) pairs.
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
    def check_input(widget, text: str, ignore_errors=True):
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
    def update_with_kind(
        widget, kind: Kind, signal_filter: set, device_info: dict, device_name: str
    ) -> list[str | tuple]:
        """
        Update the selection based on the kind of signal.

        Args:
            widget: Widget instance.
            kind (Kind): The kind of signal to filter.
            signal_filter (set): Set of signal kinds to filter.
            device_info (dict): Dictionary containing device information.
            device_name (str): Name of the device.

        Returns:
            list[str | tuple]: A list of filtered signals based on the kind.
        """
        handler_class = FilterIO._find_handler(widget)
        if handler_class:
            return handler_class().update_with_kind(
                kind=kind,
                signal_filter=signal_filter,
                device_info=device_info,
                device_name=device_name,
            )
        raise ValueError(
            f"No matching handler for widget type: {type(widget)} in handler list {FilterIO._handlers}"
        )

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
