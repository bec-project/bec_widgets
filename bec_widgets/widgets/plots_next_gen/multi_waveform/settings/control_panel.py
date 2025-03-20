import os

from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.qt_utils.error_popups import SafeSlot
from bec_widgets.qt_utils.settings_dialog import SettingWidget
from bec_widgets.utils import UILoader
from bec_widgets.utils.widget_io import WidgetIO


class MultiWaveformControlPanel(SettingWidget):
    """
    A settings widget MultiWaveformControlPanel that allows the user to modify the properties.

    The widget has skip_settings property set to True, which means it should not be saved
    in the settings file. It is used to mirror the properties of the target widget.
    """

    def __init__(self, parent=None, target_widget=None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        self.setProperty("skip_settings", True)
        self.setObjectName("MultiWaveformControlPanel")
        current_path = os.path.dirname(__file__)

        form = UILoader().load_ui(os.path.join(current_path, "multi_waveform_controls.ui"), self)

        self.target_widget = target_widget

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.ui = form

        self.ui_widget_list = [
            self.ui.opacity,
            self.ui.highlighted_index,
            self.ui.highlight_last_curve,
            self.ui.flush_buffer,
            self.ui.max_trace,
        ]

        if self.target_widget is not None:
            self.connect_all_signals()
            self.target_widget.property_changed.connect(self.update_property)
            self.target_widget.monitor_signal_updated.connect(self.update_controls_limits)
            self.ui.highlight_last_curve.toggled.connect(self.set_highlight_last_curve)

        self.fetch_all_properties()

    def connect_all_signals(self):
        for widget in self.ui_widget_list:
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
        if widget_to_set is None:
            return

        WidgetIO.set_value(widget_to_set, value)

    def fetch_all_properties(self):
        """
        Fetch all properties from the target widget and update the settings widget.
        """
        for widget in self.ui_widget_list:
            property_name = widget.objectName()
            value = getattr(self.target_widget, property_name)
            WidgetIO.set_value(widget, value)

    def accept_changes(self):
        """
        Apply all properties from the settings widget to the target widget.
        """
        for widget in self.ui_widget_list:
            property_name = widget.objectName()
            value = WidgetIO.get_value(widget)
            setattr(self.target_widget, property_name, value)

    @SafeSlot()
    def update_controls_limits(self):
        """
        Update the limits of the controls.
        """
        num_curves = len(self.target_widget.curves)
        if num_curves == 0:
            num_curves = 1  # Avoid setting max to 0
        current_index = num_curves - 1
        self.ui.highlighted_index.setMinimum(0)
        self.ui.highlighted_index.setMaximum(self.target_widget.number_of_visible_curves - 1)
        self.ui.spinbox_index.setMaximum(self.target_widget.number_of_visible_curves - 1)
        if self.ui.highlight_last_curve.isChecked():
            self.ui.highlighted_index.setValue(current_index)
            self.ui.spinbox_index.setValue(current_index)

    @SafeSlot(bool)
    def set_highlight_last_curve(self, enable: bool) -> None:
        """
        Enable or disable highlighting of the last curve.

        Args:
            enable(bool): True to enable highlighting of the last curve, False to disable.
        """
        self.target_widget.config.highlight_last_curve = enable
        if enable:
            self.ui.highlighted_index.setEnabled(False)
            self.ui.spinbox_index.setEnabled(False)
            self.ui.highlight_last_curve.setChecked(True)
            self.target_widget.set_curve_highlight(-1)
        else:
            self.ui.highlighted_index.setEnabled(True)
            self.ui.spinbox_index.setEnabled(True)
            self.ui.highlight_last_curve.setChecked(False)
            index = self.ui.spinbox_index.value()
            self.target_widget.set_curve_highlight(index)
