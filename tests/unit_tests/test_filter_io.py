from qtpy.QtWidgets import QComboBox

from bec_widgets.utils.filter_io import (
    combobox_contains_text,
    get_bec_signals_for_classes,
    replace_combobox_items,
)
from bec_widgets.widgets.dap.dap_combo_box.dap_combo_box import DapComboBox

from .client_mocks import mocked_client
from .conftest import create_widget


def test_replace_combobox_items(qtbot, mocked_client):
    widget = create_widget(qtbot, DapComboBox, client=mocked_client)

    replace_combobox_items(widget, ["testA", ("testB", {"payload": True})])

    assert widget.count() == 2
    assert widget.itemText(0) == "testA"
    assert widget.itemText(1) == "testB"
    assert widget.itemData(1) == {"payload": True}
    assert combobox_contains_text(widget, "testA") is True
    assert combobox_contains_text(widget, "missing") is False


def test_get_bec_signals_for_classes_ndim_filter(mocked_client):
    signals = [
        ("dev1", "sig1", {"describe": {"signal_info": {"ndim": 1}}}),
        ("dev1", "sig2", {"describe": {"signal_info": {"ndim": 2}}}),
    ]
    mocked_client.device_manager.get_bec_signals = lambda _filters: signals

    out = get_bec_signals_for_classes(
        client=mocked_client, signal_class_filter=["AsyncSignal"], ndim_filter=1
    )

    assert out == [("dev1", "sig1", {"describe": {"signal_info": {"ndim": 1}}})]


def test_replace_combobox_items_empty(qtbot):
    widget = QComboBox()
    qtbot.addWidget(widget)
    widget.addItem("old")

    replace_combobox_items(widget, [])

    assert widget.count() == 0
