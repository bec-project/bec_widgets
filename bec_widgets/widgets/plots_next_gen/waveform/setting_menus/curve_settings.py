import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidgetItem
from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.qt_utils.error_popups import SafeSlot
from bec_widgets.utils import UILoader
from bec_widgets.utils.widget_io import WidgetIO


class CurveSettingWidget(QWidget):
    """
        Widget that lets a user set up curves for the Waveform widget.
    It allows:
      - Selecting color palette for the entire widget
      - Choosing x-axis mode
      - Selecting device and signal
      - Adding a new curve
      - Viewing existing curves in a QTreeWidget
    """

    def __init__(self, parent=None, target_widget=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.setObjectName("CurveSettings")
        current_path = os.path.dirname(__file__)
        self.ui = UILoader().load_ui(os.path.join(current_path, "curve_settings.ui"), self)

        self.target_widget = target_widget

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.ui)

        self.connect_all_signals()

        self.refresh_tree_from_waveform()  # TODO implement

    def connect_all_signals(self):
        self.ui.pushButton.clicked.connect(self.on_apply_color_palette)
        self.ui.x_mode.currentTextChanged.connect(self.enable_ui_elements_x_mode)
        self.ui.x_mode.currentTextChanged.connect(self.on_x_mode_changed)
        self.enable_ui_elements_x_mode()  # Enable or disable the x-axis mode elements based on the x-axis mode

        self.ui.add_curve.clicked.connect(self.add_curve_from_ui)

        # TODO: Implement this method

        # General property forwarding for the target widget
        # for widget in [self.ui.x_mode]:
        #     WidgetIO.connect_widget_change_signal(widget, self.set_property)

    def enable_ui_elements_x_mode(self):
        """
        Enable or disable the x-axis mode elements based on the x-axis mode.
        """
        combo_box_mode = self.ui.x_mode.currentText()
        if combo_box_mode == "device":
            self.ui.device_line_edit.setEnabled(True)
            self.ui.signal_line_edit.setEnabled(True)
        else:
            self.ui.device_line_edit.setEnabled(False)
            self.ui.signal_line_edit.setEnabled(False)

    @SafeSlot("QString")
    def on_x_mode_changed(self, text):
        """
        Update the x-axis mode of the target widget.
        """
        if not self.target_widget:
            return

        self.target_widget.x_mode = text
        if text == "device":
            self.target_widget.device = self.ui.device_line_edit.text()
            self.target_widget.signal = self.ui.signal_line_edit.text()

        self.refresh_tree_from_waveform()  # TODO implement

    @SafeSlot()
    def on_apply_color_palette(self):
        """
        Apply the selected color palette to the target widget.
        """
        if not self.target_widget:
            return

        color_map = getattr(self.ui.bec_color_map_widget, "colormap", None)

        self.target_widget.color_palette = color_map

        self.refresh_tree_from_waveform()  # TODO implement

    def add_curve_from_ui(self):
        """
        Add a curve to the target widget based on the UI elements.
        """
        if not self.target_widget:
            return

    def refresh_tree_from_waveform(self):
        """
        Clears the treeWidget and repopulates it with the current curves
        from the target_widget’s curve_json.
        """
        self.ui.treeWidget.clear()
        if not self.target_widget:
            return

        # The Waveform has a SafeProperty 'curve_json' that returns JSON for all device curves
        # or you can iterate over target_widget.curves and build your own representation.
        # For a simpler approach, we’ll just iterate curves directly:

        for curve in self.target_widget.curves:
            # Make a top-level item in the tree for each curve
            top_item = QTreeWidgetItem(self.ui.treeWidget)
            top_item.setText(0, "CURVE")
            top_item.setText(1, curve.name())  # e.g. "myDevice-myEntry"

            # Child: device name
            dev_item = QTreeWidgetItem(top_item)
            dev_item.setText(0, "device")
            if curve.config.signal:
                dev_item.setText(1, curve.config.signal.name)

            # Child: entry
            entry_item = QTreeWidgetItem(top_item)
            entry_item.setText(0, "signal")
            if curve.config.signal:
                entry_item.setText(1, curve.config.signal.entry)

            # Child: color
            color_item = QTreeWidgetItem(top_item)
            color_item.setText(0, "color")
            if curve.config.color:
                color_item.setText(1, str(curve.config.color))

            # Child: source (custom/device/dap)
            source_item = QTreeWidgetItem(top_item)
            source_item.setText(0, "source")
            source_item.setText(1, curve.config.source)

            # Expand the top-level item
            self.ui.treeWidget.addTopLevelItem(top_item)
            top_item.setExpanded(True)

        # Optionally, resize columns
        # self.ui.treeWidget.header().resizeSections(Qt.ResizeToContents)

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

        property_name = widget.objectName()
        setattr(self.target_widget, property_name, value)

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
