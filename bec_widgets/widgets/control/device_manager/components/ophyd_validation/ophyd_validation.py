"""
Module with a test widget that allows to run the ophyd_devices static tests
utilities for a device config test. Results are displayed in two lists (running, completed).
In addition, it allows to configure the test parameters.

-> Connect: Try to establish a connection to the device
-> Timeout: Timeout for connection attempt. Default here is 5s.
-> Force Connect: To force connection even if already connected.
                  Mostly relevant for ADBase integrations.
"""

import queue
import weakref
from typing import Any
from uuid import uuid4

from bec_lib.atlas_models import Device as DeviceModel
from bec_lib.logger import bec_logger
from qtpy import QtCore, QtWidgets

from bec_widgets.utils.bec_list import BECList
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.widgets.control.device_manager.components.ophyd_validation import (
    ConfigStatus,
    ConnectionStatus,
    DeviceTestModel,
    ValidationButton,
    ValidationListItem,
    format_error_to_md,
    get_validation_icons,
)

READY_TO_TEST = False

logger = bec_logger.logger

try:
    import bec_server  # type: ignore
    import ophyd_devices  # type: ignore

    READY_TO_TEST = True
except ImportError:
    logger.warning(f"Optional dependencies not available: {ImportError}")
    ophyd_devices = None
    bec_server = None

try:
    from ophyd_devices.utils.static_device_test import StaticDeviceTest
except ImportError:
    StaticDeviceTest = None


class DeviceTestResult(QtCore.QObject):
    """Simple object to inject device validation signal to DeviceTest QRunnable."""

    # ValidationResult: device_config, config_status, connection_status, error_message
    device_validated = QtCore.Signal(dict, int, int, str)
    device_validation_started = QtCore.Signal(str)


class DeviceTest(QtCore.QRunnable):
    """QRunnable to run a device test in the QT thread pool."""

    def __init__(
        self,
        device_model: DeviceTestModel,
        enable_connect: bool,
        force_connect: bool,
        timeout: float,
    ):
        super().__init__()
        self.uuid = device_model.uuid
        test_config = {device_model.device_name: device_model.device_config}
        self.tester = StaticDeviceTest(config_dict=test_config)
        self.signals = DeviceTestResult()
        self.device_config = device_model.device_config
        self.enable_connect = enable_connect
        self.force_connect = force_connect
        self.timeout = timeout
        self._cancelled = False

    def cancel(self):
        """Cancel the device test."""
        self._cancelled = True

    def run(self):
        """Run the device test."""
        if not READY_TO_TEST:
            logger.error("Cannot run device test: dependencies not available.")
            return
        device_name = self.device_config.get("name", "")
        self.signals.device_validation_started.emit(device_name)  # Emit started signal
        if self._cancelled:
            logger.debug("Device test cancelled before start.")
            self.signals.device_validated.emit(
                self.device_config,
                ConfigStatus.UNKNOWN.value,
                ConnectionStatus.UNKNOWN.value,
                f"{self.device_config.get('name')} was cancelled by user.",
            )
            return
        results = self.tester.run_with_list_output(
            connect=self.enable_connect,
            force_connect=self.force_connect,
            timeout_per_device=self.timeout,
        )
        if not results:
            self.signals.device_validated.emit(
                self.device_config,
                ConfigStatus.UNKNOWN.value,
                ConnectionStatus.UNKNOWN.value,
                "Results from OphydDevices StaticDeviceTest are empty.",
            )
            return
        try:
            config_is_valid = int(results[0].config_is_valid)
            connection_status = (
                int(results[0].success) if self.enable_connect else ConnectionStatus.UNKNOWN.value
            )
            error_message = results[0].message or ""
            self.signals.device_validated.emit(
                self.device_config, config_is_valid, connection_status, error_message
            )
        except Exception as e:
            logger.error(f"Error reading results from device test: {e}")
            self.signals.device_validated.emit(
                self.device_config,
                ConfigStatus.UNKNOWN.value,
                ConnectionStatus.UNKNOWN.value,
                f"Error processing device test results: {e}",
            )


