import os

from qtpy.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget

from bec_widgets.qt_utils.error_popups import SafeSlot
from bec_widgets.qt_utils.settings_dialog import SettingWidget
from bec_widgets.utils import UILoader
from bec_widgets.utils.widget_io import WidgetIO


class AxisSettings(SettingWidget):
    def __init__(self, parent=None, target_widget=None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        # This is a settings widget that depends on the target widget
        # and should mirror what is in the target widget.
        # Saving settings for this widget could result in recursively setting the target widget.
        self.setProperty("skip_settings", True)
        self.setObjectName("AxisSettings")
        current_path = os.path.dirname(__file__)
        form = UILoader().load_ui(os.path.join(current_path, "axis_settings_vertical.ui"), self)

        self.target_widget = target_widget

        # # Scroll area
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setWidget(form)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.scroll_area)
        # self.layout.addWidget(self.ui)
        self.ui = form

        self.connect_all_signals()
        if self.target_widget is not None:
            self.target_widget.property_changed.connect(self.update_property)

    def connect_all_signals(self):
        for widget in [
            self.ui.title,
            self.ui.inner_axes,
            self.ui.outer_axes,
            self.ui.x_label,
            self.ui.x_min,
            self.ui.x_max,
            self.ui.x_log,
            self.ui.x_grid,
            self.ui.y_label,
            self.ui.y_min,
            self.ui.y_max,
            self.ui.y_log,
            self.ui.y_grid,
        ]:
            WidgetIO.connect_widget_change_signal(widget, self.set_property)

    @SafeSlot()
    def set_property(self, widget: QWidget, value):
        """
        Set property of the target widget based on the widget that emitted the signal.
        The name of the property has to be the same as the objectName of the widget
        and compatible with WidgetIO.

        Args:
            widget(QWidget): The widget that emitted the signal.
            value(): The value to set the property to.
        """

        try:  # to avoid crashing when the widget is not found in Designer
            property_name = widget.objectName()
            setattr(self.target_widget, property_name, value)
        except RuntimeError:
            return

    @SafeSlot()
    def update_property(self, property_name: str, value):
        """
        Update the value of the widget based on the property name and value.
        The name of the property has to be the same as the objectName of the widget
        and compatible with WidgetIO.

        Args:
            property_name(str): The name of the property to update.
            value: The value to set the property to.
        """
        try:  # to avoid crashing when the widget is not found in Designer
            widget_to_set = self.ui.findChild(QWidget, property_name)
        except RuntimeError:
            return
        # Block signals to avoid triggering set_property again
        was_blocked = widget_to_set.blockSignals(True)
        WidgetIO.set_value(widget_to_set, value)
        widget_to_set.blockSignals(was_blocked)
