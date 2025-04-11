from typing import TYPE_CHECKING
from unittest import mock

import pytest
from qtpy.QtCore import QPoint, Qt

from bec_widgets.widgets.services.device_browser.device_browser import DeviceBrowser

from .client_mocks import mocked_client

if TYPE_CHECKING:  # pragma: no cover
    from qtpy.QtWidgets import QListWidgetItem

    from bec_widgets.widgets.services.device_browser import DeviceItem


@pytest.fixture
def device_browser(qtbot, mocked_client):
    dev_browser = DeviceBrowser(client=mocked_client)
    qtbot.addWidget(dev_browser)
    qtbot.waitExposed(dev_browser)
    yield dev_browser


def test_device_browser_init_with_devices(device_browser):
    """
    Test that the device browser is initialized with the correct number of devices.
    """
    device_list = device_browser.ui.device_list
    assert device_list.count() == len(device_browser.dev)


def test_device_browser_filtering(qtbot, device_browser):
    """
    Test that the device browser is able to filter the device list.
    """
    device_list = device_browser.ui.device_list
    device_browser.ui.filter_input.setText("sam")
    qtbot.wait(1000)
    assert device_list.count() == 3

    device_browser.ui.filter_input.setText("nonexistent")
    qtbot.wait(1000)
    assert device_list.count() == 0

    device_browser.ui.filter_input.setText("")
    qtbot.wait(1000)
    assert device_list.count() == len(device_browser.dev)


def test_device_item_mouse_press_event(device_browser, qtbot):
    """
    Test that the mousePressEvent is triggered correctly.
    """
    # Simulate a left mouse press event on the device item
    device_item: QListWidgetItem = device_browser.ui.device_list.itemAt(0, 0)
    widget: DeviceItem = device_browser.ui.device_list.itemWidget(device_item)
    qtbot.mouseClick(widget.label, Qt.MouseButton.LeftButton)


def test_device_item_mouse_press_and_move_events_creates_drag(device_browser, qtbot):
    """
    Test that the mousePressEvent is triggered correctly and initiates a drag.
    """
    device_item: QListWidgetItem = device_browser.ui.device_list.itemAt(0, 0)
    widget: DeviceItem = device_browser.ui.device_list.itemWidget(device_item)
    device_name = widget.device
    with mock.patch("qtpy.QtGui.QDrag.exec_") as mock_exec:
        with mock.patch("qtpy.QtGui.QDrag.setMimeData") as mock_set_mimedata:
            qtbot.mousePress(widget.label, Qt.MouseButton.LeftButton, pos=QPoint(0, 0))
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