class ThreadPoolManager(QtCore.QObject):
    """
    Manager wrapping QThreadPool to expose a queue for jobs.
    It allows queued jobs to be cancelled if they have not yet started.

    Args:
        max_workers (int): Maximum number of concurrent workers.
        poll_interval_ms (int): Poll interval in milliseconds to check for new jobs.
    """

    validations_are_running = QtCore.Signal(bool)
    device_validation_started = QtCore.Signal(str)
    device_validated = QtCore.Signal(dict, int, int, str)

    def __init__(self, parent=None, max_workers: int = 4, poll_interval_ms: int = 100):
        super().__init__(parent=parent)
        self.pool = QtCore.QThreadPool(parent=parent)
        self.pool.setMaxThreadCount(max_workers)

        self._queue = queue.Queue()
        self._timer = QtCore.QTimer(parent=parent)
        self._timer.timeout.connect(self._process_queue)
        self.poll_interval_ms = poll_interval_ms
        self._timer.setInterval(self.poll_interval_ms)
        self._active_tests: dict[str, weakref.ReferenceType[DeviceTest]] = {}

    def start_polling(self):
        """Start the polling timer."""
        if not self._timer.isActive():
            self._timer.start()

    def stop_polling(self):
        """Stop the polling timer."""
        if self._timer.isActive():
            self._timer.stop()

    def _emit_device_validation_started(self, device_name: str):
        """Emit device validation started signal."""
        self.device_validation_started.emit(device_name)

    def _emit_device_validated(
        self, device_config: dict, config_status: int, connection_status: int, error_message: str
    ):
        """Emit device validated signal."""
        self.device_validated.emit(device_config, config_status, connection_status, error_message)

    def submit(self, device_name: str, device_test: DeviceTest):
        """Queue a job for execution."""
        device_test.signals.device_validation_started.connect(self._emit_device_validation_started)
        device_test.signals.device_validated.connect(self._emit_device_validated)
        self._queue.put((device_name, device_test))

    def clear_device_in_queue(self, device_name: str):
        """Remove a specific device test from the queue."""
        if device_name in self._active_tests:
            try:
                ref = self._active_tests.pop(device_name)
                obj = ref()
                if obj and hasattr(obj, "cancel"):
                    obj.cancel()
                    obj.signals.device_validated.disconnect()
            except KeyError:
                logger.debug(f"Device {device_name} not found in active tests during cancellation.")
            return

        with self._queue.mutex:
            for name, runnable in self._queue.queue:
                if name == device_name:  # found the device to remove, discard it
                    runnable.cancel()
                    runnable.signals.device_validated.disconnect()
                    self._queue.queue = queue.deque(
                        item for item in self._queue.queue if item[0] != device_name
                    )
                    break

    def clear_queue(self):
        """Remove all queued (not yet started) jobs."""
        running = self.get_active_tests()
        scheduled = self.get_scheduled_tests()
        for device_name in running + scheduled:
            self.clear_device_in_queue(device_name)

    def get_active_tests(self) -> list[str]:
        """Return a list of currently active test device names."""
        return list(self._active_tests.keys())

    def get_scheduled_tests(self) -> list[str]:
        """Return a list of currently scheduled (queued) test device names."""
        with self._queue.mutex:
            return [device_name for device_name, _ in list(self._queue.queue)]

    def _process_queue(self):
        """Start new jobs if there is capacity. Runs with specified poll interval."""
        while not self._queue.empty() and len(self._active_tests) < self.pool.maxThreadCount():
            device_name, runnable = self._queue.get()
            runnable.signals.device_validated.connect(self._on_task_finished)
            self._active_tests[device_name] = weakref.ref(runnable)
            self.pool.start(runnable)
        self.validations_are_running.emit(len(self._active_tests) > 0)

    @SafeSlot(dict, int, int, str)
    def _on_task_finished(
        self, device_config: dict, config_status: int, connection_status: int, error_message: str
    ):
        """Handle task finished signal to update active thread count."""
        device_name = device_config.get("name", None)
        if device_name:
            self._active_tests.pop(device_name, None)


