from __future__ import annotations

import json

import pyqtgraph as pg
from bec_lib import bec_logger
from bec_lib.endpoints import MessageEndpoints
from pydantic import Field, ValidationError, field_validator
from qtpy.QtCore import QTimer, Signal
from qtpy.QtWidgets import QHBoxLayout, QMainWindow, QWidget

from bec_widgets.utils import Colors, ConnectionConfig
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.settings_dialog import SettingsDialog
from bec_widgets.utils.toolbars.toolbar import MaterialIconAction
from bec_widgets.widgets.plots.plot_base import PlotBase, UIMode
from bec_widgets.widgets.plots.scatter_waveform.scatter_curve import (
    ScatterCurve,
    ScatterCurveConfig,
    ScatterDeviceSignal,
)
from bec_widgets.widgets.plots.scatter_waveform.settings.scatter_curve_setting import (
    ScatterCurveSettings,
)

logger = bec_logger.logger


# noinspection PyDataclass
class ScatterWaveformConfig(ConnectionConfig):
    color_map: str | None = Field(
        "plasma",
        description="The color map of the z scaling of scatter waveform.",
        validate_default=True,
    )

    model_config: dict = {"validate_assignment": True}
    _validate_color_palette = field_validator("color_map")(Colors.validate_color_map)


