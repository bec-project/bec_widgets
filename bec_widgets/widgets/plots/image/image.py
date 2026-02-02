from __future__ import annotations

from collections import defaultdict
from typing import Literal

import numpy as np
from bec_lib import bec_logger
from bec_lib.endpoints import MessageEndpoints
from pydantic import BaseModel, Field, field_validator
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QWidget

from bec_widgets.utils import ConnectionConfig
from bec_widgets.utils.colors import Colors, apply_theme
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.widgets.plots.image.image_base import ImageBase
from bec_widgets.widgets.plots.image.image_item import ImageItem
from bec_widgets.widgets.plots.image.toolbar_components.device_selection import (
    DeviceSelection,
    DeviceSelectionConnection,
    device_selection_bundle,
)
from bec_widgets.widgets.plots.plot_base import PlotBase

logger = bec_logger.logger


# noinspection PyDataclass
class ImageConfig(ConnectionConfig):
    color_map: str = Field(
        "plasma", description="The colormap  of the figure widget.", validate_default=True
    )
    color_bar: Literal["full", "simple"] | None = Field(
        None, description="The type of the color bar."
    )
    lock_aspect_ratio: bool = Field(
        False, description="Whether to lock the aspect ratio of the image."
    )

    model_config: dict = {"validate_assignment": True}
    _validate_color_map = field_validator("color_map")(Colors.validate_color_map)


class ImageLayerConfig(BaseModel):
    device: str = Field("", description="The device name to monitor.")
    signal: str = Field("", description="The signal/entry name to monitor on the device.")
    monitor_type: Literal["1d", "2d"] | None = Field(None, description="The type of monitor.")
    source: Literal["device_monitor_1d", "device_monitor_2d"] | None = Field(
        None, description="The source of the image data."
    )
    async_signal_name: str | None = Field(
        None, description="Async signal name (obj_name) used for async endpoints."
    )
    connection_status: Literal["connected", "disconnected", "error"] = Field(
        "disconnected", description="Current connection status."
    )
    connection_error: str | None = Field(None, description="Last connection error, if any.")


