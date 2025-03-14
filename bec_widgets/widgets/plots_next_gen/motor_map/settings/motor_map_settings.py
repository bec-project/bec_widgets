import os

from qtpy.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget

from bec_widgets.qt_utils.error_popups import SafeSlot
from bec_widgets.qt_utils.settings_dialog import SettingWidget
from bec_widgets.utils import UILoader
from bec_widgets.utils.widget_io import WidgetIO


class MotorMapSettings(SettingWidget):
    """
    A settings widget for the MotorMap widget.

    The widget has skip_settings property set to True, which means it should not be saved
    in the settings file. It is used to mirror the properties of the target widget.
    """

    def __init__(self, parent=None, target_widget=None, popup=False, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        self.setProperty("skip_settings", True)
        self.setObjectName("MotorMapSettings")
        current_path = os.path.dirname(__file__)

        form = UILoader().load_ui(os.path.join(current_path, "motor_map_settings.ui"), self)

        self.target_widget = target_widget
        self.popup = popup

        # # Scroll area
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setWidget(form)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.scroll_area)
        self.ui = form

        self.ui_widget_list = [
            self.ui.max_points,
            self.ui.num_dim_points,
            self.ui.precision,
            self.ui.scatter_size,
            self.ui.background_value,
        ]

        if self.target_widget is not None and self.popup is False:
            self.connect_all_signals()
            self.target_widget.property_changed.connect(self.update_property)

        self.fetch_all_properties()

    def connect_all_signals(self):
        for widget in self.ui_widget_list:
            WidgetIO.connect_widget_change_signal(widget, self.set_property)
        self.ui.color_scatter.color_selected.connect(
            lambda color: self.target_widget.setProperty("color_scatter", color)
        )

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
        if property_name == "color_scatter":
            # Update the color scatter button
            self.ui.color_scatter.set_color(value)

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
        if widget_to_set is None:
            return
        if widget_to_set is self.ui.color_scatter:
            # Update the color scatter button
            self.ui.color_scatter.set_color(value)
            return
        # Block signals to avoid triggering set_property again
        was_blocked = widget_to_set.blockSignals(True)
        WidgetIO.set_value(widget_to_set, value)
        widget_to_set.blockSignals(was_blocked)

    def fetch_all_properties(self):
        """
        Fetch all properties from the target widget and update the settings widget.
        """
        for widget in self.ui_widget_list:
            property_name = widget.objectName()
            value = getattr(self.target_widget, property_name)
            WidgetIO.set_value(widget, value)

        self.ui.color_scatter.set_color(self.target_widget.color)

    def accept_changes(self):
        """
        Apply all properties from the settings widget to the target widget.
        """
        for widget in self.ui_widget_list:
            property_name = widget.objectName()
            value = WidgetIO.get_value(widget)
            setattr(self.target_widget, property_name, value)

        self.target_widget.color_scatter = self.ui.color_scatter.get_color()
