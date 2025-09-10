"""Module to run a static tests for devices from a yaml config."""

from __future__ import annotations

import enum
import re
from collections import deque
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from html import escape
from threading import Event, RLock
from typing import Any, Iterable

from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from PySide6.QtCore import QThreadPool
from qtpy import QtCore, QtWidgets

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.utility.spinner.spinner import SpinnerWidget

READY_TO_TEST = False

logger = bec_logger.logger

try:
    import bec_server
    import ophyd_devices

    READY_TO_TEST = True
except ImportError:
    logger.warning(f"Optional dependencies not available: {ImportError}")
    ophyd_devices = None
    bec_server = None

try:
    from ophyd_devices.utils.static_device_test import StaticDeviceTest
except ImportError:
    StaticDeviceTest = None


class ValidationStatus(int, enum.Enum):
    """Validation status for device configurations."""

    PENDING = 0  # colors.default
    VALID = 1  # colors.highlight
    FAILED = 2  # colors.emergency


class DeviceValidationResult(QtCore.QObject):
    """Simple object to inject validation signals into QRunnable."""

    # Device validation signal, device_name, ValidationStatus as int, error message or ''
    device_validated = QtCore.Signal(str, bool, str)


class DeviceTester(QtCore.QRunnable):
    def __init__(self, config: dict) -> None:
        super().__init__()
        self.signals = DeviceValidationResult()
        self.shutdown_event = Event()

        self._config = config

        self._max_threads = 4
        self._pending_event = Event()
        self._lock = RLock()
        self._test_executor = ThreadPoolExecutor(self._max_threads, "device_manager_tester")

        self._pending_queue: deque[tuple[str, dict]] = deque([])
        self._active: set[str] = set()

        QtWidgets.QApplication.instance().aboutToQuit.connect(lambda: self.shutdown_event.set())

    def run(self):
        if StaticDeviceTest is None:
            logger.error("Ophyd devices or bec_server not available, cannot run validation.")
            return
        while not self.shutdown_event.is_set():
            self._pending_event.wait(timeout=0.5)  # check if shutting down every 0.5s
            if len(self._active) >= self._max_threads:
                self._pending_event.clear()  # it will be set again on removing something from active
                continue
            with self._lock:
                if len(self._pending_queue) > 0:
                    item, cfg = self._pending_queue.pop()
                    self._active.add(item)
                    fut = self._test_executor.submit(self._run_test, item, {item: cfg})
                    fut.__dict__["__device_name"] = item
                    fut.add_done_callback(self._done_cb)
            self._safe_check_and_clear()

        self._cleanup()

    def submit(self, devices: Iterable[tuple[str, dict]]):
        with self._lock:
            self._pending_queue.extend(devices)
            self._pending_event.set()

    @staticmethod
    def _run_test(name: str, config: dict) -> tuple[str, bool, str]:
        tester = StaticDeviceTest(config_dict=config)  # type: ignore # we exit early if it is None
        results = tester.run_with_list_output(connect=False)
        return name, results[0].success, results[0].message

    def _safe_check_and_clear(self):
        with self._lock:
            if len(self._pending_queue) == 0:
                self._pending_event.clear()

    def _safe_remove_from_active(self, name: str):
        with self._lock:
            self._active.remove(name)
            self._pending_event.set()  # check again once a completed task is removed

    def _done_cb(self, future: Future):
        try:
            name, success, message = future.result()
        except CancelledError:
            return
        except Exception as e:
            name, success, message = future.__dict__["__device_name"], False, str(e)
        finally:
            self._safe_remove_from_active(future.__dict__["__device_name"])
        self.signals.device_validated.emit(name, success, message)

    def _cleanup(self): ...


