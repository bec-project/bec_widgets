from typing import TYPE_CHECKING
from unittest import mock

import pytest
from qtpy.QtCore import QPoint, Qt
from qtpy.QtWidgets import QTabWidget

from bec_widgets.widgets.services.device_browser.device_browser import DeviceBrowser
from bec_widgets.widgets.services.device_browser.device_item.device_config_form import (
    DeviceConfigForm,
)
from bec_widgets.widgets.services.device_browser.device_item.device_signal_display import (
    SignalDisplay,
)

from .client_mocks import mocked_client

if TYPE_CHECKING:  # pragma: no cover
    from qtpy.QtWidgets import QListWidgetItem

    from bec_widgets.widgets.services.device_browser.device_item import DeviceItem


# pylint: disable=no-member
# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=protected-access


@pytest.fixture
def device_browser(qtbot, mocked_client):
    dev_browser = DeviceBrowser(client=mocked_client)
    dev_browser.dev["samx"].read_configuration = mock.MagicMock()
    qtbot.addWidget(dev_browser)
    qtbot.waitExposed(dev_browser)
    yield dev_browser


def test_device_browser_init_with_devices(device_browser):
    """
    Test that the device browser is initialized with the correct number of devices.
    """
    device_list = device_browser.ui.device_list
    assert device_list.count() == len(device_browser.dev)


@pytest.mark.parametrize(
    ["search_term", "expected_num_visible"],
    [("sam", 3), ("nonexistent", 0), ("", -1), (r"(\)", -1)],
)
def test_device_browser_filtering(
    qtbot, device_browser, search_term: str, expected_num_visible: int
):
    """
    Test that the device browser is able to filter the device list.
    """
    expected = expected_num_visible if expected_num_visible >= 0 else len(device_browser.dev)

    def num_visible(item_dict):
        return len(list(filter(lambda i: not i.isHidden(), item_dict.values())))

    device_browser.ui.filter_input.setText(search_term)
    qtbot.wait(100)
    assert num_visible(device_browser._device_items) == expected


def test_device_item_mouse_press_event(device_browser, qtbot):
    """
    Test that the mousePressEvent is triggered correctly.
    """
    # Simulate a left mouse press event on the device item
    device_item: QListWidgetItem = device_browser.ui.device_list.itemAt(0, 0)
    widget: DeviceItem = device_browser.ui.device_list.itemWidget(device_item)
    qtbot.mouseClick(widget._title, Qt.MouseButton.LeftButton)


def test_update_event_captured(device_browser, qtbot):
    device_browser.update_device_list = mock.MagicMock()
    device_browser.update_device_list.assert_not_called()
    device_browser.on_device_update("remove", {})
    device_browser.update_device_list.assert_called_once()
    device_browser.on_device_update("", {})


def test_device_item_expansion(device_browser, qtbot):
    """
    Test that the form is displayed when the item is expanded, and that the expansion is triggered
    by clicking on the expansion button, the title, or the device icon
    """
    device_item: QListWidgetItem = device_browser.ui.device_list.itemAt(0, 0)
    widget: DeviceItem = device_browser.ui.device_list.itemWidget(device_item)
    qtbot.mouseClick(widget._expansion_button, Qt.MouseButton.LeftButton)
    tab_widget: QTabWidget = widget._contents.layout().itemAt(0).widget()
    qtbot.waitUntil(lambda: tab_widget.widget(0) is not None, timeout=100)
    qtbot.waitUntil(
        lambda: isinstance(tab_widget.widget(0).layout().itemAt(0).widget(), DeviceConfigForm),
        timeout=100,
    )
    form = tab_widget.widget(0).layout().itemAt(0).widget()
    assert widget.expanded
    assert (name_field := form.widget_dict.get("name")) is not None
    qtbot.waitUntil(lambda: name_field.getValue() == "samx", timeout=500)
    qtbot.mouseClick(widget._expansion_button, Qt.MouseButton.LeftButton)
    assert not widget.expanded

    qtbot.mouseClick(widget._title, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: widget.expanded, timeout=500)

    qtbot.mouseClick(widget._title_icon, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not widget.expanded, timeout=500)


def test_device_item_mouse_press_and_move_events_creates_drag(device_browser, qtbot):
    """
    Test that the mousePressEvent is triggered correctly and initiates a drag.
    """
    device_item: QListWidgetItem = device_browser.ui.device_list.itemAt(0, 0)
    widget: DeviceItem = device_browser.ui.device_list.itemWidget(device_item)
    device_name = widget.device
    with mock.patch("qtpy.QtGui.QDrag.exec_") as mock_exec:
        with mock.patch("qtpy.QtGui.QDrag.setMimeData") as mock_set_mimedata:
            qtbot.mousePress(widget._title, Qt.MouseButton.LeftButton, pos=QPoint(0, 0))
            qtbot.mouseMove(widget, pos=QPoint(10, 10))
            qtbot.mouseRelease(widget, Qt.MouseButton.LeftButton)
            mock_set_mimedata.assert_called_once()
            mock_exec.assert_called_once()
            assert mock_set_mimedata.call_args[0][0].text() == device_name


def test_device_item_double_click_event(device_browser, qtbot):
    """
    Test that the mouseDoubleClickEvent is triggered correctly.
    """
    # Simulate a left mouse press event on the device item
    device_item: QListWidgetItem = device_browser.ui.device_list.itemAt(0, 0)
    widget: DeviceItem = device_browser.ui.device_list.itemWidget(device_item)
    qtbot.mouseDClick(widget, Qt.LeftButton)


def test_device_deletion(device_browser, qtbot):
    device_item: QListWidgetItem = device_browser.ui.device_list.itemAt(0, 0)
    widget: DeviceItem = device_browser.ui.device_list.itemWidget(device_item)
    widget._config_helper = mock.MagicMock()

    assert widget.device in device_browser._device_items
    qtbot.mouseClick(widget.delete_button, Qt.LeftButton)
    qtbot.waitUntil(lambda: widget.device not in device_browser._device_items, timeout=10000)


def test_signal_display(mocked_client, qtbot):
    signal_display = SignalDisplay(client=mocked_client, device="test_device")
    qtbot.addWidget(signal_display)
    device_mock = mock.MagicMock()
    signal_display.dev = {"test_device": device_mock}
    signal_display._refresh()
    device_mock.read.assert_called()
    device_mock.read_configuration.assert_called()


def test_signal_display_no_device(mocked_client, qtbot):
    device_mock = mock.MagicMock()
    mocked_client.client.device_manager.devices = {"test_device_1": device_mock}
    signal_display = SignalDisplay(client=mocked_client, device="test_device_2")
    qtbot.addWidget(signal_display)
    assert (
        signal_display._content_layout.itemAt(1).widget().text()
        == "Device test_device_2 not found in device manager!"
    )
    signal_display._refresh()
    device_mock.read.assert_not_called()
    device_mock.read_configuration.assert_not_called()


def test_signal_display_omitted_not_added(mocked_client, qtbot):
    device_mock = mock.MagicMock()
    device_mock._info = {"signals": {"signal_1": {"kind_str": "omitted"}}}

    signal_display = SignalDisplay(client=mocked_client, device="test_device_1")
    signal_display.dev = {"test_device_1": device_mock}
    signal_display._populate()

    qtbot.addWidget(signal_display)
    assert signal_display._content_layout.itemAt(1).widget() is None
