"""Benchmarks of the device pickers against DeviceComboBox with a large device list."""

# pylint: disable=redefined-outer-name, missing-function-docstring
from __future__ import annotations

import threading

import pytest
from qtpy.QtWidgets import QApplication

from bec_widgets.tests.client_mocks import mocked_client  # noqa: F401
from bec_widgets.tests.fake_devices import FakeDevice, FakePositioner
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.control.device_input.picker.picker_qml import DevicePickerQML
from bec_widgets.widgets.control.device_input.picker.picker_qwidget import DevicePicker

WIDGETS = [DeviceComboBox, DevicePicker, DevicePickerQML]


@pytest.fixture
def many_devices(mocked_client):
    devices = []
    for index in range(300):
        devices.append(FakePositioner(f"mot{index:03d}", limits=[-1, 1], read_value=1.0))
        devices.append(FakeDevice(f"det{index:03d}"))
    mocked_client.device_manager.add_devices(devices)
    yield mocked_client


def _close(widgets):
    for widget in widgets:
        widget.close()
        widget.deleteLater()


@pytest.mark.parametrize("widget_cls", WIDGETS, ids=lambda cls: cls.__name__)
def test_create_device_input(benchmark, qtbot, many_devices, widget_cls):
    """Create one device input with about 600 devices."""
    created = []

    def create():
        created.append(widget_cls(client=many_devices))

    benchmark(create)
    assert created[-1].devices
    _close(created)


@pytest.mark.parametrize("widget_cls", WIDGETS, ids=lambda cls: cls.__name__)
def test_device_update_refreshes_twenty_inputs(benchmark, qtbot, many_devices, widget_cls):
    """Deliver one device configuration update to 20 device inputs, as on a config reload."""
    widgets = [widget_cls(client=many_devices) for _ in range(20)]

    def update():
        thread = threading.Thread(
            target=lambda: [widget.on_device_update("reload", {}) for widget in widgets]
        )
        thread.start()
        thread.join()
        QApplication.processEvents()

    benchmark(update)
    _close(widgets)


@pytest.mark.parametrize("widget_cls", [DevicePicker, DevicePickerQML], ids=lambda c: c.__name__)
def test_search_popup_keystroke(benchmark, qtbot, many_devices, widget_cls):
    """Filter the open popup by one more character."""
    widget = widget_cls(client=many_devices)
    widget.open_picker()
    controller = widget.picker_controller
    queries = iter(["m", "mo", "mot", "mot1", "mot12", ""] * 1000)

    benchmark(lambda: controller.set_query(next(queries)))
    widget.hidePopup()
    _close([widget])
