"""Module providing a simple help inspector tool for QtWidgets."""

from functools import partial
from typing import Callable
from uuid import uuid4

from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy import QtCore, QtWidgets

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import AccentColors, get_accent_colors
from bec_widgets.utils.error_popups import SafeSlot

logger = bec_logger.logger


class HelpInspector(BECWidget, QtWidgets.QWidget):
    """
    A help inspector widget that allows to inspect other widgets in the application.
    Per default, it emits signals with the docstring, tooltip and bec help text of the inspected widget.
    The method "get_help_md" is called on the widget which is added to the BECWidget base class.
    It should return a string with a help text, ideally in proper format to be displayed (i.e. markdown).
    The inspector also allows to register custom callback that are called with the inspected widget
    as argument. This may be useful in the future to hook up more callbacks with custom signals.

    Args:
        parent (QWidget | None): The parent widget of the help inspector.
        client: Optional client for BECWidget functionality.
        size (tuple[int, int]): Optional size of the icon for the help inspector.
    """

    widget_docstring = QtCore.Signal(str)  # Emits docstring from QWidget
    widget_tooltip = QtCore.Signal(str)  # Emits tooltip string from QWidget
    bec_widget_help = QtCore.Signal(str)  # Emits md formatted help string from BECWidget class

    def __init__(self, parent=None, client=None):
        super().__init__(client=client, parent=parent, theme_update=True)
        self._app = QtWidgets.QApplication.instance()
        layout = QtWidgets.QHBoxLayout(self)  # type: ignore
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._active = False
        self._init_ui()
        self._callbacks = {}
        # Register the default callbacks
        self._register_default_callbacks()
        # Connect the button toggle signal
        self._button.toggled.connect(self._toggle_mode)

    def _init_ui(self):
        """Init the UI components."""
        colors: AccentColors = get_accent_colors()
        self._button = QtWidgets.QToolButton(self.parent())
        self._button.setCheckable(True)

        self._icon_checked = partial(
            material_icon, "help", size=(32, 32), color=colors.highlight, filled=True
        )
        self._icon_unchecked = partial(
            material_icon, "help", size=(32, 32), color=colors.highlight, filled=False
        )
        self._button.setText("Help Inspect Tool")
        self._button.setIcon(self._icon_unchecked())
        self._button.setToolTip("Click to enter Help Mode")
        self.layout().addWidget(self._button)

    def apply_theme(self, theme: str) -> None:
        colors = get_accent_colors()
        self._icon_checked = partial(
            material_icon, "help", size=(32, 32), color=colors.highlight, filled=True
        )
        self._icon_unchecked = partial(
            material_icon, "help", size=(32, 32), color=colors.highlight, filled=False
        )
        if self._active:
            self._button.setIcon(self._icon_checked())
        else:
            self._button.setIcon(self._icon_unchecked())

    @SafeSlot(bool)
    def _toggle_mode(self, enabled: bool):
        """
        Toggle the help inspection mode.

        Args:
            enabled (bool): Whether to enable or disable the help inspection mode.
        """
        if self._app is None:
            self._app = QtWidgets.QApplication.instance()
        self._active = enabled
        if enabled:
            self._app.installEventFilter(self)
            self._button.setIcon(self._icon_checked())
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WhatsThisCursor)
        else:
            self._app.removeEventFilter(self)
            self._button.setIcon(self._icon_unchecked())
            self._button.setChecked(False)
            QtWidgets.QApplication.restoreOverrideCursor()

    def eventFilter(self, obj, event):
        """
        Filter events to capture Key_Escape event, and mouse clicks
        if event filter is active. Any click event on a widget is suppressed, if
        the Inspector is active, and the registered callbacks are called with
        the clicked widget as argument.

        Args:
            obj (QObject): The object that received the event.
            event (QEvent): The event to filter.
        """
        if (
            event.type() == QtCore.QEvent.KeyPress
            and event.key() == QtCore.Qt.Key_Escape
            and self._active
        ):
            self._toggle_mode(False)
            return super().eventFilter(obj, event)
        if self._active and event.type() == QtCore.QEvent.MouseButtonPress:
            if event.button() == QtCore.Qt.LeftButton:
                widget = self._app.widgetAt(event.globalPos())
                if widget:
                    if widget is self or self.isAncestorOf(widget):
                        self._toggle_mode(False)
                        return True
                    for cb in self._callbacks.values():
                        try:
                            cb(widget)
                        except Exception as e:
                            print(f"Error occurred in callback {cb}: {e}")
                    return True
        return super().eventFilter(obj, event)

    def register_callback(self, callback: Callable[[QtWidgets.QWidget], None]) -> str:
        """
        Register a callback to be called when a widget is inspected.
        The callback should be callable with the following signature:
            callback(widget: QWidget) -> None

        Args:
            callback (Callable[[QWidget], None]): The callback function to register.
        Returns:
            str: A unique ID for the registered callback.
        """
        cb_id = str(uuid4())
        self._callbacks[cb_id] = callback
        return cb_id

    def unregister_callback(self, cb_id: str):
        """Unregister a previously registered callback."""
        self._callbacks.pop(cb_id, None)

    def _register_default_callbacks(self):
        """Default behavior: publish tooltip, docstring, bec_help"""

        def cb_doc(widget: QtWidgets.QWidget):
            docstring = widget.__doc__ or "No documentation available."
            self.widget_docstring.emit(docstring)

        def cb_help(widget: QtWidgets.QWidget):
            tooltip = widget.toolTip() or "No tooltip available."
            self.widget_tooltip.emit(tooltip)

        def cb_bec_help(widget: QtWidgets.QWidget):
            help_text = None
            if hasattr(widget, "get_help_md") and callable(widget.get_help_md):
                try:
                    help_text = widget.get_help_md()
                except Exception as e:
                    logger.debug(f"Error retrieving help text from {widget}: {e}")
            if help_text is None:
                help_text = widget.toolTip() or "No help available."
            if not isinstance(help_text, str):
                logger.error(
                    f"Help text from {widget.__class__} is not a string: {type(help_text)}"
                )
                help_text = str(help_text)
            self.bec_widget_help.emit(help_text)

        self.register_callback(cb_doc)
        self.register_callback(cb_help)
        self.register_callback(cb_bec_help)