class LegendLabel(QtWidgets.QWidget):
    """Wrapper widget for legend labels with icon and text for OphydValidation."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._icons = get_validation_icons(
            colors=get_accent_colors(), icon_size=(18, 18), convert_to_pixmap=False
        )
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(8)

        # Config Status Legend
        config_legend = QtWidgets.QLabel("Config Legend:")
        layout.addWidget(config_legend, 0, 0)
        for ii, status in enumerate(
            [ConfigStatus.UNKNOWN, ConfigStatus.INVALID, ConfigStatus.VALID]
        ):
            icon = self._icons["config_status"][status]
            icon_widget = ValidationButton(parent=self, icon=icon)
            icon_widget.setEnabled(False)
            icon_widget.set_enabled_style(False)
            icon_widget.setToolTip(f"Device Configuration: {status.description()}")
            layout.addWidget(icon_widget, 0, ii + 1)

        # Connection Status Legend
        connection_status_legend = QtWidgets.QLabel("Connect Legend:")
        layout.addWidget(connection_status_legend, 1, 0)
        for ii, status in enumerate(
            [
                ConnectionStatus.UNKNOWN,
                ConnectionStatus.CANNOT_CONNECT,
                ConnectionStatus.CAN_CONNECT,
                ConnectionStatus.CONNECTED,
            ]
        ):
            icon = self._icons["connection_status"][status]
            icon_widget = ValidationButton(parent=self, icon=icon)
            icon_widget.setEnabled(False)
            icon_widget.set_enabled_style(False)
            icon_widget.setToolTip(f"Connection Status: {status.description()}")
            layout.addWidget(icon_widget, 1, ii + 1)
        layout.setColumnStretch(layout.columnCount(), 1)  # Counts as a column


class OphydValidation(BECWidget, QtWidgets.QWidget):
    """
    Widget to manage and run ophyd device tests.

    Args:
        parent (QWidget, optional): Parent widget. Defaults to None.
        client (BECClient, optional): BEC client instance. Defaults to None.
        hide_legend (bool, optional): Whether to hide the legend. Defaults to False.
    """

    RPC = False

    # ValidationResult: device_config, config_status, connection_status, error_message
    validation_completed = QtCore.Signal(dict, int, int, str)
    # ValidationResult: device_name, config_status, connection_status, error_message, formatted_error_message
    item_clicked = QtCore.Signal(str, int, int, str, str)
    # Signal to indicate if validations are currently running
    validations_are_running = QtCore.Signal(bool)
    # Signal to emit list of ValidationResults (device_config, config_status, connection_status, error_message) at once
    multiple_validations_completed = QtCore.Signal(list)

    def __init__(self, parent=None, client=None, hide_legend: bool = False):
        super().__init__(parent=parent, client=client, theme_update=True)
        self._running_ophyd_tests = False
        if not READY_TO_TEST:
            self.setDisabled(True)
            self.thread_pool_manager = None
        else:
            self.thread_pool_manager = ThreadPoolManager(parent=self, max_workers=4)
            self.thread_pool_manager.validations_are_running.connect(self._set_running_ophyd_tests)
            self.thread_pool_manager.device_validated.connect(self._on_device_test_completed)
            self.thread_pool_manager.device_validation_started.connect(
                self._trigger_validation_started
            )

        self._validation_icons = get_validation_icons(
            colors=get_accent_colors(), icon_size=(32, 32), convert_to_pixmap=False
        )

        self._main_layout = QtWidgets.QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(4)
        self._colors = get_accent_colors()

        # Setup main UI
        self.list_widget = self._create_list_widget_with_label("Running & Failed Validations")
        if not hide_legend:
            legend_widget = LegendLabel(parent=self)
            self._main_layout.addWidget(legend_widget)
        self._thread_pool_poll_loop()

    def apply_theme(self, theme: str):
        """Apply the current theme to the widget."""
        self._colors = get_accent_colors()
        # TODO consider removing as accent colors are the same across themes, or am I wrong?
        self._stop_validation_button.setStyleSheet(
            f"background-color: {self._colors.emergency.name()}; color: white; font-weight: bold; padding: 4px;"
        )

    def _thread_pool_poll_loop(self):
        """Start the thread pool polling loop."""
        if self.thread_pool_manager:
            self.thread_pool_manager.start_polling()

    def _create_list_widget_with_label(self, label_text: str) -> BECList:
        """Setup the running validations section."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Section title
        title_layout = QtWidgets.QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_label = QtWidgets.QLabel(label_text)
        title_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 2px;")
        status_label = QtWidgets.QLabel("Config | Connect")
        status_label.setStyleSheet("font-weight: bold; font-size: 9px; padding: 2px;")
        title_layout.addWidget(title_label)
        title_layout.addStretch(1)
        title_layout.addWidget(status_label)
        layout.addLayout(title_layout)

        # Separator line
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(separator)

        # List widget for running validations
        list_w = BECList(parent=self)
        list_w.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        list_w.itemClicked.connect(self._on_item_clicked)
        list_w.currentItemChanged.connect(self._on_current_item_changed)
        layout.addWidget(list_w)

        # Stop Running validation button
        self._stop_validation_button = QtWidgets.QPushButton("Stop Running Validations")
        self._stop_validation_button.clicked.connect(self.cancel_all_validations)
        self._stop_validation_button.setStyleSheet(
            f"background-color: {self._colors.emergency.name()}; color: white; font-weight: bold; padding: 4px;"
        )
        self._stop_validation_button.setVisible(False)
        layout.addWidget(self._stop_validation_button)
        self.validations_are_running.connect(self._stop_validation_button.setVisible)
        self._main_layout.addWidget(widget)

        return list_w

    ##########################
    ### Event Handlers
    ##########################

    @SafeSlot(bool)
    def _set_running_ophyd_tests(self, running: bool):
        """Set the running ophyd tests state."""
        self.running_ophyd_tests = running

    @SafeSlot(QtWidgets.QListWidgetItem, QtWidgets.QListWidgetItem)
    def _on_current_item_changed(
        self, current: QtWidgets.QListWidgetItem, previous: QtWidgets.QListWidgetItem
    ):
        """Handle current item changed."""
        widget: ValidationListItem = self.list_widget.get_widget_for_item(current)
        if widget:
            self._emit_item_clicked(widget)

    @SafeSlot(QtWidgets.QListWidgetItem)
    def _on_item_clicked(self, item: QtWidgets.QListWidgetItem):
        """Handle click on running item."""
        widget: ValidationListItem = self.list_widget.get_widget_for_item(item)
        if widget:
            self._emit_item_clicked(widget)

    def _emit_item_clicked(self, widget: ValidationListItem):
        format_error_msg = format_error_to_md(
            widget.device_model.device_name, widget.device_model.validation_msg
        )
        self.item_clicked.emit(
            widget.device_model.device_name,
            widget.device_model.config_status,
            widget.device_model.connection_status,
            widget.device_model.validation_msg,
            format_error_msg,
        )

    ###########################
    ### Properties
    ###########################

    @SafeProperty(bool, notify=validations_are_running)
    # pylint: disable=method-hidden
    def running_ophyd_tests(self) -> bool:
        """Indicates if validations are currently running."""
        return self._running_ophyd_tests

    @running_ophyd_tests.setter
    def running_ophyd_tests(self, value: bool) -> None:
        if self._running_ophyd_tests != value:
            self._running_ophyd_tests = value
            self.validations_are_running.emit(value)

    ###########################
    ### Public Methods
    ###########################

    @SafeSlot()
    def clear_all(self):
        """Clear all running and failed validations."""
        self.thread_pool_manager.clear_queue()
        self.list_widget.clear_widgets()

    def get_device_configs(self) -> list[dict[str, Any]]:
        """
        Get the current device configurations being tested.

        Returns:
            list[dict[str, Any]]: List of device configurations.
        """
        widgets: list[ValidationListItem] = self.list_widget.get_widgets()
        return [widget.device_model.device_config for widget in widgets]

    @SafeSlot(list, bool, bool)
    def device_table_config_changed(
        self, device_configs: list[dict[str, Any]], added: bool, skip_validation: bool
    ) -> None:
        """Slot to handle device config changes in the device table."""
        self.change_device_configs(
            device_configs=device_configs, added=added, skip_validation=skip_validation
        )

    @SafeSlot(list, bool)
    @SafeSlot(list, bool, bool)
    @SafeSlot(list, bool, bool, bool, float)
    @SafeSlot(list, bool, bool, bool, float, bool)
    def change_device_configs(
        self,
        device_configs: list[dict[str, Any]],
        added: bool,
        connect: bool = False,
        force_connect: bool = False,
        timeout: float = 5.0,
        skip_validation: bool = False,
    ) -> None:
        """
        Change the device configuration to test. If added is False, existing devices are removed.
        Device tests will be removed based on device names. No duplicates are allowed.

        For validation runs, results are emitted via the validation_completed signal. Unless devices
        are already in the running session with the same config, in which case the combined results
        of all such devices are emitted via the multiple_validations_completed signal. NOTE Please make
        sure to connect to both signals if you want to capture all results.

        Args:
            device_configs (list[dict[str, Any]]): List of device configurations.
            added (bool): Whether the devices are added to the existing list.
            connect (bool, optional): Whether to attempt connection during validation. Defaults to False.
            force_connect (bool, optional): Whether to force connection during validation. Defaults to False.
            timeout (float, optional): Timeout for connection attempt. Defaults to 5.0.
        """
        if not READY_TO_TEST:
            logger.error("Cannot change device configs: dependencies not available.")
            return
        # Track all devices that are already in the running session from the
        # config updates to avoid sending multiple single device validation signals.
        # Sending successive single updates may affect the UI performance on the receiving end.
        devices_already_in_session = []
        for cfg in device_configs:
            device_name = cfg.get("name", None)
            if device_name is None:  # Config missing name, will be skipped..
                logger.error(f"Device config missing 'name': {cfg}. Config will be skipped.")
                continue
            if not added or skip_validation is True:  # Remove requested
                self._remove_device_config(cfg)
                continue
            if self._is_device_in_redis_session(cfg.get("name"), cfg):
                logger.debug(
                    f"Device {device_name} already in running session with same config. Skipping."
                )
                devices_already_in_session.append(
                    (
                        cfg,
                        ConfigStatus.VALID.value,
                        ConnectionStatus.CONNECTED.value,
                        "Device already in session.",
                    )
                )
                self._remove_device_config(cfg)
                continue
            if not self._device_already_exists(cfg.get("name")):  # New device case
                self._add_device_config(
                    cfg, connect=connect, force_connect=force_connect, timeout=timeout
                )
            else:  # Update existing, but removing first
                logger.info(f"Device {cfg.get('name')} already exists, re-adding it.")
                self._remove_device_config(cfg)
                self._add_device_config(
                    cfg, connect=connect, force_connect=force_connect, timeout=timeout
                )
        # Send out batch of updates for devices already in session
        if devices_already_in_session:
            # NOTE: Use singleShot here to ensure that the signal is emitted after all other scheduled
            # tasks in the event loop are processed. This avoids potential deadlocks. In particular,
            # this is relevant for the DeviceFormDialog which opens a modal dialog during validation
            # and therefore must not have the signal emitted immediately in the same event loop iteration.
            # Otherwise, the dialog would block signal processing.
            QtCore.QTimer.singleShot(
                0, lambda: self.multiple_validations_completed.emit(devices_already_in_session)
            )

    def cancel_validation(self, device_name: str) -> None:
        """Cancel a running validation for a specific device.

        Args:
            device_name (str): Name of the device to cancel validation for.
        """
        if not READY_TO_TEST:
            logger.error("Cannot cancel validation: dependencies not available.")
            return
        if self.thread_pool_manager:
            self.thread_pool_manager.clear_device_in_queue(device_name)
        widget: ValidationListItem = self.list_widget.get_widget(device_name)
        if widget:
            self._on_device_test_completed(
                widget.device_model.device_config,
                ConfigStatus.UNKNOWN.value,
                ConnectionStatus.UNKNOWN.value,
                f"{widget.device_model.device_name} was cancelled by user.",
            )

    def cancel_all_validations(self) -> None:
        """Cancel all running validations."""
        if not READY_TO_TEST:
            logger.error("Cannot cancel validations: dependencies not available.")
            return
        running = self.thread_pool_manager.get_active_tests()
        scheduled = self.thread_pool_manager.get_scheduled_tests()
        for device_name in running + scheduled:
            self.cancel_validation(device_name)

    #################
    ### Private methods
    #################

    def _device_already_exists(self, device_name: str) -> bool:
        return device_name in self.list_widget

    def _add_device_config(
        self, device_config: dict[str, Any], connect: bool, force_connect: bool, timeout: float
    ) -> None:
        device_name = device_config.get("name")
        # Check if device is in redis session with same config, if yes don't even bother testing..
        device_test_model = DeviceTestModel(
            uuid=f"device_test_{device_name}_uuid_{uuid4()}",
            device_name=device_name,
            device_config=device_config,
        )

        widget = ValidationListItem(
            parent=self, device_model=device_test_model, validation_icons=self._validation_icons
        )
        widget.request_rerun_validation.connect(self._on_request_rerun_validation)
        self.list_widget.add_widget_item(device_name, widget)
        self.__delayed_submit_test(widget, connect, force_connect, timeout)

    def _remove_device_config(self, device_config: dict[str, Any]) -> None:
        device_name = device_config.get("name")
        if not device_name:
            logger.error(f"Device config missing 'name': {device_config}. Cannot remove device.")
            return
        if not self._device_already_exists(device_name):
            logger.debug(
                f"Device with name {device_name} not found in OphydValidation, can't remove it."
            )
            return
        if self.thread_pool_manager:
            self.thread_pool_manager.clear_device_in_queue(device_name)
        self.list_widget.remove_widget_item(device_name)

    @SafeSlot(str, dict, bool, bool, float)
    def _on_request_rerun_validation(
        self,
        device_name: str,
        device_config: dict[str, Any],
        connect: bool,
        force_connect: bool,
        timeout: float,
    ) -> None:
        """Handle request to re-run validation for a device."""
        if not self._device_already_exists(device_name):
            logger.debug(
                f"Device with name {device_name} not found in OphydValidation, can't re-run."
            )
            return
        widget: ValidationListItem = self.list_widget.get_widget(device_name)
        if widget and not widget.is_running:
            self.__delayed_submit_test(widget, connect, force_connect, timeout)
        else:
            logger.debug(f"Device {device_name} is already running validation, cannot re-run.")

    def _emit_device_in_redis_session(self, device_config: dict) -> None:
        self.validation_completed.emit(
            device_config,
            ConfigStatus.VALID.value,
            ConnectionStatus.CONNECTED.value,
            f"{device_config.get('name')} is OK. Already loaded in running session.",
        )

    def __delayed_submit_test(
        self, widget: ValidationListItem, connect: bool, force_connect: bool, timeout: float
    ) -> None:
        """Delayed submission of device test to ensure UI updates."""
        QtCore.QTimer.singleShot(
            0, lambda: self._submit_test(widget, connect, force_connect, timeout)
        )

    def _submit_test(
        self, widget: ValidationListItem, connect: bool, force_connect: bool, timeout: float
    ) -> None:
        """Submit a device test to the thread pool."""
        if not READY_TO_TEST or StaticDeviceTest is None:
            logger.error("Cannot submit device test: dependencies not available.")
            return
        # Check if device is already in redis session with same config
        if self._is_device_in_redis_session(
            widget.device_model.device_name, widget.device_model.device_config
        ):
            logger.info(
                f"Device {widget.device_model.device_name} already in running session with same config. "
                "Skipping validation."
            )
            self.validation_completed.emit(
                widget.device_model.device_config,
                ConfigStatus.VALID.value,
                ConnectionStatus.CONNECTED.value,
                f"{widget.device_model.device_name} is OK. Already loaded in running session.",
            )
            # Remove widget from list as it's safe to assume it can be loaded.
            self._remove_device_config(widget.device_model.device_config)
            return
        runnable = DeviceTest(
            device_model=widget.device_model,
            enable_connect=connect,
            force_connect=force_connect,
            timeout=timeout,
        )
        widget.validation_scheduled()
        if self.thread_pool_manager:
            self.thread_pool_manager.submit(widget.device_model.device_name, runnable)

    def _trigger_validation_started(self, device_name: str) -> None:
        """Trigger validation started for a specific device."""
        widget: ValidationListItem = self.list_widget.get_widget(device_name)
        if widget:
            widget.validation_started()

    def _on_device_test_completed(
        self, device_config: dict, config_status: int, connection_status: int, error_message: str
    ) -> None:
        """Handle device test completion."""
        device_name = device_config.get("name")
        if not self._device_already_exists(device_name):
            logger.debug(f"Received test result for unknown device {device_name}. Ignoring.")
            return
        if config_status == ConfigStatus.VALID.value and connection_status in [
            ConnectionStatus.CONNECTED.value,
            ConnectionStatus.CAN_CONNECT.value,
        ]:
            # Validated successfully, remove item from running list
            self.list_widget.remove_widget_item(device_name)
            self.validation_completed.emit(
                device_config, config_status, connection_status, error_message
            )
            return
        widget = self.list_widget.get_widget(device_name)
        if widget:
            widget.on_validation_finished(
                validation_msg=error_message,
                config_status=config_status,
                connection_status=connection_status,
            )
            self.validation_completed.emit(
                device_config, config_status, connection_status, error_message
            )

    def _is_device_in_redis_session(self, device_name: str, device_config: dict) -> bool:
        """Check if a device is in the running section."""
        dev_obj = self.client.device_manager.devices.get(device_name, None)
        if dev_obj is None or dev_obj.enabled is False:
            return False
        return self._compare_device_configs(dev_obj._config, device_config)

    def _compare_device_configs(self, config1: dict, config2: dict) -> bool:
        """Compare two device configurations through the Device model in bec_lib.atlas_models.

        Args:
            config1 (dict): The first device configuration.
            config2 (dict): The second device configuration.

        Returns:
            bool: True if the configurations are equivalent, False otherwise.
        """
        try:
            model1 = DeviceModel.model_validate(config1)
            model2 = DeviceModel.model_validate(config2)
            return model1 == model2
        except Exception:
            return False