class ScatterWaveform(PlotBase):
    PLUGIN = True
    RPC = True
    ICON_NAME = "scatter_plot"
    USER_ACCESS = [
        *PlotBase.USER_ACCESS,
        # Scatter Waveform Specific RPC Access
        "main_curve",
        "color_map",
        "color_map.setter",
        "plot",
        "update_with_scan_history",
        "clear_all",
        # Device properties
        "x_device_name",
        "x_device_name.setter",
        "x_device_entry",
        "x_device_entry.setter",
        "y_device_name",
        "y_device_name.setter",
        "y_device_entry",
        "y_device_entry.setter",
        "z_device_name",
        "z_device_name.setter",
        "z_device_entry",
        "z_device_entry.setter",
    ]

    sync_signal_update = Signal()
    new_scan = Signal()
    new_scan_id = Signal(str)
    scatter_waveform_property_changed = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        config: ScatterWaveformConfig | None = None,
        client=None,
        gui_id: str | None = None,
        popups: bool = True,
        **kwargs,
    ):
        if config is None:
            config = ScatterWaveformConfig(widget_class=self.__class__.__name__)
        # Specific GUI elements
        self.scatter_dialog = None
        self.scatter_curve_settings = None

        super().__init__(
            parent=parent, config=config, client=client, gui_id=gui_id, popups=popups, **kwargs
        )
        self._main_curve = ScatterCurve(parent_item=self)

        # Scan Data
        self.old_scan_id = None
        self.scan_id = None
        self.scan_item = None

        # Scan status update loop
        self.bec_dispatcher.connect_slot(self.on_scan_status, MessageEndpoints.scan_status())
        self.bec_dispatcher.connect_slot(self.on_scan_progress, MessageEndpoints.scan_progress())

        # Curve update loop
        self.proxy_update_sync = pg.SignalProxy(
            self.sync_signal_update, rateLimit=25, slot=self.update_sync_curves
        )

        self._init_scatter_curve_settings()

        # Show toolbar bundles - only include scatter_waveform_settings if not in SIDE mode
        shown_bundles = ["plot_export", "mouse_interaction", "roi", "axis_popup"]
        if self.ui_mode != UIMode.SIDE:
            shown_bundles.insert(0, "scatter_waveform_settings")
        self.toolbar.show_bundles(shown_bundles)

        self.update_with_scan_history(-1)

    ################################################################################
    # Widget Specific GUI interactions
    ################################################################################

    def _init_scatter_curve_settings(self):
        """
        Initialize the scatter curve settings menu.
        """
        if self.ui_mode == UIMode.SIDE:
            self.scatter_curve_settings = ScatterCurveSettings(
                parent=self, target_widget=self, popup=False
            )
            self.side_panel.add_menu(
                action_id="scatter_curve",
                icon_name="scatter_plot",
                tooltip="Show Scatter Curve Settings",
                widget=self.scatter_curve_settings,
                title="Scatter Curve Settings",
            )
        else:
            scatter_curve_action = MaterialIconAction(
                icon_name="scatter_plot",
                tooltip="Show Scatter Curve Settings",
                checkable=True,
                parent=self,
            )
            self.toolbar.add_action("scatter_waveform_settings", scatter_curve_action)
            scatter_curve_action.action.triggered.connect(self.show_scatter_curve_settings)

    def show_scatter_curve_settings(self):
        """
        Show the scatter curve settings dialog.
        """
        scatter_settings_action = self.toolbar.components.get_action(
            "scatter_waveform_settings"
        ).action
        if self.scatter_dialog is None or not self.scatter_dialog.isVisible():
            scatter_settings = ScatterCurveSettings(parent=self, target_widget=self, popup=True)
            self.scatter_dialog = SettingsDialog(
                self,
                settings_widget=scatter_settings,
                window_title="Scatter Curve Settings",
                modal=False,
            )
            self.scatter_dialog.resize(700, 240)
            # When the dialog is closed, update the toolbar icon and clear the reference
            self.scatter_dialog.finished.connect(self._scatter_dialog_closed)
            self.scatter_dialog.show()
            scatter_settings_action.setChecked(True)
        else:
            # If already open, bring it to the front
            self.scatter_dialog.raise_()
            self.scatter_dialog.activateWindow()
            scatter_settings_action.setChecked(True)  # keep it toggled

    def _scatter_dialog_closed(self):
        """
        Slot for when the scatter curve settings dialog is closed.
        """
        self.scatter_dialog = None
        self.toolbar.components.get_action("scatter_waveform_settings").action.setChecked(False)

    ################################################################################
    # Widget Specific Properties
    ################################################################################
    @property
    def main_curve(self) -> ScatterCurve:
        """The main scatter curve item."""
        return self._main_curve

    @SafeProperty(str)
    def color_map(self) -> str:
        """The color map of the scatter waveform."""
        return self.config.color_map

    @color_map.setter
    def color_map(self, value: str):
        """
        Set the color map of the scatter waveform.

        Args:
            value(str): The color map to set.
        """
        try:
            self.config.color_map = value
            self.main_curve.color_map = value
            self.scatter_waveform_property_changed.emit()
        except ValidationError:
            return

    @SafeProperty(str, designable=False, popup_error=True)
    def curve_json(self) -> str:
        """
        Get the curve configuration as a JSON string.
        """
        return json.dumps(self.main_curve.config.model_dump(), indent=2)

    @curve_json.setter
    def curve_json(self, value: str):
        """
        Set the curve configuration from a JSON string.

        Args:
            value(str): The JSON string to set the curve configuration from.
        """
        try:
            config = ScatterCurveConfig(**json.loads(value))
            self._add_main_scatter_curve(config)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON: {e}")

    ################################################################################
    # High Level methods for API
    ################################################################################
    @SafeSlot(popup_error=True)
    def plot(
        self,
        x_name: str,
        y_name: str,
        z_name: str,
        x_entry: None | str = None,
        y_entry: None | str = None,
        z_entry: None | str = None,
        color_map: str | None = "plasma",
        label: str | None = None,
        validate_bec: bool = True,
    ) -> ScatterCurve:
        """
        Plot the data from the device signals.

        Args:
            x_name (str): The name of the x device signal.
            y_name (str): The name of the y device signal.
            z_name (str): The name of the z device signal.
            x_entry (None | str): The x entry of the device signal.
            y_entry (None | str): The y entry of the device signal.
            z_entry (None | str): The z entry of the device signal.
            color_map (str | None): The color map of the scatter waveform.
            label (str | None): The label of the curve.
            validate_bec (bool): Whether to validate the device signals with current BEC instance.

        Returns:
            ScatterCurve: The scatter curve object.
        """

        if validate_bec:
            x_entry = self.entry_validator.validate_signal(x_name, x_entry)
            y_entry = self.entry_validator.validate_signal(y_name, y_entry)
            z_entry = self.entry_validator.validate_signal(z_name, z_entry)

        if color_map is not None:
            try:
                self.config.color_map = color_map
            except ValidationError:
                raise ValueError(
                    f"Invalid color map '{color_map}'. Using previously defined color map '{self.config.color_map}'."
                )

        if label is None:
            label = f"{z_name}-{z_entry}"

        config = ScatterCurveConfig(
            parent_id=self.gui_id,
            label=label,
            color_map=color_map,
            x_device=ScatterDeviceSignal(name=x_name, entry=x_entry),
            y_device=ScatterDeviceSignal(name=y_name, entry=y_entry),
            z_device=ScatterDeviceSignal(name=z_name, entry=z_entry),
        )

        # Add Curve
        self._add_main_scatter_curve(config)

        self.scatter_waveform_property_changed.emit()

        return self._main_curve

    def _add_main_scatter_curve(self, config: ScatterCurveConfig):
        """
        Add the main scatter curve to the plot.

        Args:
            config(ScatterCurveConfig): The configuration of the scatter curve.
        """
        # To have only one main curve
        if self._main_curve is not None:
            self.rpc_register.remove_rpc(self._main_curve)
            self.rpc_register.broadcast()
            self.plot_item.removeItem(self._main_curve)
            self._main_curve.deleteLater()
            self._main_curve = None

        self._main_curve = ScatterCurve(parent_item=self, config=config, name=config.label)

        # Update axis labels (matching Heatmap's label policy)
        self.update_labels()
        self.plot_item.addItem(self._main_curve)

        self.sync_signal_update.emit()

    ################################################################################
    # BEC Update Methods
    ################################################################################
    @SafeSlot(dict, dict)
    def on_scan_status(self, msg: dict, meta: dict):
        """
        Initial scan status message handler, which is triggered at the begging and end of scan.
        Used for triggering the update of the sync and async curves.

        Args:
            msg(dict): The message content.
            meta(dict): The message metadata.
        """
        current_scan_id = msg.get("scan_id", None)
        if current_scan_id is None:
            return
        if current_scan_id != self.scan_id:
            self.reset()
            self.new_scan.emit()
            self.new_scan_id.emit(current_scan_id)
            self.auto_range_x = True
            self.auto_range_y = True
            self.old_scan_id = self.scan_id
            self.scan_id = current_scan_id
            self.scan_item = self.queue.scan_storage.find_scan_by_ID(self.scan_id)

            # First trigger to update the scan curves
            self.sync_signal_update.emit()

    @SafeSlot(dict, dict)
    def on_scan_progress(self, msg: dict, meta: dict):
        """
        Slot for handling scan progress messages. Used for triggering the update of the sync curves.

        Args:
            msg(dict): The message content.
            meta(dict): The message metadata.
        """
        self.sync_signal_update.emit()
        status = msg.get("done")
        if status:
            QTimer.singleShot(100, self.update_sync_curves)
            QTimer.singleShot(300, self.update_sync_curves)

    @SafeSlot()
    def update_sync_curves(self, _=None):
        """
        Update the scan curves with the data from the scan segment.
        """
        if self.scan_item is None:
            logger.info("No scan executed so far; skipping device curves categorisation.")
            return "none"
        data, access_key = self._fetch_scan_data_and_access()

        if data == "none":
            logger.info("No scan executed so far; skipping device curves categorisation.")
            return "none"

        try:
            x_name = self._main_curve.config.x_device.name
            x_entry = self._main_curve.config.x_device.entry
            y_name = self._main_curve.config.y_device.name
            y_entry = self._main_curve.config.y_device.entry
            z_name = self._main_curve.config.z_device.name
            z_entry = self._main_curve.config.z_device.entry
        except AttributeError:
            return

        if access_key == "val":
            x_data = data.get(x_name, {}).get(x_entry, {}).get(access_key, None)
            y_data = data.get(y_name, {}).get(y_entry, {}).get(access_key, None)
            z_data = data.get(z_name, {}).get(z_entry, {}).get(access_key, None)
        else:
            x_data = data.get(x_name, {}).get(x_entry, {}).read().get("value", None)
            y_data = data.get(y_name, {}).get(y_entry, {}).read().get("value", None)
            z_data = data.get(z_name, {}).get(z_entry, {}).read().get("value", None)

        self._main_curve.set_data(x=x_data, y=y_data, z=z_data)

    def _fetch_scan_data_and_access(self):
        """
        Decide whether the widget is in live or historical mode
        and return the appropriate data dict and access key.

        Returns:
            data_dict (dict): The data structure for the current scan.
            access_key (str): Either 'val' (live) or 'value' (history).
        """
        if self.scan_item is None:
            # Optionally fetch the latest from history if nothing is set
            self.update_with_scan_history(-1)
            if self.scan_item is None:
                logger.info("No scan executed so far; skipping device curves categorisation.")
                return "none", "none"

        if hasattr(self.scan_item, "live_data"):
            # Live scan
            return self.scan_item.live_data, "val"
        else:
            # Historical
            scan_devices = self.scan_item.devices
            return scan_devices, "value"

    ################################################################################
    # Widget Specific Properties
    ################################################################################

    @SafeProperty(str)
    def x_device_name(self) -> str:
        """Device name for the X axis."""
        if self._main_curve is None or self._main_curve.config.x_device is None:
            return ""
        return self._main_curve.config.x_device.name or ""

    @x_device_name.setter
    def x_device_name(self, device_name: str) -> None:
        """
        Set the X device name.

        Args:
            device_name(str): Device name for the X axis
        """
        device_name = device_name or ""

        if device_name:
            try:
                entry = self.entry_validator.validate_signal(device_name, None)
                # Update or create config
                if self._main_curve.config.x_device is None:
                    self._main_curve.config.x_device = ScatterDeviceSignal(
                        name=device_name, entry=entry
                    )
                else:
                    self._main_curve.config.x_device.name = device_name
                    self._main_curve.config.x_device.entry = entry
                self.property_changed.emit("x_device_name", device_name)
                self.update_labels()
                self._try_auto_plot()
            except Exception:
                pass  # Silently fail if device is not available yet
        else:
            if self._main_curve.config.x_device is not None:
                self._main_curve.config.x_device = None
            self.property_changed.emit("x_device_name", "")
            self.update_labels()

    @SafeProperty(str)
    def x_device_entry(self) -> str:
        """Signal entry for the X axis device."""
        if self._main_curve is None or self._main_curve.config.x_device is None:
            return ""
        return self._main_curve.config.x_device.entry or ""

    @x_device_entry.setter
    def x_device_entry(self, entry: str) -> None:
        """
        Set the X device entry.

        Args:
            entry(str): Signal entry for the X axis device
        """
        if not entry:
            return

        if self._main_curve.config.x_device is None:
            logger.warning("Cannot set x_device_entry without x_device_name set first.")
            return

        device_name = self._main_curve.config.x_device.name
        try:
            validated_entry = self.entry_validator.validate_signal(device_name, entry)
            self._main_curve.config.x_device.entry = validated_entry
            self.property_changed.emit("x_device_entry", validated_entry)
            self.update_labels()
            self._try_auto_plot()
        except Exception:
            pass  # Silently fail if validation fails

    @SafeProperty(str)
    def y_device_name(self) -> str:
        """Device name for the Y axis."""
        if self._main_curve is None or self._main_curve.config.y_device is None:
            return ""
        return self._main_curve.config.y_device.name or ""

    @y_device_name.setter
    def y_device_name(self, device_name: str) -> None:
        """
        Set the Y device name.

        Args:
            device_name(str): Device name for the Y axis
        """
        device_name = device_name or ""

        if device_name:
            try:
                entry = self.entry_validator.validate_signal(device_name, None)
                # Update or create config
                if self._main_curve.config.y_device is None:
                    self._main_curve.config.y_device = ScatterDeviceSignal(
                        name=device_name, entry=entry
                    )
                else:
                    self._main_curve.config.y_device.name = device_name
                    self._main_curve.config.y_device.entry = entry
                self.property_changed.emit("y_device_name", device_name)
                self.update_labels()
                self._try_auto_plot()
            except Exception:
                pass  # Silently fail if device is not available yet
        else:
            if self._main_curve.config.y_device is not None:
                self._main_curve.config.y_device = None
            self.property_changed.emit("y_device_name", "")
            self.update_labels()

    @SafeProperty(str)
    def y_device_entry(self) -> str:
        """Signal entry for the Y axis device."""
        if self._main_curve is None or self._main_curve.config.y_device is None:
            return ""
        return self._main_curve.config.y_device.entry or ""

    @y_device_entry.setter
    def y_device_entry(self, entry: str) -> None:
        """
        Set the Y device entry.

        Args:
            entry(str): Signal entry for the Y axis device
        """
        if not entry:
            return

        if self._main_curve.config.y_device is None:
            logger.warning("Cannot set y_device_entry without y_device_name set first.")
            return

        device_name = self._main_curve.config.y_device.name
        try:
            validated_entry = self.entry_validator.validate_signal(device_name, entry)
            self._main_curve.config.y_device.entry = validated_entry
            self.property_changed.emit("y_device_entry", validated_entry)
            self.update_labels()
            self._try_auto_plot()
        except Exception:
            pass  # Silently fail if validation fails

    @SafeProperty(str)
    def z_device_name(self) -> str:
        """Device name for the Z (color) axis."""
        if self._main_curve is None or self._main_curve.config.z_device is None:
            return ""
        return self._main_curve.config.z_device.name or ""

    @z_device_name.setter
    def z_device_name(self, device_name: str) -> None:
        """
        Set the Z device name.

        Args:
            device_name(str): Device name for the Z axis
        """
        device_name = device_name or ""

        if device_name:
            try:
                entry = self.entry_validator.validate_signal(device_name, None)
                # Update or create config
                if self._main_curve.config.z_device is None:
                    self._main_curve.config.z_device = ScatterDeviceSignal(
                        name=device_name, entry=entry
                    )
                else:
                    self._main_curve.config.z_device.name = device_name
                    self._main_curve.config.z_device.entry = entry
                self.property_changed.emit("z_device_name", device_name)
                self.update_labels()
                self._try_auto_plot()
            except Exception:
                pass  # Silently fail if device is not available yet
        else:
            if self._main_curve.config.z_device is not None:
                self._main_curve.config.z_device = None
            self.property_changed.emit("z_device_name", "")
            self.update_labels()

    @SafeProperty(str)
    def z_device_entry(self) -> str:
        """Signal entry for the Z (color) axis device."""
        if self._main_curve is None or self._main_curve.config.z_device is None:
            return ""
        return self._main_curve.config.z_device.entry or ""

    @z_device_entry.setter
    def z_device_entry(self, entry: str) -> None:
        """
        Set the Z device entry.

        Args:
            entry(str): Signal entry for the Z axis device
        """
        if not entry:
            return

        if self._main_curve.config.z_device is None:
            logger.warning("Cannot set z_device_entry without z_device_name set first.")
            return

        device_name = self._main_curve.config.z_device.name
        try:
            validated_entry = self.entry_validator.validate_signal(device_name, entry)
            self._main_curve.config.z_device.entry = validated_entry
            self.property_changed.emit("z_device_entry", validated_entry)
            self.update_labels()
            self._try_auto_plot()
        except Exception:
            pass  # Silently fail if validation fails

    def _try_auto_plot(self) -> None:
        """
        Attempt to automatically call plot() if all three devices are set.
        """
        has_x = self._main_curve.config.x_device is not None
        has_y = self._main_curve.config.y_device is not None
        has_z = self._main_curve.config.z_device is not None

        if has_x and has_y and has_z:
            x_name = self._main_curve.config.x_device.name
            x_entry = self._main_curve.config.x_device.entry
            y_name = self._main_curve.config.y_device.name
            y_entry = self._main_curve.config.y_device.entry
            z_name = self._main_curve.config.z_device.name
            z_entry = self._main_curve.config.z_device.entry
            try:
                self.plot(
                    x_name=x_name,
                    y_name=y_name,
                    z_name=z_name,
                    x_entry=x_entry,
                    y_entry=y_entry,
                    z_entry=z_entry,
                    validate_bec=False,  # Don't validate - entries already validated
                )
            except Exception as e:
                logger.debug(f"Auto-plot failed: {e}")
                pass  # Silently fail if plot cannot be called yet

    def update_labels(self):
        """
        Update the labels of the x and y axes based on current device configuration.
        """
        if self._main_curve is None:
            return

        config = self._main_curve.config

        # Safely get device names
        x_device = config.x_device
        y_device = config.y_device

        x_name = x_device.name if x_device else None
        y_name = y_device.name if y_device else None

        if x_name is not None:
            self.x_label = x_name  # type: ignore
            x_dev = self.dev.get(x_name)
            if x_dev and hasattr(x_dev, "egu"):
                self.x_label_units = x_dev.egu()

        if y_name is not None:
            self.y_label = y_name  # type: ignore
            y_dev = self.dev.get(y_name)
            if y_dev and hasattr(y_dev, "egu"):
                self.y_label_units = y_dev.egu()

    ################################################################################
    # Scan History
    ################################################################################

    @SafeSlot(int)
    @SafeSlot(str)
    @SafeSlot()
    def update_with_scan_history(self, scan_index: int = None, scan_id: str = None):
        """
        Update the scan curves with the data from the scan storage.
        Provide only one of scan_id or scan_index.

        Args:
            scan_id(str, optional): ScanID of the scan to be updated. Defaults to None.
            scan_index(int, optional): Index of the scan to be updated. Defaults to None.
        """
        if scan_index is not None and scan_id is not None:
            raise ValueError("Only one of scan_id or scan_index can be provided.")

        if scan_index is None and scan_id is None:
            logger.warning(f"Neither scan_id or scan_number was provided, fetching the latest scan")
            scan_index = -1

        if scan_index is None:
            self.scan_id = scan_id
            self.scan_item = self.client.history.get_by_scan_id(scan_id)
            self.sync_signal_update.emit()
            return

        if scan_index == -1:
            scan_item = self.client.queue.scan_storage.current_scan
            if scan_item is not None:
                if scan_item.status_message is None:
                    logger.warning(f"Scan item with {scan_item.scan_id} has no status message.")
                    return
                self.scan_item = scan_item
                self.scan_id = scan_item.scan_id
                self.sync_signal_update.emit()
                return

        if len(self.client.history) == 0:
            logger.info("No scans executed so far. Skipping scan history update.")
            return

        self.scan_item = self.client.history[scan_index]
        metadata = self.scan_item.metadata
        self.scan_id = metadata["bec"]["scan_id"]

        self.sync_signal_update.emit()

    ################################################################################
    # Cleanup
    ################################################################################
    @SafeSlot()
    def clear_all(self):
        """
        Clear all the curves from the plot.
        """
        if self.crosshair is not None:
            self.crosshair.clear_markers()
        self._main_curve.clear()

    def cleanup(self):
        """
        Cleanup the widget and disconnect all signals.
        """
        if self.scatter_dialog is not None:
            self.scatter_dialog.close()
            self.scatter_dialog.deleteLater()
        if self.scatter_curve_settings is not None:
            self.scatter_curve_settings.cleanup()
        self.bec_dispatcher.disconnect_slot(self.on_scan_status, MessageEndpoints.scan_status())
        self.bec_dispatcher.disconnect_slot(self.on_scan_progress, MessageEndpoints.scan_progress())
        self.plot_item.removeItem(self._main_curve)
        self._main_curve = None
        super().cleanup()


class DemoApp(QMainWindow):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Waveform Demo")
        self.resize(800, 600)
        self.main_widget = QWidget()
        self.layout = QHBoxLayout(self.main_widget)
        self.setCentralWidget(self.main_widget)

        self.waveform_popup = ScatterWaveform(popups=True)
        self.waveform_popup.plot("samx", "samy", "bpm4i")

        self.waveform_side = ScatterWaveform(popups=False)
        self.waveform_popup.plot("samx", "samy", "bpm3a")

        self.layout.addWidget(self.waveform_side)
        self.layout.addWidget(self.waveform_popup)


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    widget = DemoApp()
    widget.show()
    widget.resize(1400, 600)
    sys.exit(app.exec_())