if __name__ == "__main__":
    import sys

    from bec_qthemes import apply_theme

    from bec_widgets.widgets.control.device_control.positioner_box import PositionerBox
    from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

    app = QtWidgets.QApplication(sys.argv)

    main_window = QtWidgets.QMainWindow()
    apply_theme("dark")
    main_window.setWindowTitle("Help Inspector Test")

    central_widget = QtWidgets.QWidget()
    main_layout = QtWidgets.QVBoxLayout(central_widget)
    dark_mode_button = DarkModeButton(parent=main_window)
    main_layout.addWidget(dark_mode_button)

    help_inspector = HelpInspector()
    main_layout.addWidget(help_inspector)

    test_button = QtWidgets.QPushButton("Test Button")
    test_button.setToolTip("This is a test button.")
    test_line_edit = QtWidgets.QLineEdit()
    test_line_edit.setToolTip("This is a test line edit.")
    test_label = QtWidgets.QLabel("Test Label")
    test_label.setToolTip("")
    box = PositionerBox()

    layout_1 = QtWidgets.QHBoxLayout()
    layout_1.addWidget(test_button)
    layout_1.addWidget(test_line_edit)
    layout_1.addWidget(test_label)
    layout_1.addWidget(box)
    main_layout.addLayout(layout_1)

    doc_label = QtWidgets.QLabel("Docstring will appear here.")
    tool_tip_label = QtWidgets.QLabel("Tooltip will appear here.")
    bec_help_label = QtWidgets.QLabel("BEC Help text will appear here.")
    main_layout.addWidget(doc_label)
    main_layout.addWidget(tool_tip_label)
    main_layout.addWidget(bec_help_label)

    help_inspector.widget_tooltip.connect(tool_tip_label.setText)
    help_inspector.widget_docstring.connect(doc_label.setText)
    help_inspector.bec_widget_help.connect(bec_help_label.setText)

    main_window.setCentralWidget(central_widget)
    main_window.resize(400, 200)
    main_window.show()
    sys.exit(app.exec())
