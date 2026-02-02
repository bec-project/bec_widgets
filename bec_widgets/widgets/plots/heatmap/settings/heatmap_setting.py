from __future__ import annotations

import os

from qtpy.QtWidgets import QFrame, QScrollArea, QVBoxLayout

from bec_widgets.utils import UILoader
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.settings_dialog import SettingWidget


class HeatmapSettings(SettingWidget):
    def __init__(self, parent=None, target_widget=None, popup=False, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        # This is a settings widget that depends on the target widget
        # and should mirror what is in the target widget.
        # Saving settings for this widget could result in recursively setting the target widget.
        self.setProperty("skip_settings", True)

        current_path = os.path.dirname(__file__)
        if popup:
            form = UILoader().load_ui(
                os.path.join(current_path, "heatmap_settings_horizontal.ui"), self
            )
        else:
            form = UILoader().load_ui(
                os.path.join(current_path, "heatmap_settings_vertical.ui"), self
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

        self.target_widget.heatmap_property_changed.connect(self.fetch_all_properties)
        if popup is False:
            self.ui.button_apply.clicked.connect(self.accept_changes)

        self.ui.device_x.setFocus()

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
        device_x, signal_x = None, None
        device_y, signal_y = None, None
        device_z, signal_z = None, None

        # Safely access device properties
        if hasattr(self.target_widget, "_image_config") and self.target_widget._image_config:
            config = self.target_widget._image_config

            if hasattr(config, "device_x") and config.device_x:
                device_x = getattr(config.device_x, "device", None)
                signal_x = getattr(config.device_x, "signal", None)

            if hasattr(config, "device_y") and config.device_y:
                device_y = getattr(config.device_y, "device", None)
                signal_y = getattr(config.device_y, "signal", None)

            if hasattr(config, "device_z") and config.device_z:
                device_z = getattr(config.device_z, "device", None)
                signal_z = getattr(config.device_z, "signal", None)

        # Apply the properties to the settings widget
        if hasattr(self.ui, "color_map"):
            self.ui.color_map.colormap = color_map

        if hasattr(self.ui, "device_x"):
            self.ui.device_x.set_device(device_x)
        if hasattr(self.ui, "signal_x") and signal_x is not None:
            self.ui.signal_x.set_to_obj_name(signal_x)

        if hasattr(self.ui, "device_y"):
            self.ui.device_y.set_device(device_y)
        if hasattr(self.ui, "signal_y") and signal_y is not None:
            self.ui.signal_y.set_to_obj_name(signal_y)

        if hasattr(self.ui, "device_z"):
            self.ui.device_z.set_device(device_z)
        if hasattr(self.ui, "signal_z") and signal_z is not None:
            self.ui.signal_z.set_to_obj_name(signal_z)

        if hasattr(self.ui, "interpolation"):
            self.ui.interpolation.setCurrentText(
                getattr(self.target_widget._image_config, "interpolation", "linear")
            )
        if hasattr(self.ui, "oversampling_factor"):
            self.ui.oversampling_factor.setValue(
                getattr(self.target_widget._image_config, "oversampling_factor", 1.0)
            )
        if hasattr(self.ui, "enforce_interpolation"):
            self.ui.enforce_interpolation.setChecked(
                getattr(self.target_widget._image_config, "enforce_interpolation", False)
            )

    @SafeSlot()
    def accept_changes(self):
        """
        Apply all properties from the settings widget to the target widget.
        """
        device_x = self.ui.device_x.currentText()
        signal_x = self.ui.signal_x.get_signal_name()
        device_y = self.ui.device_y.currentText()
        signal_y = self.ui.signal_y.get_signal_name()
        device_z = self.ui.device_z.currentText()
        signal_z = self.ui.signal_z.get_signal_name()
        validate_bec = self.ui.validate_bec.checked
        color_map = self.ui.color_map.colormap
        interpolation = self.ui.interpolation.currentText()
        oversampling_factor = self.ui.oversampling_factor.value()
        enforce_interpolation = self.ui.enforce_interpolation.isChecked()

        self.target_widget.plot(
            device_x=device_x,
            device_y=device_y,
            device_z=device_z,
            signal_x=signal_x,
            signal_y=signal_y,
            signal_z=signal_z,
            color_map=color_map,
            validate_bec=validate_bec,
            interpolation=interpolation,
            oversampling_factor=oversampling_factor,
            enforce_interpolation=enforce_interpolation,
            reload=True,
        )

    def cleanup(self):
        self.ui.device_x.close()
        self.ui.device_x.deleteLater()
        self.ui.signal_x.close()
        self.ui.signal_x.deleteLater()
        self.ui.device_y.close()
        self.ui.device_y.deleteLater()
        self.ui.signal_y.close()
        self.ui.signal_y.deleteLater()
        self.ui.device_z.close()
        self.ui.device_z.deleteLater()
        self.ui.signal_z.close()
        self.ui.signal_z.deleteLater()
        self.ui.interpolation.close()
        self.ui.interpolation.deleteLater()
