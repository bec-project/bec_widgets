import os

from qtpy.QtWidgets import QFrame, QScrollArea, QVBoxLayout

from bec_widgets.utils import UILoader
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.settings_dialog import SettingWidget


class ScatterCurveSettings(SettingWidget):
    def __init__(self, parent=None, target_widget=None, popup=False, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        # This is a settings widget that depends on the target widget
        # and should mirror what is in the target widget.
        # Saving settings for this widget could result in recursively setting the target widget.
        self.setProperty("skip_settings", True)

        current_path = os.path.dirname(__file__)
        if popup:
            form = UILoader().load_ui(
                os.path.join(current_path, "scatter_curve_settings_horizontal.ui"), self
            )
        else:
            form = UILoader().load_ui(
                os.path.join(current_path, "scatter_curve_settings_vertical.ui"), self
            )

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

        self.fetch_all_properties()

        self.target_widget.scatter_waveform_property_changed.connect(self.fetch_all_properties)
        if popup is False:
            self.ui.button_apply.clicked.connect(self.accept_changes)

    @SafeSlot()
    def fetch_all_properties(self):
        """
        Fetch all properties from the target widget and update the settings widget.
        """
        if not self.target_widget:
            return

        # Get properties from the target widget
        color_map = getattr(self.target_widget, "color_map", None)

        # Default values for device properties
        x_name, x_entry = None, None
        y_name, y_entry = None, None
        z_name, z_entry = None, None

        # Safely access device properties
        if hasattr(self.target_widget, "main_curve") and self.target_widget.main_curve:
            if hasattr(self.target_widget.main_curve, "config"):
                config = self.target_widget.main_curve.config

                if hasattr(config, "x_device") and config.x_device:
                    x_name = getattr(config.x_device, "name", None)
                    x_entry = getattr(config.x_device, "entry", None)

                if hasattr(config, "y_device") and config.y_device:
                    y_name = getattr(config.y_device, "name", None)
                    y_entry = getattr(config.y_device, "entry", None)

                if hasattr(config, "z_device") and config.z_device:
                    z_name = getattr(config.z_device, "name", None)
                    z_entry = getattr(config.z_device, "entry", None)

        # Apply the properties to the settings widget
        if hasattr(self.ui, "color_map"):
            self.ui.color_map.colormap = color_map

        if hasattr(self.ui, "x_name"):
            self.ui.x_name.set_device(x_name)
        if hasattr(self.ui, "x_entry") and x_entry is not None:
            self.ui.x_entry.setText(x_entry)

        if hasattr(self.ui, "y_name"):
            self.ui.y_name.set_device(y_name)
        if hasattr(self.ui, "y_entry") and y_entry is not None:
            self.ui.y_entry.setText(y_entry)

        if hasattr(self.ui, "z_name"):
            self.ui.z_name.set_device(z_name)
        if hasattr(self.ui, "z_entry") and z_entry is not None:
            self.ui.z_entry.setText(z_entry)

    @SafeSlot()
    def accept_changes(self):
        """
        Apply all properties from the settings widget to the target widget.
        """
        x_name = self.ui.x_name.text()
        x_entry = self.ui.x_entry.text()
        y_name = self.ui.y_name.text()
        y_entry = self.ui.y_entry.text()
        z_name = self.ui.z_name.text()
        z_entry = self.ui.z_entry.text()
        validate_bec = self.ui.validate_bec.checked
        color_map = self.ui.color_map.colormap

        self.target_widget.plot(
            x_name=x_name,
            y_name=y_name,
            z_name=z_name,
            x_entry=x_entry,
            y_entry=y_entry,
            z_entry=z_entry,
            color_map=color_map,
            validate_bec=validate_bec,
        )

    def cleanup(self):
        self.ui.x_name.close()
        self.ui.x_name.deleteLater()
        self.ui.x_entry.close()
        self.ui.x_entry.deleteLater()
        self.ui.y_name.close()
        self.ui.y_name.deleteLater()
        self.ui.y_entry.close()
        self.ui.y_entry.deleteLater()
        self.ui.z_name.close()
        self.ui.z_name.deleteLater()
        self.ui.z_entry.close()
        self.ui.z_entry.deleteLater()