class Image(ImageBase):
    """
    Image widget for displaying 2D data.
    """

    PLUGIN = True
    RPC = True
    ICON_NAME = "image"
    USER_ACCESS = [
        *PlotBase.USER_ACCESS,
        # ImageView Specific Settings
        "color_map",
        "color_map.setter",
        "v_range",
        "v_range.setter",
        "v_min",
        "v_min.setter",
        "v_max",
        "v_max.setter",
        "autorange",
        "autorange.setter",
        "autorange_mode",
        "autorange_mode.setter",
        "device",
        "device.setter",
        "signal",
        "signal.setter",
        "enable_colorbar",
        "enable_simple_colorbar",
        "enable_simple_colorbar.setter",
        "enable_full_colorbar",
        "enable_full_colorbar.setter",
        "fft",
        "fft.setter",
        "log",
        "log.setter",
        "num_rotation_90",
        "num_rotation_90.setter",
        "transpose",
        "transpose.setter",
        "image",
        "main_image",
        "add_roi",
        "remove_roi",
        "rois",
    ]

    SUPPORTED_SIGNALS = ["AsyncSignal", "AsyncMultiSignal", "DynamicSignal"]

    def __init__(
        self,
        parent: QWidget | None = None,
        config: ImageConfig | None = None,
        client=None,
        gui_id: str | None = None,
        popups: bool = True,
        **kwargs,
    ):
        if config is None:
            config = ImageConfig(widget_class=self.__class__.__name__)
        self.gui_id = config.gui_id
        self.subscriptions: defaultdict[str, ImageLayerConfig] = defaultdict(ImageLayerConfig)
        # Store signal configs separately (not serialized to QSettings)
        self._signal_configs: dict[str, dict] = {}

        super().__init__(
            parent=parent, config=config, client=client, gui_id=gui_id, popups=popups, **kwargs
        )
        self._device_selection_updating = False
        self._autorange_on_next_update = False
        self._init_toolbar_image()
        self.layer_removed.connect(self._on_layer_removed)
        self.old_scan_id = None
        self.scan_id = None
        self.async_update = False
        self.bec_dispatcher.connect_slot(self.on_scan_status, MessageEndpoints.scan_status())
        self.bec_dispatcher.connect_slot(self.on_scan_progress, MessageEndpoints.scan_progress())

    @property
    def _config(self) -> ImageLayerConfig:
        """Helper property to access the main layer config."""
        return self.subscriptions["main"]

    ##################################
    ### Toolbar Initialization
    ##################################

    def _init_toolbar_image(self):
        """
        Initializes the toolbar for the image widget.
        """
        self.toolbar.add_bundle(
            device_selection_bundle(self.toolbar.components, client=self.client)
        )
        self.toolbar.connect_bundle(
            "device_selection",
            DeviceSelectionConnection(self.toolbar.components, target_widget=self),
        )

        crosshair_bundle = self.toolbar.get_bundle("image_crosshair")
        crosshair_bundle.add_action("image_autorange")
        crosshair_bundle.add_action("image_colorbar_switch")

        self.toolbar.show_bundles(
            [
                "device_selection",
                "plot_export",
                "mouse_interaction",
                "image_crosshair",
                "image_processing",
                "axis_popup",
            ]
        )

        QTimer.singleShot(0, self._adjust_and_connect)

    def _adjust_and_connect(self):
        """
        Sync the device selection toolbar with current properties.
        Has to be done with QTimer.singleShot to ensure the UI is fully initialized, needed for testing.

        Note: DeviceComboBox and SignalComboBox auto-populate themselves, no manual population needed.
        """
        self._sync_device_selection()

    @SafeSlot()
    def on_device_selection_changed(self, _):
        """
        Called when device or signal selection changes in the toolbar.
        This reads from the toolbar and updates the widget properties.
        """
        if self._device_selection_updating:
            return

        self._device_selection_updating = True
        try:
            try:
                action = self.toolbar.components.get_action("device_selection")
            except Exception:
                return

            if action is None:
                return

            device_selection: DeviceSelection = action.widget
            device = device_selection.device_combo_box.currentText()
            signal_text = device_selection.signal_combo_box.currentText()

            if not device:
                self.device = ""
                return
            if not device_selection.device_combo_box.is_valid_input:
                return

            if not device_selection.signal_combo_box.is_valid_input:
                if self._config.signal:
                    self.signal = ""
                if device != self._config.device:
                    self.device = device
                return

            if device == self._config.device and signal_text == self._config.signal:
                return

            # Get the signal config stored in the combobox
            signal_config = device_selection.signal_combo_box.get_signal_config()

            if not signal_config:
                # Fallback: try to get config from device
                try:
                    device_obj = self.dev[device]
                    signal_config = device_obj._info["signals"].get(signal_text, {})
                except (KeyError, AttributeError):
                    logger.warning(f"Could not get signal config for {device}.{signal_text}")
                    signal_config = None

            # Store signal config and set properties which will trigger the connection
            self._signal_configs["main"] = signal_config
            self.device = device
            self.signal = signal_text
        finally:
            self._device_selection_updating = False

    ################################################################################
    # Data Acquisition

    @SafeProperty(str, auto_emit=True)
    def device(self) -> str:
        """
        The name of the device to monitor for image data.
        """
        return self._config.device

    @device.setter
    def device(self, value: str):
        """
        Set the device name for the image. This should be used together with signal.
        When both device and signal are set, the widget connects to that device signal.

        Args:
            value(str): The name of the device to monitor.
        """
        if not value:
            # Clear the monitor if empty device name
            if self._config.device:
                self._disconnect_current_monitor()
                self._config.device = ""
                self._config.signal = ""
                self._signal_configs.pop("main", None)
                self._set_connection_status("disconnected")
            return

        old_device = self._config.device
        self._config.device = value

        # If we have a signal, reconnect with the new device
        if self._config.signal:
            # Try to get fresh signal config for the new device
            try:
                device_obj = self.dev[value]
                # Try to get signal config for the current entry
                if self._config.signal in device_obj._info.get("signals", {}):
                    self._signal_configs["main"] = device_obj._info["signals"][self._config.signal]
                    self._setup_connection()
                else:
                    # Signal doesn't exist on new device
                    logger.warning(
                        f"Signal '{self._config.signal}' doesn't exist on device '{value}'"
                    )
                    self._disconnect_current_monitor()
                    self._config.signal = ""
                    self._signal_configs.pop("main", None)
                    self._set_connection_status(
                        "error", f"Signal '{self._config.signal}' doesn't exist"
                    )
            except (KeyError, AttributeError):
                # Device doesn't exist
                logger.warning(f"Device '{value}' not found")
                if old_device:
                    self._disconnect_current_monitor()
                self._set_connection_status("error", f"Device '{value}' not found")

        # Toolbar sync happens via SafeProperty auto_emit property_changed handling.

    @SafeProperty(str, auto_emit=True)
    def signal(self) -> str:
        """
        The signal/entry name to monitor on the device.
        """
        return self._config.signal

    @signal.setter
    def signal(self, value: str):
        """
        Set the device signal for the image. This should be used together with device.
        When set, it will connect to updates from that device signal.

        Args:
            value(str): The signal name to monitor.
        """
        if not value:
            if self._config.signal:
                self._disconnect_current_monitor()
                self._config.signal = ""
                self._signal_configs.pop("main", None)
                self._set_connection_status("disconnected")
            return

        self._config.signal = value

        # If we have a device, try to connect
        if self._config.device:
            try:
                device_obj = self.dev[self._config.device]
                signal_config = device_obj._info["signals"].get(value)
                if not isinstance(signal_config, dict) or not signal_config.get("signal_class"):
                    logger.warning(
                        f"Could not find valid configuration for signal '{value}' "
                        f"on device '{self._config.device}'."
                    )
                    self._signal_configs.pop("main", None)
                    self._set_connection_status("error", f"Signal '{value}' not found")
                    return

                self._signal_configs["main"] = signal_config
                self._setup_connection()
            except (KeyError, AttributeError):
                logger.warning(
                    f"Could not find signal '{value}' on device '{self._config.device}'."
                )
                # Remove signal config if it can't be fetched
                self._signal_configs.pop("main", None)
                self._set_connection_status("error", f"Signal '{value}' not found")

        else:
            logger.debug(f"signal setter: No device set yet for signal '{value}'")

    @property
    def main_image(self) -> ImageItem:
        """Access the main image item."""
        return self.layer_manager["main"].image

    def _setup_connection(self):
        """
        Internal method to setup connection based on current device, signal, and signal_config.
        """
        if not self._config.device or not self._config.signal:
            logger.warning("Cannot setup connection without both device and signal")
            self._set_connection_status("disconnected")
            return

        signal_config = self._signal_configs.get("main")
        if not signal_config:
            logger.warning(
                f"Cannot setup connection for {self._config.device}.{self._config.signal} without signal_config"
            )
            self._set_connection_status("error", "Missing signal config")
            return

        # Disconnect any existing monitor first
        self._disconnect_current_monitor()

        # Determine monitor type and source from signal_config
        signal_class = signal_config.get("signal_class", None)
        supported_classes = ["PreviewSignal"] + self.SUPPORTED_SIGNALS

        if signal_class not in supported_classes:
            logger.warning(
                f"Signal '{self._config.device}.{self._config.signal}' has unsupported signal class '{signal_class}'. "
                f"Supported classes: {supported_classes}"
            )
            self._set_connection_status("error", f"Unsupported signal class '{signal_class}'")
            return

        describe = signal_config.get("describe") or {}
        signal_info = describe.get("signal_info") or {}
        ndim = signal_info.get("ndim", None)

        if ndim is None:
            logger.warning(
                f"Signal '{self._config.device}.{self._config.signal}' does not have a valid 'ndim' in its signal_info."
            )
            self._set_connection_status("error", "Missing ndim in signal_info")
            return

        config = self.subscriptions["main"]
        self.async_update = False
        config.async_signal_name = None

        if ndim == 1:
            config.source = "device_monitor_1d"
            config.monitor_type = "1d"
            if signal_class == "PreviewSignal":
                self.bec_dispatcher.connect_slot(
                    self.on_image_update_1d,
                    MessageEndpoints.device_preview(self._config.device, self._config.signal),
                )
            elif signal_class in self.SUPPORTED_SIGNALS:
                self.async_update = True
                config.async_signal_name = signal_config.get(
                    "obj_name", f"{self._config.device}_{self._config.signal}"
                )
                self._setup_async_image(self.scan_id)
        elif ndim == 2:
            config.source = "device_monitor_2d"
            config.monitor_type = "2d"
            if signal_class == "PreviewSignal":
                self.bec_dispatcher.connect_slot(
                    self.on_image_update_2d,
                    MessageEndpoints.device_preview(self._config.device, self._config.signal),
                )
            elif signal_class in self.SUPPORTED_SIGNALS:
                self.async_update = True
                config.async_signal_name = signal_config.get(
                    "obj_name", f"{self._config.device}_{self._config.signal}"
                )
                self._setup_async_image(self.scan_id)
        else:
            logger.warning(
                f"Unsupported ndim '{ndim}' for monitor '{self._config.device}.{self._config.signal}'."
            )
            self._set_connection_status("error", f"Unsupported ndim '{ndim}'")
            return

        self._set_connection_status("connected")
        logger.info(
            f"Connected to {self._config.device}.{self._config.signal} with type {config.monitor_type}"
        )
        self._autorange_on_next_update = True

    def _disconnect_current_monitor(self):
        """
        Internal method to disconnect the current monitor subscriptions.
        """
        if not self._config.device or not self._config.signal:
            return

        config = self.subscriptions["main"]

        if self.async_update:
            async_signal_name = config.async_signal_name or self._config.signal
            ids_to_check = [self.scan_id, self.old_scan_id]

            if config.source == "device_monitor_1d":
                for scan_id in ids_to_check:
                    if scan_id is None:
                        continue
                    self.bec_dispatcher.disconnect_slot(
                        self.on_image_update_1d,
                        MessageEndpoints.device_async_signal(
                            scan_id, self._config.device, async_signal_name
                        ),
                    )
                    logger.info(
                        f"Disconnecting 1d update ScanID:{scan_id}, Device Name:{self._config.device},Device Entry:{async_signal_name}"
                    )
            elif config.source == "device_monitor_2d":
                for scan_id in ids_to_check:
                    if scan_id is None:
                        continue
                    self.bec_dispatcher.disconnect_slot(
                        self.on_image_update_2d,
                        MessageEndpoints.device_async_signal(
                            scan_id, self._config.device, async_signal_name
                        ),
                    )
                    logger.info(
                        f"Disconnecting 2d update ScanID:{scan_id}, Device Name:{self._config.device},Device Entry:{async_signal_name}"
                    )

        else:
            if config.source == "device_monitor_1d":
                self.bec_dispatcher.disconnect_slot(
                    self.on_image_update_1d,
                    MessageEndpoints.device_preview(self._config.device, self._config.signal),
                )
                logger.info(
                    f"Disconnecting preview 1d update Device Name:{self._config.device}, Device Entry:{self._config.signal}"
                )
            elif config.source == "device_monitor_2d":
                self.bec_dispatcher.disconnect_slot(
                    self.on_image_update_2d,
                    MessageEndpoints.device_preview(self._config.device, self._config.signal),
                )
                logger.info(
                    f"Disconnecting preview 2d update Device Name:{self._config.device}, Device Entry:{self._config.signal}"
                )

        # Reset async state
        self.async_update = False
        config.async_signal_name = None
        self._set_connection_status("disconnected")

    ################################################################################
    # High Level methods for API
    ################################################################################
    @SafeSlot(popup_error=True)
    def image(
        self,
        device: str | None = None,
        signal: str | None = None,
        color_map: str | None = None,
        color_bar: Literal["simple", "full"] | None = None,
        vrange: tuple[int, int] | None = None,
    ) -> ImageItem | None:
        """
        Set the image source and update the image.

        Args:
            device(str|None): The name of the device to monitor. If None or empty string, the current monitor will be disconnected.
            signal(str|None): The signal/entry name to monitor on the device.
            color_map(str): The color map to use for the image.
            color_bar(str): The type of color bar to use. Options are "simple" or "full".
            vrange(tuple): The range of values to use for the color map.

        Returns:
            ImageItem: The image object, or None if connection failed.
        """
        # Disconnect existing monitor if any
        if self._config.device and self._config.signal:
            self._disconnect_current_monitor()

        if not device or not signal:
            if device or signal:
                logger.warning("Both device and signal must be specified")
            else:
                logger.info("Disconnecting image monitor")
            self.device = ""
            return None

        # Validate device
        self.entry_validator.validate_monitor(device)

        # Clear old entry first to avoid reconnect attempts on the new device
        if self._config.signal:
            self.signal = ""

        # Set properties to trigger connection
        self.device = device
        self.signal = signal

        # Apply visual settings
        if color_map is not None:
            self.main_image.color_map = color_map
        if color_bar is not None:
            self.enable_colorbar(True, color_bar)
        if vrange is not None:
            self.vrange = vrange

        return self.main_image

    def _sync_device_selection(self):
        """
        Synchronize the device and signal comboboxes with the current monitor state.
        This ensures the toolbar reflects the device and signal properties.
        """
        try:
            device_selection_action = self.toolbar.components.get_action("device_selection")
        except Exception:  # noqa: BLE001 - toolbar might not be ready during early init
            logger.warning(f"Image ({self.object_name}) toolbar was not ready during init.")
            return

        if device_selection_action is None:
            return

        device_selection: DeviceSelection = device_selection_action.widget
        target_device = self._config.device or ""
        target_entry = self._config.signal or ""

        # Check if already synced
        if (
            device_selection.device_combo_box.currentText() == target_device
            and device_selection.signal_combo_box.currentText() == target_entry
        ):
            return

        device_selection.set_device_and_signal(target_device, target_entry)

    def _sync_signal_from_toolbar(self) -> None:
        """
        Pull the signal selection from the toolbar if it differs from the current signal.
        This keeps CLI-driven device updates in sync with the signal combobox state.
        """
        if self._device_selection_updating:
            return

        if not self._config.device:
            return

        try:
            device_selection_action = self.toolbar.components.get_action("device_selection")
        except Exception:  # noqa: BLE001 - toolbar might not be ready during early init
            return

        if device_selection_action is None:
            return

        device_selection: DeviceSelection = device_selection_action.widget
        if device_selection.device_combo_box.currentText() != self._config.device:
            return

        signal_text = device_selection.signal_combo_box.currentText()
        if not signal_text or signal_text == self._config.signal:
            return

        signal_config = device_selection.signal_combo_box.get_signal_config()
        if not signal_config:
            try:
                device_obj = self.dev[self._config.device]
                signal_config = device_obj._info["signals"].get(signal_text, {})
            except (KeyError, AttributeError):
                signal_config = None

        if not signal_config:
            return

        self._signal_configs["main"] = signal_config
        self._device_selection_updating = True
        try:
            self.signal = signal_text
        finally:
            self._device_selection_updating = False

    def _set_connection_status(self, status: str, message: str | None = None) -> None:
        self._config.connection_status = status
        self._config.connection_error = message
        self.property_changed.emit("connection_status", status)
        self.property_changed.emit("connection_error", message or "")

    ################################################################################
    # Post Processing
    ################################################################################

    @SafeProperty(bool, auto_emit=True)
    def fft(self) -> bool:
        """
        Whether FFT postprocessing is enabled.
        """
        return self.main_image.fft

    @fft.setter
    def fft(self, enable: bool):
        """
        Set FFT postprocessing.

        Args:
            enable(bool): Whether to enable FFT postprocessing.
        """
        self.main_image.fft = enable

    @SafeProperty(bool, auto_emit=True)
    def log(self) -> bool:
        """
        Whether logarithmic scaling is applied.
        """
        return self.main_image.log

    @log.setter
    def log(self, enable: bool):
        """
        Set logarithmic scaling.

        Args:
            enable(bool): Whether to enable logarithmic scaling.
        """
        self.main_image.log = enable

    @SafeProperty(int)
    def num_rotation_90(self) -> int:
        """
        The number of 90° rotations to apply counterclockwise.
        """
        return self.main_image.num_rotation_90

    @num_rotation_90.setter
    def num_rotation_90(self, value: int):
        """
        Set the number of 90° rotations to apply counterclockwise.

        Args:
            value(int): The number of 90° rotations to apply.
        """
        self.main_image.num_rotation_90 = value

    @SafeProperty(bool, auto_emit=True)
    def transpose(self) -> bool:
        """
        Whether the image is transposed.
        """
        return self.main_image.transpose

    @transpose.setter
    def transpose(self, enable: bool):
        """
        Set the image to be transposed.

        Args:
            enable(bool): Whether to enable transposing the image.
        """
        self.main_image.transpose = enable

    ################################################################################
    # Image Update Methods
    ################################################################################

    ########################################
    # Connections

    @SafeSlot(dict, dict)
    def on_scan_status(self, msg: dict, meta: dict):
        """
        Initial scan status message handler, which is triggered at the beginning and end of scan.
        Needed for setup of AsyncSignal connections.

        Args:
            msg(dict): The message content.
            meta(dict): The message metadata.
        """
        current_scan_id = msg.get("scan_id", None)
        if current_scan_id is None:
            return
        self._handle_scan_change(current_scan_id)

    @SafeSlot(dict, dict)
    def on_scan_progress(self, msg: dict, meta: dict):
        """
        For setting async image readback during scan progress updates if widget is started later than scan.

        Args:
            msg(dict): The message content.
            meta(dict): The message metadata.
        """
        current_scan_id = meta.get("scan_id", None)
        if current_scan_id is None:
            return
        self._handle_scan_change(current_scan_id)

    def _handle_scan_change(self, current_scan_id: str):
        """
        Update internal scan ids and refresh async connections if needed.
        Also clears image buffers when scan changes.

        Args:
            current_scan_id (str): The current scan identifier.
        """
        if current_scan_id == self.scan_id:
            return

        # Scan ID changed - clear buffers and reset image
        self.old_scan_id = self.scan_id
        self.scan_id = current_scan_id

        # Clear image buffer for 1D data accumulation
        self.main_image.clear()
        if hasattr(self.main_image, "buffer"):
            self.main_image.buffer = []
            self.main_image.max_len = 0

        # Reset crosshair if present
        if self.crosshair is not None:
            self.crosshair.reset()

        # Reconnect async image subscription with new scan_id
        if self.async_update:
            self._setup_async_image(scan_id=self.scan_id)

    def _get_async_signal_name(self) -> tuple[str, str] | None:
        """
        Returns device and async signal names used for endpoints/messages.

        Returns:
            tuple[str, str] | None: (device, async_signal_name) or None if not available.
        """
        if not self._config.device or not self._config.signal:
            return None

        config = self.subscriptions["main"]
        async_signal = config.async_signal_name or self._config.signal
        return self._config.device, async_signal

    def _setup_async_image(self, scan_id: str | None):
        """
        (Re)connect async image readback for the current scan.

        Args:
            scan_id (str | None): The scan identifier to subscribe to.
        """
        if not self.async_update:
            return

        config = self.subscriptions["main"]
        async_names = self._get_async_signal_name()
        if async_names is None:
            logger.info("Async image setup skipped because monitor information is incomplete.")
            return

        device, async_signal = async_names
        if config.monitor_type == "1d":
            slot = self.on_image_update_1d
        elif config.monitor_type == "2d":
            slot = self.on_image_update_2d
        else:
            logger.warning(
                f"Async image setup skipped due to unsupported monitor type '{config.monitor_type}'."
            )
            return

        # Disconnect any previous scan subscriptions to avoid stale updates.
        for prev_scan_id in (self.old_scan_id, self.scan_id):
            if prev_scan_id is None:
                continue
            self.bec_dispatcher.disconnect_slot(
                slot, MessageEndpoints.device_async_signal(prev_scan_id, device, async_signal)
            )

        if scan_id is None:
            logger.info("Scan ID not available yet; delaying async image subscription.")
            return

        self.bec_dispatcher.connect_slot(
            slot,
            MessageEndpoints.device_async_signal(scan_id, device, async_signal),
            from_start=True,
            cb_info={"scan_id": scan_id},
        )
        logger.info(f"Setup async image for {device}.{async_signal} and scan {scan_id}.")

    def disconnect_monitor(self, device: str | None = None, signal: str | None = None):
        """
        Disconnect the monitor from the image update signals, both 1D and 2D.

        Args:
            device(str|None): The name of the device to disconnect. Defaults to current device.
            signal(str|None): The signal/entry name to disconnect. Defaults to current signal.
        """
        config = self.subscriptions["main"]
        target_device = device or self._config.device
        target_entry = signal or self._config.signal

        if not target_device or not target_entry:
            logger.warning("Cannot disconnect monitor without both device and signal")
            return

        if self.async_update:
            async_signal_name = config.async_signal_name or target_entry
            ids_to_check = [self.scan_id, self.old_scan_id]
            if config.source == "device_monitor_1d":
                for scan_id in ids_to_check:
                    if scan_id is None:
                        continue
                    self.bec_dispatcher.disconnect_slot(
                        self.on_image_update_1d,
                        MessageEndpoints.device_async_signal(
                            scan_id, target_device, async_signal_name
                        ),
                    )
            elif config.source == "device_monitor_2d":
                for scan_id in ids_to_check:
                    if scan_id is None:
                        continue
                    self.bec_dispatcher.disconnect_slot(
                        self.on_image_update_2d,
                        MessageEndpoints.device_async_signal(
                            scan_id, target_device, async_signal_name
                        ),
                    )
        else:
            if config.source == "device_monitor_1d":
                self.bec_dispatcher.disconnect_slot(
                    self.on_image_update_1d,
                    MessageEndpoints.device_preview(target_device, target_entry),
                )
            elif config.source == "device_monitor_2d":
                self.bec_dispatcher.disconnect_slot(
                    self.on_image_update_2d,
                    MessageEndpoints.device_preview(target_device, target_entry),
                )
            else:
                logger.warning(
                    f"Cannot disconnect monitor {target_device}.{target_entry} with source {self.subscriptions['main'].source}"
                )
                return

        self.subscriptions["main"].async_signal_name = None
        self.async_update = False
        self._sync_device_selection()

    ########################################
    # 1D updates

    @SafeSlot(dict, dict)
    def on_image_update_1d(self, msg: dict, metadata: dict):
        """
        Update the image with 1D data.
        For preview signals: metadata doesn't contain scan_id.
        For async signals: scan_id is managed via on_scan_status/on_scan_progress.

        Args:
            msg(dict): The message containing the data.
            metadata(dict): The metadata associated with the message.
        """
        try:
            image = self.main_image
        except Exception:
            return
        data = self._get_payload_data(msg)

        if data is None:
            logger.warning("No data received for image update from 1D.")
            return

        image_buffer = self.adjust_image_buffer(image, data)

        if self._color_bar is not None:
            self._color_bar.blockSignals(True)
        image.set_data(image_buffer)
        if self._color_bar is not None:
            self._color_bar.blockSignals(False)
        if self._autorange_on_next_update:
            self._autorange_on_next_update = False
            self.auto_range()
        self.image_updated.emit()

    @staticmethod
    def adjust_image_buffer(image: ImageItem, new_data: np.ndarray) -> np.ndarray:
        """
        Adjusts the image buffer to accommodate the new data, ensuring that all rows have the same length.

        Args:
            image: The image object (used to store a buffer list and max_len).
            new_data (np.ndarray): The new incoming 1D waveform data.

        Returns:
            np.ndarray: The updated image buffer with adjusted shapes.
        """
        new_len = new_data.shape[0]
        if not hasattr(image, "buffer"):
            image.buffer = []
            image.max_len = 0

        if new_len > image.max_len:
            image.max_len = new_len
            for i in range(len(image.buffer)):
                wf = image.buffer[i]
                pad_width = image.max_len - wf.shape[0]
                if pad_width > 0:
                    image.buffer[i] = np.pad(wf, (0, pad_width), mode="constant", constant_values=0)
            image.buffer.append(new_data)
        else:
            pad_width = image.max_len - new_len
            if pad_width > 0:
                new_data = np.pad(new_data, (0, pad_width), mode="constant", constant_values=0)
            image.buffer.append(new_data)

        image_buffer = np.array(image.buffer)
        return image_buffer

    ########################################
    # 2D updates

    @SafeSlot(dict, dict)
    def on_image_update_2d(self, msg: dict, metadata: dict):
        """
        Update the image with 2D data.

        Args:
            msg(dict): The message containing the data.
            metadata(dict): The metadata associated with the message.
        """
        try:
            image = self.main_image
        except Exception:
            return
        data = self._get_payload_data(msg)
        if data is None:
            logger.warning("No data received for image update from 2D.")
            return
        if self._color_bar is not None:
            self._color_bar.blockSignals(True)
        image.set_data(data)
        if self._color_bar is not None:
            self._color_bar.blockSignals(False)
        if self._autorange_on_next_update:
            self._autorange_on_next_update = False
            self.auto_range()
        self.image_updated.emit()

    def _get_payload_data(self, msg: dict) -> np.ndarray | None:
        """
        Extract payload from async/preview/monitor1D/2D message structures due to inconsistent formats in backend.

        Args:
            msg (dict): The incoming message containing data.
        """
        if not self.async_update:
            return msg.get("data")
        async_names = self._get_async_signal_name()
        if async_names is None:
            logger.warning("Async payload extraction failed; monitor info incomplete.")
            return None
        _, async_signal = async_names
        return msg.get("signals", {}).get(async_signal, {}).get("value", None)

    ################################################################################
    # Clean up
    ################################################################################

    @SafeSlot(str)
    def _on_layer_removed(self, layer_name: str):
        """
        Handle the removal of a layer by disconnecting the monitor.

        Args:
            layer_name(str): The name of the layer that was removed.
        """
        if layer_name not in self.subscriptions:
            return
        # For the main layer, disconnect current monitor
        if layer_name == "main" and self._config.device and self._config.signal:
            self._disconnect_current_monitor()
            self._config.device = ""
            self._config.signal = ""
            self._signal_configs.pop("main", None)

    def cleanup(self):
        """
        Disconnect the image update signals and clean up the image.
        """
        self.layer_removed.disconnect(self._on_layer_removed)

        # Disconnect current monitor
        if self._config.device and self._config.signal:
            self._disconnect_current_monitor()

        self.subscriptions.clear()

        # Toolbar cleanup - disconnect the device_selection bundle
        try:
            self.toolbar.disconnect_bundle("device_selection")
        except Exception:  # noqa: BLE001
            pass

        self.bec_dispatcher.disconnect_slot(self.on_scan_status, MessageEndpoints.scan_status())
        self.bec_dispatcher.disconnect_slot(self.on_scan_progress, MessageEndpoints.scan_progress())
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication, QHBoxLayout

    app = QApplication(sys.argv)
    apply_theme("dark")
    win = QWidget()
    win.setWindowTitle("Image Demo")
    ml = QHBoxLayout(win)

    image_popup = Image(popups=True)
    # image_side_panel = Image(popups=False)

    ml.addWidget(image_popup)
    # ml.addWidget(image_side_panel)

    win.resize(1500, 800)
    win.show()
    sys.exit(app.exec_())
