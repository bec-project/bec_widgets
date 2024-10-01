from unittest import mock

import pyqtgraph as pg
import pytest

from bec_widgets.utils.bec_signal_proxy import BECSignalProxy
from bec_widgets.widgets.dap_combo_box.dap_combo_box import DapComboBox

from .client_mocks import mocked_client
from .conftest import create_widget


@pytest.fixture
def dap_combo_box(qtbot, mocked_client):
    """Fixture for TextBox widget to test BECSignalProxy with a simple widget"""
    with mock.patch(
        "bec_widgets.widgets.dap_combo_box.dap_combo_box.DapComboBox._validate_dap_model",
        return_value=True,
    ):
        widget = create_widget(qtbot, DapComboBox, client=mocked_client)
        yield widget


def test_bec_signal_proxy(qtbot, dap_combo_box):
    """Test BECSignalProxy"""
    proxy_container = []

    def proxy_callback(*args):
        """A simple callback function for the proxy"""
        proxy_container.append(args)

    container = []

    def all_callbacks(*args):
        """A simple callback function for all signal calls"""
        container.append(args)

    proxy = BECSignalProxy(dap_combo_box.x_axis_updated, rateLimit=25, slot=proxy_callback)
    pg_proxy = pg.SignalProxy(dap_combo_box.x_axis_updated, rateLimit=25, slot=all_callbacks)
    qtbot.wait(200)
    # Test that the proxy is blocked
    assert container == []
    assert proxy_container == []
    # Set first value
    dap_combo_box.x_axis = "samx"
    qtbot.waitSignal(dap_combo_box.x_axis_updated, timeout=1000)
    qtbot.wait(100)
    assert container == [(("samx",),)]
    assert proxy.blocked is True
    assert proxy_container == [(("samx",),)]
    # Set new value samy
    dap_combo_box.x_axis = "samy"
    qtbot.waitSignal(dap_combo_box.x_axis_updated, timeout=1000)
    qtbot.wait(100)
    assert container == [(("samx",),), (("samy",),)]
    assert proxy.blocked is True
    assert proxy_container == [(("samx",),)]
    # Set new value samz
    dap_combo_box.x_axis = "samz"
    qtbot.waitSignal(dap_combo_box.x_axis_updated, timeout=1000)
    qtbot.wait(100)
    assert container == [(("samx",),), (("samy",),), (("samz",),)]
    assert proxy.blocked is True
    proxy.unblock_proxy()
    qtbot.waitSignal(proxy.is_blocked, timeout=1000)
    qtbot.wait(100)
    assert proxy.blocked is True
    assert proxy_container == [(("samx",),), (("samz",),)]
    # Unblock the proxy again, no new argument received.
    # The callback should not be called again.
    proxy.unblock_proxy()
    qtbot.waitSignal(proxy.is_blocked, timeout=1000)
    qtbot.wait(100)
    assert proxy.blocked is False
    assert proxy_container == [(("samx",),), (("samz",),)]
