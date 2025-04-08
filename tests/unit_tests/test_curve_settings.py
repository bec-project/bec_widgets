import json
from unittest.mock import MagicMock, patch

import pytest
from qtpy.QtWidgets import QComboBox, QVBoxLayout

from bec_widgets.widgets.plots.waveform.settings.curve_settings.curve_setting import CurveSetting
from bec_widgets.widgets.plots.waveform.settings.curve_settings.curve_tree import CurveTree
from bec_widgets.widgets.plots.waveform.waveform import Waveform
from tests.unit_tests.client_mocks import dap_plugin_message, mocked_client, mocked_client_with_dap
from tests.unit_tests.conftest import create_widget

##################################################
# CurveSetting
##################################################


@pytest.fixture
def curve_setting_fixture(qtbot, mocked_client):
    """
    Creates a CurveSetting widget targeting a mock or real Waveform widget.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    wf.x_mode = "auto"
    curve_setting = create_widget(qtbot, CurveSetting, parent=None, target_widget=wf)
    return curve_setting, wf


def test_curve_setting_init(curve_setting_fixture):
    """
    Ensure CurveSetting constructs properly, with a CurveTree inside
    and an x-axis group box for modes.
    """
    curve_setting, wf = curve_setting_fixture

    # The layout should be QVBoxLayout
    assert isinstance(curve_setting.layout, QVBoxLayout)

    # There's an x_axis_box group and a y_axis_box group
    assert hasattr(curve_setting, "x_axis_box")
    assert hasattr(curve_setting, "y_axis_box")

    # The x_axis_box should contain a QComboBox for mode
    mode_combo = curve_setting.mode_combo
    assert isinstance(mode_combo, QComboBox)
    # Should contain these items: ["auto", "index", "timestamp", "device"]
    expected_modes = ["auto", "index", "timestamp", "device"]
    for m in expected_modes:
        assert m in [
            curve_setting.mode_combo.itemText(i) for i in range(curve_setting.mode_combo.count())
        ]

    # Check that there's a curve_manager inside y_axis_box
    assert hasattr(curve_setting, "curve_manager")
    assert curve_setting.y_axis_box.layout.count() > 0


def test_curve_setting_accept_changes(curve_setting_fixture, qtbot):
    """
    Test that calling accept_changes() applies x-axis mode changes
    and triggers the CurveTree to send its curve JSON to the target waveform.
    """
    curve_setting, wf = curve_setting_fixture

    # Suppose user chooses "index" from the combo
    curve_setting.mode_combo.setCurrentText("index")
    # The device_x is disabled if not device mode

    # Spy on 'send_curve_json' from the curve_manager
    send_spy = MagicMock()
    curve_setting.curve_manager.send_curve_json = send_spy

    # Call accept_changes()
    curve_setting.accept_changes()

    # Check that we updated the waveform
    assert wf.x_mode == "index"
    # Check that the manager send_curve_json was called
    send_spy.assert_called_once()


def test_curve_setting_switch_device_mode(curve_setting_fixture, qtbot):
    """
    If user chooses device mode from the combo, the device_x line edit should be enabled
    and set to the current wavefrom.x_axis_mode["name"].
    """
    curve_setting, wf = curve_setting_fixture

    # Initially we assume "auto"
    assert curve_setting.mode_combo.currentText() == "auto"
    # Switch to device
    curve_setting.mode_combo.setCurrentText("device")
    assert curve_setting.device_x.isEnabled()

    # This line edit should reflect the waveform.x_axis_mode["name"], or be blank if none
    assert curve_setting.device_x.text() == wf.x_axis_mode["name"]


def test_curve_setting_refresh(curve_setting_fixture, qtbot):
    """
    Test that calling refresh() refreshes the embedded CurveTree
    and re-reads the x axis mode from the waveform.
    """
    curve_setting, wf = curve_setting_fixture

    # Suppose the waveform changed x_mode from "auto" to "timestamp" behind the scenes
    wf.x_mode = "timestamp"
    # Spy on the curve_manager
    refresh_spy = MagicMock()
    curve_setting.curve_manager.refresh_from_waveform = refresh_spy

    # Call refresh
    curve_setting.refresh()

    refresh_spy.assert_called_once()
    # The combo should now read "timestamp"
    assert curve_setting.mode_combo.currentText() == "timestamp"


def test_change_device_from_target_widget(curve_setting_fixture, qtbot):
    curve_setting, wf = curve_setting_fixture

    wf.x_mode = "samx"

    # Call refresh
    curve_setting.refresh()

    assert curve_setting.mode_combo.currentText() == "device"
    assert curve_setting.device_x.isEnabled()
    assert curve_setting.device_x.text() == wf.x_axis_mode["name"]
    assert curve_setting.signal_x.text() == wf.x_axis_mode["entry"]


##################################################
# CurveTree
##################################################


@pytest.fixture
def curve_tree_fixture(qtbot, mocked_client_with_dap):
    """
    Creates a CurveTree widget referencing a mocked or real Waveform.
    """
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    wf.color_palette = "magma"
    curve_tree = create_widget(qtbot, CurveTree, parent=None, waveform=wf)
    return curve_tree, wf


def test_curve_tree_init(curve_tree_fixture):
    """
    Test that the CurveTree initializes properly with references to the waveform,
    sets up the toolbar, and an empty QTreeWidget.
    """
    curve_tree, wf = curve_tree_fixture
    assert curve_tree.waveform == wf
    assert curve_tree.color_palette == "magma"
    assert curve_tree.tree.columnCount() == 7

    assert "add" in curve_tree.toolbar.widgets
    assert "expand_all" in curve_tree.toolbar.widgets
    assert "collapse_all" in curve_tree.toolbar.widgets
    assert "renormalize_colors" in curve_tree.toolbar.widgets


def test_add_new_curve(curve_tree_fixture):
    """
    Test that add_new_curve() adds a top-level item with a device curve config,
    assigns it a color from the buffer, and doesn't modify existing rows.
    """
    curve_tree, wf = curve_tree_fixture
    curve_tree.color_buffer = ["#111111", "#222222", "#333333", "#444444", "#555555"]

    assert curve_tree.tree.topLevelItemCount() == 0

    with patch.object(curve_tree, "_ensure_color_buffer_size") as ensure_spy:
        new_item = curve_tree.add_new_curve(name="bpm4i", entry="bpm4i")
        ensure_spy.assert_called_once()

    assert curve_tree.tree.topLevelItemCount() == 1
    last_item = curve_tree.all_items[-1]
    assert last_item is new_item
    assert new_item.config.source == "device"
    assert new_item.config.signal.name == "bpm4i"
    assert new_item.config.signal.entry == "bpm4i"
    assert new_item.config.color in curve_tree.color_buffer


def test_renormalize_colors(curve_tree_fixture):
    """
    Test that renormalize_colors overwrites colors for all items in creation order.
    """
    curve_tree, wf = curve_tree_fixture
    # Add multiple curves
    c1 = curve_tree.add_new_curve(name="bpm4i", entry="bpm4i")
    c2 = curve_tree.add_new_curve(name="bpm3a", entry="bpm3a")
    curve_tree.color_buffer = []

    set_color_spy_c1 = patch.object(c1.color_button, "set_color")
    set_color_spy_c2 = patch.object(c2.color_button, "set_color")

    with set_color_spy_c1 as spy1, set_color_spy_c2 as spy2:
        curve_tree.renormalize_colors()
        spy1.assert_called_once()
        spy2.assert_called_once()


def test_expand_collapse(curve_tree_fixture):
    """
    Test expand_all_daps() and collapse_all_daps() calls expand/collapse on every top-level item.
    """
    curve_tree, wf = curve_tree_fixture
    c1 = curve_tree.add_new_curve(name="bpm4i", entry="bpm4i")
    curve_tree.tree.expandAll()
    expand_spy = patch.object(curve_tree.tree, "expandItem")
    collapse_spy = patch.object(curve_tree.tree, "collapseItem")

    with expand_spy as e_spy:
        curve_tree.expand_all_daps()
        e_spy.assert_called_once_with(c1)

    with collapse_spy as c_spy:
        curve_tree.collapse_all_daps()
        c_spy.assert_called_once_with(c1)


def test_send_curve_json(curve_tree_fixture, monkeypatch):
    """
    Test that send_curve_json sets the waveform's color_palette and curve_json
    to the exported config from the tree.
    """
    curve_tree, wf = curve_tree_fixture
    # Add multiple curves
    curve_tree.add_new_curve(name="bpm4i", entry="bpm4i")
    curve_tree.add_new_curve(name="bpm3a", entry="bpm3a")

    curve_tree.color_palette = "viridis"
    curve_tree.send_curve_json()

    assert wf.color_palette == "viridis"
    data = json.loads(wf.curve_json)
    assert len(data) == 2
    labels = [d["label"] for d in data]
    assert "bpm4i-bpm4i" in labels
    assert "bpm3a-bpm3a" in labels


def test_refresh_from_waveform(qtbot, mocked_client_with_dap, monkeypatch):
    """
    Test that refresh_from_waveform() rebuilds the tree from the waveform's curve_json
    """
    patched_models = {"GaussianModel": {}, "LorentzModel": {}, "SineModel": {}}
    monkeypatch.setattr(mocked_client_with_dap.dap, "_available_dap_plugins", patched_models)

    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    wf.x_mode = "auto"
    curve_tree = create_widget(qtbot, CurveTree, parent=None, waveform=wf)

    wf.plot(arg1="bpm4i", dap="GaussianModel")
    wf.plot(arg1="bpm3a", dap="GaussianModel")

    # Clear the tree to simulate a fresh rebuild.
    curve_tree.tree.clear()
    curve_tree.all_items.clear()
    assert curve_tree.tree.topLevelItemCount() == 0

    # For DAP rows
    curve_tree.refresh_from_waveform()
    assert curve_tree.tree.topLevelItemCount() == 2


def test_add_dap_row(curve_tree_fixture):
    """
    Test that add_dap_row creates a new DAP curve as a child of a device curve,
    with the correct configuration and parent-child relationship.
    """
    curve_tree, wf = curve_tree_fixture

    # Add a device curve first
    device_row = curve_tree.add_new_curve(name="bpm4i", entry="bpm4i")
    assert device_row.source == "device"
    assert curve_tree.tree.topLevelItemCount() == 1
    assert device_row.childCount() == 0

    # Now add a DAP row to it
    device_row.add_dap_row()

    # Check that child was added
    assert device_row.childCount() == 1
    dap_child = device_row.child(0)

    # Verify the DAP child has the correct configuration
    assert dap_child.source == "dap"
    assert dap_child.config.parent_label == device_row.config.label

    # Check that the DAP inherits device name/entry from parent
    assert dap_child.config.signal.name == "bpm4i"
    assert dap_child.config.signal.entry == "bpm4i"

    # Check that the item is in the curve_tree's all_items list
    assert dap_child in curve_tree.all_items


def test_remove_self_top_level(curve_tree_fixture):
    """
    Test that remove_self removes a top-level device row from the tree.
    """
    curve_tree, wf = curve_tree_fixture

    # Add two device curves
    row1 = curve_tree.add_new_curve(name="bpm4i", entry="bpm4i")
    row2 = curve_tree.add_new_curve(name="bpm3a", entry="bpm3a")
    assert curve_tree.tree.topLevelItemCount() == 2
    assert len(curve_tree.all_items) == 2

    # Remove the first row
    row1.remove_self()

    # Check that only one row remains and it's the correct one
    assert curve_tree.tree.topLevelItemCount() == 1
    assert curve_tree.tree.topLevelItem(0) == row2
    assert len(curve_tree.all_items) == 1
    assert curve_tree.all_items[0] == row2


def test_remove_self_child(curve_tree_fixture):
    """
    Test that remove_self removes a child DAP row while preserving the parent device row.
    """
    curve_tree, wf = curve_tree_fixture

    # Add a device curve and a DAP child
    device_row = curve_tree.add_new_curve(name="bpm4i", entry="bpm4i")
    device_row.add_dap_row()
    dap_child = device_row.child(0)

    assert curve_tree.tree.topLevelItemCount() == 1
    assert device_row.childCount() == 1
    assert len(curve_tree.all_items) == 2

    # Remove the DAP child
    dap_child.remove_self()

    # Check that the parent device row still exists but has no children
    assert curve_tree.tree.topLevelItemCount() == 1
    assert device_row.childCount() == 0
    assert len(curve_tree.all_items) == 1
    assert curve_tree.all_items[0] == device_row


def test_export_data_dap(curve_tree_fixture):
    """
    Test that export_data from a DAP row correctly includes parent relationship and DAP model.
    """
    curve_tree, wf = curve_tree_fixture

    # Add a device curve with specific parameters
    device_row = curve_tree.add_new_curve(name="bpm4i", entry="bpm4i")

    # Add a DAP child
    device_row.add_dap_row()
    dap_child = device_row.child(0)

    # Set a specific model in the DAP combobox
    dap_child.dap_combo.fit_model_combobox.setCurrentText("GaussianModel")

    # Export data from the DAP row
    exported = dap_child.export_data()

    # Check the exported data
    assert exported["source"] == "dap"
    assert exported["parent_label"] == "bpm4i-bpm4i"
    assert exported["signal"]["name"] == "bpm4i"
    assert exported["signal"]["entry"] == "bpm4i"
    assert exported["signal"]["dap"] == "GaussianModel"
    assert exported["label"] == "bpm4i-bpm4i-GaussianModel"