if __name__ == "__main__":  # pragma: no cover
    import sys

    app = QtWidgets.QApplication(sys.argv)
    import os
    import random

    import bec_lib
    from bec_lib.bec_yaml_loader import yaml_load
    from bec_lib.plugin_helper import plugin_package_name, plugin_repo_path
    from bec_qthemes import apply_theme

    apply_theme("light")
    # Main widget
    wid = QtWidgets.QWidget()
    w_layout = QtWidgets.QVBoxLayout(wid)
    w_layout.setContentsMargins(0, 0, 0, 0)
    w_layout.setSpacing(0)
    wid.setLayout(w_layout)
    # Check if plugin is installed

    plugin_path = plugin_repo_path()
    plugin_name = plugin_package_name()
    cfgs = [""]
    cfgs.extend([os.path.join(os.path.dirname(bec_lib.__file__), "configs", "demo_config.yaml")])
    if plugin_path:
        print(f"Adding configs from plugin {plugin_name} at {plugin_path}")
        cfg_base_path = os.path.join(plugin_path, plugin_name, "device_configs")
        config_files = os.listdir(cfg_base_path)
        cfgs.extend(
            [os.path.join(cfg_base_path, f) for f in config_files if f.endswith((".yaml", ".yml"))]
        )

    combo_box_configs = QtWidgets.QComboBox()
    combo_box_configs.addItems(cfgs)
    combo_box_configs.setCurrentIndex(0)

    but_layout = QtWidgets.QHBoxLayout()
    but_layout.addWidget(combo_box_configs)
    button_reset = QtWidgets.QPushButton("Clear All")
    but_layout.addWidget(button_reset)
    button_clear_random = QtWidgets.QPushButton("Clear random amount")
    but_layout.addWidget(button_clear_random)
    w_layout.addLayout(but_layout)

    def _load_config(config_path: str):
        current_config = device_manager_ophyd_test.get_device_configs()
        device_manager_ophyd_test.change_device_configs(current_config, False)
        if not config_path:  # empty escape
            return
        try:
            config = [{"name": k, **v} for k, v in yaml_load(config_path).items()]
            config.append({"name": "non_existing_device", "type": "NonExistingDevice"})
            device_manager_ophyd_test.change_device_configs(config, True, False, False, 2.0)
        except Exception as e:
            logger.error(f"Error loading config {config_path}: {e}")

    def _clear_random_entries():
        current_config = device_manager_ophyd_test.get_device_configs()
        n_remove = random.randint(1, len(current_config))
        to_remove = random.sample(current_config, n_remove)
        device_manager_ophyd_test.change_device_configs(to_remove, False)

    device_manager_ophyd_test = OphydValidation()
    button_reset.clicked.connect(device_manager_ophyd_test.clear_all)
    combo_box_configs.currentTextChanged.connect(_load_config)
    button_clear_random.clicked.connect(_clear_random_entries)

    w_layout.addWidget(device_manager_ophyd_test)

    # Add text box for results
    text_box = QtWidgets.QTextEdit()
    text_box.setReadOnly(True)
    w_layout.addWidget(text_box)

    def _validation_callback(
        device_name: str,
        config_status: int,
        connection_status: int,
        error_message: str,
        formatted_error_message: str,
    ):  # type: ignore
        text_box.setMarkdown(formatted_error_message)

    device_manager_ophyd_test.item_clicked.connect(_validation_callback)
    wid.resize(600, 1000)
    wid.show()
    sys.exit(app.exec_())
