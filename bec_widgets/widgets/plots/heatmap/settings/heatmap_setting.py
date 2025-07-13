from __future__ import annotations

import os
from typing import TYPE_CHECKING

from qtpy.QtWidgets import QFrame, QScrollArea, QVBoxLayout

from bec_widgets.utils import UILoader
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.settings_dialog import SettingWidget

if TYPE_CHECKING:
    from bec_widgets.widgets.control.device_input.signal_combobox.signal_combobox import (
        SignalComboBox,
    )


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

        self.ui.x_name.setFocus()

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
        if hasattr(self.target_widget, "_image_config") and self.target_widget._image_config:
            config = self.target_widget._image_config

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
            self.ui.x_entry.set_to_obj_name(x_entry)

        if hasattr(self.ui, "y_name"):
            self.ui.y_name.set_device(y_name)
        if hasattr(self.ui, "y_entry") and y_entry is not None:
            self.ui.y_entry.set_to_obj_name(y_entry)

        if hasattr(self.ui, "z_name"):
            self.ui.z_name.set_device(z_name)
        if hasattr(self.ui, "z_entry") and z_entry is not None:
            self.ui.z_entry.set_to_obj_name(z_entry)

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

    def _get_signal_name(self, signal: SignalComboBox) -> str:
        """
        Get the signal name from the signal combobox.
        Args:
            signal (SignalComboBox): The signal combobox to get the name from.
        Returns:
            str: The signal name.
        """
        device_entry = signal.currentText()
        index = signal.findText(device_entry)
        if index == -1:
            return device_entry

        device_entry_info = signal.itemData(index)
        if device_entry_info:
            device_entry = device_entry_info.get("obj_name", device_entry)

        return device_entry if device_entry else ""

    @SafeSlot()
    def accept_changes(self):
        """
        Apply all properties from the settings widget to the target widget.
        """
        x_name = self.ui.x_name.currentText()
        x_entry = self._get_signal_name(self.ui.x_entry)
        y_name = self.ui.y_name.currentText()
        y_entry = self._get_signal_name(self.ui.y_entry)
        z_name = self.ui.z_name.currentText()
        z_entry = self._get_signal_name(self.ui.z_entry)
        validate_bec = self.ui.validate_bec.checked
        color_map = self.ui.color_map.colormap
        interpolation = self.ui.interpolation.currentText()
        oversampling_factor = self.ui.oversampling_factor.value()
        enforce_interpolation = self.ui.enforce_interpolation.isChecked()

        self.target_widget.plot(
            x_name=x_name,
            y_name=y_name,
            z_name=z_name,
            x_entry=x_entry,
            y_entry=y_entry,
            z_entry=z_entry,
            color_map=color_map,
            validate_bec=validate_bec,
            interpolation=interpolation,
            oversampling_factor=oversampling_factor,
            enforce_interpolation=enforce_interpolation,
            reload=True,
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
        self.ui.interpolation.close()
        self.ui.interpolation.deleteLater()
