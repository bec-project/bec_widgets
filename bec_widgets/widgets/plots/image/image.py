from __future__ import annotations

from collections import defaultdict
from typing import Literal

import numpy as np
from bec_lib import bec_logger
from pydantic import BaseModel, Field, field_validator
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.colors import Colors, apply_theme
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.qt_data_subscription import QtDataSubscription
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

    #: Retention cap for scan-less 1D preview streams (rows of the waterfall buffer).
    PREVIEW_1D_MAX_ROWS = 1000
    #: Retention cap for scan-less 2D preview streams (only the newest frame is shown).
    PREVIEW_2D_MAX_FRAMES = 2

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
        # Data delivery through the DataAPI (one bridge for the main layer).
        self._data_bridge: QtDataSubscription | None = None
        self._source_key: tuple[str, str] | None = None
        self._min_display_ordinal: int | None = None
        self.old_scan_id = None
        self.scan_id = None
        self.async_update = False

        super().__init__(
            parent=parent, config=config, client=client, gui_id=gui_id, popups=popups, **kwargs
        )
        self._device_selection_updating = False
        self._autorange_on_next_update = False
        self._init_toolbar_image()
        self.layer_removed.connect(self._on_layer_removed)

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
        old_signal = self._config.signal
        if old_device and old_signal and old_device != value:
            self._cleanup_data_api_subscription()
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

        old_signal = self._config.signal
        if self._config.device and old_signal and old_signal != value:
            self._cleanup_data_api_subscription()
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
        Internal method to setup the DataAPI subscription based on current
        device, signal, and signal_config.
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

        # Close any existing subscription first
        self._cleanup_data_api_subscription()

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

        if ndim not in (1, 2):
            logger.warning(
                f"Unsupported ndim '{ndim}' for monitor '{self._config.device}.{self._config.signal}'."
            )
            self._set_connection_status("error", f"Unsupported ndim '{ndim}'")
            return

        config = self.subscriptions["main"]
        self.async_update = False
        config.async_signal_name = None
        config.monitor_type = "1d" if ndim == 1 else "2d"
        config.source = "device_monitor_1d" if ndim == 1 else "device_monitor_2d"

        if signal_class == "PreviewSignal":
            # Scan-less device stream served by the DataAPI device plugin.
            scan = None
            entry = self._config.signal
            max_points = self.PREVIEW_1D_MAX_ROWS if ndim == 1 else self.PREVIEW_2D_MAX_FRAMES
        else:
            # Scan-scoped async stream; the DataAPI rebinds on new scans and
            # hands terminal scans over to history automatically.
            self.async_update = True
            config.async_signal_name = signal_config.get(
                "obj_name", f"{self._config.device}_{self._config.signal}"
            )
            scan = "live"
            entry = config.async_signal_name
            max_points = None

        try:
            self._data_bridge = QtDataSubscription(
                self.client,
                sources=[(self._config.device, entry)],
                scan=scan,
                parent=self,
                min_emit_interval=0.1,
                max_points=max_points,
            )
            self._data_bridge.updated.connect(self._on_data_update)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                f"Failed to configure image data subscription for "
                f"{self._config.device}.{self._config.signal}: {exc}"
            )
            self._cleanup_data_api_subscription()
            self._set_connection_status("error", str(exc))
            return

        self._source_key = (self._config.device, entry)
        self._min_display_ordinal = None
        self._set_connection_status("connected")
        logger.info(
            f"Connected to {self._config.device}.{self._config.signal} with type {config.monitor_type}"
        )
        self._autorange_on_next_update = True

    def _cleanup_data_api_subscription(self):
        """Close the active DataAPI bridge, if any."""
        self._source_key = None
        self._min_display_ordinal = None
        if self._data_bridge is None:
            return
        try:
            self._data_bridge.close()
        finally:
            self._data_bridge = None

    def _disconnect_current_monitor(self):
        """
        Close the current DataAPI subscription and reset the async bookkeeping.
        """
        self._cleanup_data_api_subscription()

        # Reset async state
        config = self.subscriptions["main"]
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

    def disconnect_monitor(self, device: str | None = None, signal: str | None = None):
        """
        Disconnect the monitor from the image update stream, both 1D and 2D.

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

        if config.source not in {"device_monitor_1d", "device_monitor_2d"}:
            logger.warning(
                f"Cannot disconnect monitor {target_device}.{target_entry} with source {self.subscriptions['main'].source}"
            )
            return

        self._disconnect_current_monitor()
        self._sync_device_selection()

    @SafeSlot(object)
    def _on_data_update(self, update) -> None:
        """
        Render one columnar DataAPI update (live, backfill or history).

        2-D sources display the latest frame; 1-D sources rebuild the
        waterfall buffer from the columnar fragments (newest row last).

        Args:
            update (SubscriptionUpdate): Full-state columnar snapshot.
        """
        if self._source_key is None:
            return
        source = update.sources.get(self._source_key)
        if source is None or source.values is None or len(source.values) == 0:
            return
        self._handle_scan_rollover(update, source)
        if self.subscriptions["main"].monitor_type == "2d":
            data = np.asarray(source.values[-1])
        else:
            data = self._build_1d_buffer(source)
        if data is None:
            return
        self._render_image_data(data)

    @staticmethod
    def _effective_scan_id(update, source) -> str | None:
        """
        The scan id an update belongs to: the bound scan for scan-scoped
        subscriptions, the last-seen scan id from the stream metadata for
        scan-less preview streams.

        Args:
            update (SubscriptionUpdate): The update snapshot.
            source (SourceData): The rendered source of the update.

        Returns:
            str | None: The scan id, or None if not known (yet).
        """
        if update.scan_id:
            return update.scan_id
        return source.metadata.get("scan_id")

    def _handle_scan_rollover(self, update, source) -> None:
        """
        Reset per-scan display state once the data belongs to a new scan.

        Scan-scoped subscriptions deliver fresh per-scan series, so only the
        bookkeeping and the crosshair need a reset. Scan-less preview streams
        retain pre-rollover points; the display window is restricted to the
        newest point (the one that carried the new scan id) onward.

        Args:
            update (SubscriptionUpdate): The update snapshot.
            source (SourceData): The rendered source of the update.
        """
        scan_id = self._effective_scan_id(update, source)
        if scan_id is None or scan_id == self.scan_id:
            return
        previous = self.scan_id
        self.old_scan_id = previous
        self.scan_id = scan_id
        if previous is None:
            return
        if source.kind == "unindexed" and source.ordinals:
            self._min_display_ordinal = source.ordinals[-1]
        if self.crosshair is not None:
            self.crosshair.reset()

    def _build_1d_buffer(self, source) -> np.ndarray | None:
        """
        Rebuild the 2-D waterfall buffer from the 1-D columnar fragments of a
        source: one row per ordinal, rows zero-padded to the longest row,
        newest row last. Covers async 'add' (one fragment per ordinal),
        'add_slice' (accumulated row per ordinal), 'replace' (single current
        state) and preview streams (one waveform per arrival) alike.

        Args:
            source (SourceData): The 1-D source snapshot.

        Returns:
            np.ndarray | None: The (n_rows, max_len) buffer, or None if no
                displayable rows remain.
        """
        values = source.values
        if self._min_display_ordinal is not None:
            values = [
                value
                for ordinal, value in zip(source.ordinals, values)
                if ordinal >= self._min_display_ordinal
            ]
        rows = [np.atleast_1d(np.asarray(value)) for value in values]
        rows = [row for row in rows if row.ndim == 1]
        if not rows:
            return None
        max_len = max(row.shape[0] for row in rows)
        return np.array(
            [
                np.pad(row, (0, max_len - row.shape[0]), mode="constant", constant_values=0)
                for row in rows
            ]
        )

    def _render_image_data(self, data: np.ndarray) -> None:
        """
        Display the given data on the main image (shared render tail).

        Args:
            data (np.ndarray): The 2-D buffer or frame to render.
        """
        try:
            image = self.main_image
        except Exception:  # pylint: disable=broad-except
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

        # Close the DataAPI subscription
        self._cleanup_data_api_subscription()

        self.subscriptions.clear()

        # Toolbar cleanup - disconnect the device_selection bundle
        try:
            self.toolbar.disconnect_bundle("device_selection")
        except Exception:  # noqa: BLE001
            pass

        # Dispatcher slots are released by BECWidget.cleanup via disconnect_owner.
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