class ValidationListItem(QtWidgets.QWidget):
    """Custom list item widget showing device name and validation status."""

    def __init__(self, device_name: str, device_config: dict, parent=None):
        """
        Initialize the validation list item.

        Args:
            device_name (str): The name of the device.
            device_config (dict): The configuration of the device.
            validation_colors (dict[ValidationStatus, QtGui.QColor]): The colors for each validation status.
            parent (QtWidgets.QWidget, optional): The parent widget.
        """
        super().__init__(parent)
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 2, 2)
        self.main_layout.setSpacing(4)
        self.device_name = device_name
        self.device_config = device_config
        self.validation_msg = "Validation in progress..."
        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI for the list item."""
        label = QtWidgets.QLabel(self.device_name)
        self.main_layout.addWidget(label)
        self.main_layout.addStretch()
        self._spinner = SpinnerWidget(parent=self)
        self._spinner.speed = 80
        self._spinner.setFixedSize(24, 24)
        self.main_layout.addWidget(self._spinner)
        self._base_style = "font-weight: bold;"
        self.setStyleSheet(self._base_style)
        self._start_spinner()

    def _start_spinner(self):
        """Start the spinner animation."""
        self._spinner.start()
        QtWidgets.QApplication.processEvents()

    def _stop_spinner(self):
        """Stop the spinner animation."""
        self._spinner.stop()
        self._spinner.setVisible(False)

    @SafeSlot()
    def on_validation_restart(self):
        """Handle validation restart."""
        self.validation_msg = ""
        self._start_spinner()
        self.setStyleSheet("")  # Check if this works as expected

    @SafeSlot(str)
    def on_validation_failed(self, error_msg: str):
        """Handle validation failure."""
        self.validation_msg = error_msg
        colors = get_accent_colors()
        self._stop_spinner()
        self.main_layout.removeWidget(self._spinner)
        self._spinner.deleteLater()
        label = QtWidgets.QLabel("")
        icon = material_icon("error", color=colors.emergency, size=(24, 24))
        label.setPixmap(icon)
        self.main_layout.addWidget(label)


class DMOphydTest(BECWidget, QtWidgets.QWidget):
    """Widget to test device configurations using ophyd devices."""

    # Signal to emit the validation status of a device
    device_validated = QtCore.Signal(str, int)

    def __init__(self, parent=None, client=None):
        super().__init__(parent=parent, client=client)
        if not READY_TO_TEST:
            self.setDisabled(True)
            self.tester = None
        else:
            self.tester = DeviceTester({})
            self.tester.signals.device_validated.connect(self._on_device_validated)
            QThreadPool.globalInstance().start(self.tester)
        self._device_list_items: dict[str, QtWidgets.QListWidgetItem] = {}
        self._thread_pool = QtCore.QThreadPool(maxThreadCount=1)

        self._main_layout = QtWidgets.QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(4)

        # We add a splitter between the list and the text box
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self._main_layout.addWidget(self.splitter)

        self._setup_list_ui()
        self._setup_textbox_ui()

    def _setup_list_ui(self):
        """Setup the list UI."""
        self._list_widget = QtWidgets.QListWidget(self)
        self._list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.splitter.addWidget(self._list_widget)
        # Connect signals
        self._list_widget.currentItemChanged.connect(self._on_current_item_changed)

    def _setup_textbox_ui(self):
        """Setup the text box UI."""
        self._text_box = QtWidgets.QTextEdit(self)
        self._text_box.setReadOnly(True)
        self._text_box.setFocusPolicy(QtCore.Qt.NoFocus)
        self.splitter.addWidget(self._text_box)

    @SafeSlot(dict)
    def change_device_configs(self, device_configs: list[dict[str, Any]], added: bool) -> None:
        """Receive an update with device configs.

        Args:
            device_configs (list[dict[str, Any]]): The updated device configurations.
        """
        for cfg in device_configs:
            name = cfg.get("name", "<not found>")
            if added:
                if name in self._device_list_items:
                    continue
                if self.tester:
                    self._add_device(name, cfg)
                    self.tester.submit([(name, cfg)])
                continue
            if name not in self._device_list_items:
                continue
            self._remove_list_item(name)

    def _add_device(self, name, cfg):
        item = QtWidgets.QListWidgetItem(self._list_widget)
        widget = ValidationListItem(device_name=name, device_config=cfg)

        # wrap it in a QListWidgetItem
        item.setSizeHint(widget.sizeHint())
        self._list_widget.addItem(item)
        self._list_widget.setItemWidget(item, widget)
        self._device_list_items[name] = item

    def _remove_list_item(self, device_name: str):
        """Remove a device from the list."""
        # Get the list item
        item = self._device_list_items.pop(device_name)

        # Retrieve the custom widget attached to the item
        widget = self._list_widget.itemWidget(item)
        if widget is not None:
            widget.deleteLater()  # clean up custom widget

        # Remove the item from the QListWidget
        row = self._list_widget.row(item)
        self._list_widget.takeItem(row)

    @SafeSlot(str, bool, str)
    def _on_device_validated(self, device_name: str, success: bool, message: str):
        """Handle the device validation result.

        Args:
            device_name (str): The name of the device.
            success (bool): Whether the validation was successful.
            message (str): The validation message.
        """
        logger.info(f"Device {device_name} validation result: {success}, message: {message}")
        item = self._device_list_items.get(device_name, None)
        if not item:
            logger.error(f"Device {device_name} not found in the list.")
            return
        if success:
            self._remove_list_item(device_name=device_name)
            self.device_validated.emit(device_name, ValidationStatus.VALID.value)
        else:
            widget: ValidationListItem = self._list_widget.itemWidget(item)
            widget.on_validation_failed(message)
            self.device_validated.emit(device_name, ValidationStatus.FAILED.value)

    def _on_current_item_changed(
        self, current: QtWidgets.QListWidgetItem, previous: QtWidgets.QListWidgetItem
    ):
        """Handle the current item change in the list widget.

        Args:
            current (QListWidgetItem): The currently selected item.
            previous (QListWidgetItem): The previously selected item.
        """
        widget: ValidationListItem = self._list_widget.itemWidget(current)
        if widget:
            try:
                formatted_html = self._format_validation_message(widget.validation_msg)
                self._text_box.setHtml(formatted_html)
            except Exception as e:
                logger.error(f"Error formatting validation message: {e}")
                self._text_box.setPlainText(widget.validation_msg)

    def _format_validation_message(self, raw_msg: str) -> str:
        """Simple HTML formatting for validation messages, wrapping text naturally."""
        if not raw_msg.strip():
            return "<i>Validation in progress...</i>"
        if raw_msg == "Validation in progress...":
            return "<i>Validation in progress...</i>"

        raw_msg = escape(raw_msg)

        # Split into lines
        lines = raw_msg.splitlines()
        summary = lines[0] if lines else "Validation Result"
        rest = "\n".join(lines[1:]).strip()

        # Split traceback / final ERROR
        tb_match = re.search(r"(Traceback.*|ERROR:.*)$", rest, re.DOTALL | re.MULTILINE)
        if tb_match:
            main_text = rest[: tb_match.start()].strip()
            error_detail = tb_match.group().strip()
        else:
            main_text = rest
            error_detail = ""

        # Highlight field names in orange (simple regex for word: Field)
        main_text_html = re.sub(
            r"(\b\w+\b)(?=: Field required)",
            r'<span style="color:#FF8C00; font-weight:bold;">\1</span>',
            main_text,
        )
        # Wrap in div for monospace, allowing wrapping
        main_text_html = (
            f'<div style="white-space: pre-wrap;">{main_text_html}</div>' if main_text_html else ""
        )

        # Traceback / error in red
        error_html = (
            f'<div style="white-space: pre-wrap; color:#A00000;">{error_detail}</div>'
            if error_detail
            else ""
        )

        # Summary at top, dark red
        html = (
            f'<div style="font-family: monospace; font-size:13px; white-space: pre-wrap;">'
            f'<div style="font-weight:bold; color:#8B0000; margin-bottom:4px;">{summary}</div>'
            f"{main_text_html}"
            f"{error_html}"
            f"</div>"
        )
        return html

    def validation_running(self):
        return self._device_list_items != {}

    @SafeSlot()
    def clear_list(self):
        """Clear the device list."""
        self._thread_pool.clear()
        if self._thread_pool.waitForDone(2000) is False:  # Wait for threads to finish
            logger.error("Failed to wait for threads to finish. Removing items from the list.")
        self._device_list_items.clear()
        self._list_widget.clear()

    def remove_device(self, device_name: str):
        """Remove a device from the list."""
        item = self._device_list_items.pop(device_name, None)
        if item:
            self._list_widget.removeItemWidget(item)

    def cleanup(self):
        if self.tester:
            self.tester.shutdown_event.set()
        return super().cleanup()


if __name__ == "__main__":
    import sys

    from bec_lib.bec_yaml_loader import yaml_load

    # pylint: disable=ungrouped-imports
    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    device_manager_ophyd_test = DMOphydTest()
    config_path = "/Users/appel_c/work_psi_awi/bec_workspace/csaxs_bec/csaxs_bec/device_configs/endstation.yaml"
    cfg = yaml_load(config_path)
    cfg.update({"device_will_fail": {"name": "device_will_fail", "some_param": 1}})
    device_manager_ophyd_test.add_device_configs(cfg)
    device_manager_ophyd_test.show()
    device_manager_ophyd_test.setWindowTitle("Device Manager Ophyd Test")
    device_manager_ophyd_test.resize(800, 600)
    sys.exit(app.exec_())
