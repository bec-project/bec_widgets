import pytest
from bec_lib.scan_history import ScanHistory
from qtpy.QtCore import Qt

from bec_widgets.widgets.utility.scan_index_combobox.scan_index_combobox import ScanIndexComboBox

# pylint: disable=unused-import
from tests.unit_tests.client_mocks import mocked_client
from tests.unit_tests.conftest import create_widget


@pytest.fixture
def scan_index_combo(qtbot, mocked_client, scan_history_factory):
    """ScanIndexComboBox with two history scans injected into the client."""
    msgs = [
        scan_history_factory(scan_id="hid1", scan_number=1),
        scan_history_factory(scan_id="hid2", scan_number=2),
    ]
    mocked_client.history = ScanHistory(mocked_client, False)
    for msg in msgs:
        mocked_client.history._scan_data[msg.scan_id] = msg
        mocked_client.history._scan_ids.append(msg.scan_id)
        mocked_client.history._scan_numbers.append(msg.scan_number)
    combo = create_widget(qtbot, ScanIndexComboBox, client=mocked_client)
    return combo


def test_scan_index_combobox_populates_history(scan_index_combo):
    """The combobox lists 'live' plus all scan numbers (latest first) with scan IDs as item data."""
    assert scan_index_combo.count() == 3
    assert scan_index_combo.itemText(0) == "live"
    assert scan_index_combo.itemData(0) is None
    assert scan_index_combo.itemText(1) == "2"
    assert scan_index_combo.itemData(1) == "hid2"
    assert scan_index_combo.itemText(2) == "1"
    assert scan_index_combo.itemData(2) == "hid1"


def test_scan_index_combobox_scan_id_and_number(scan_index_combo):
    """scan_id/scan_number map the selection to live (None) or a history scan."""
    assert scan_index_combo.currentText() == "live"
    assert scan_index_combo.scan_id is None
    assert scan_index_combo.scan_number is None

    scan_index_combo.setCurrentIndex(1)
    assert scan_index_combo.scan_id == "hid2"
    assert scan_index_combo.scan_number == 2

    # Typing a scan number does not move the current index; scan_id must follow the text
    scan_index_combo.setCurrentText("live")
    scan_index_combo.setCurrentText("1")
    assert scan_index_combo.scan_id == "hid1"
    assert scan_index_combo.scan_number == 1


def test_scan_index_combobox_set_scan_id(scan_index_combo):
    """set_scan_id selects the matching scan or falls back to 'live'."""
    scan_index_combo.set_scan_id("hid1")
    assert scan_index_combo.currentText() == "1"

    scan_index_combo.set_scan_id("unknown")
    assert scan_index_combo.currentText() == "live"

    scan_index_combo.set_scan_id("hid2")
    assert scan_index_combo.currentText() == "2"
    scan_index_combo.set_scan_id(None)
    assert scan_index_combo.currentText() == "live"


def test_scan_index_combobox_refresh_keeps_selection(scan_index_combo):
    """refresh_scan_indices repopulates the items without losing the current selection."""
    scan_index_combo.set_scan_id("hid2")
    scan_index_combo.refresh_scan_indices()
    assert scan_index_combo.count() == 3
    assert scan_index_combo.currentText() == "2"
    assert scan_index_combo.scan_id == "hid2"


@pytest.mark.parametrize("history", [None, "empty"])
def test_scan_index_combobox_empty_history(qtbot, mocked_client, history):
    """
    With no scan history (client not started) or an empty one, only 'live' is offered
    and any typed scan number is flagged as invalid.
    """
    mocked_client.history = ScanHistory(mocked_client, False) if history == "empty" else None
    combo = create_widget(qtbot, ScanIndexComboBox, client=mocked_client)

    assert combo.count() == 1
    assert combo.currentText() == "live"
    assert combo.scan_id is None
    assert combo.scan_number is None
    assert combo.is_valid_input

    # Typing is not blocked by a validator, but scan numbers are flagged since none exist
    assert combo.lineEdit().validator() is None
    combo.lineEdit().clear()
    qtbot.keyClicks(combo.lineEdit(), "1")
    assert combo.currentText() == "1"
    assert not combo.is_valid_input
    with pytest.raises(ValueError):
        _ = combo.scan_id


def test_scan_index_combobox_typing_multi_digit_scan(qtbot, mocked_client, scan_history_factory):
    """
    Multi-digit scan numbers can be typed even when their prefixes are not scan numbers
    themselves, and the completer autocompletes against the listed entries.
    """
    msgs = [
        scan_history_factory(scan_id="hid101", scan_number=101),
        scan_history_factory(scan_id="hid105", scan_number=105),
    ]
    mocked_client.history = ScanHistory(mocked_client, False)
    for msg in msgs:
        mocked_client.history._scan_data[msg.scan_id] = msg
        mocked_client.history._scan_ids.append(msg.scan_id)
        mocked_client.history._scan_numbers.append(msg.scan_number)
    combo = create_widget(qtbot, ScanIndexComboBox, client=mocked_client)

    combo.lineEdit().clear()
    qtbot.keyClicks(combo.lineEdit(), "101")
    assert combo.currentText() == "101"
    assert combo.is_valid_input
    assert combo.styleSheet() == ""
    assert combo.scan_id == "hid101"
    assert combo.scan_number == 101

    # The default editable-combobox completer offers the listed entries while typing
    completer = combo.completer()
    assert completer is not None
    completer.setCompletionPrefix("l")
    assert completer.currentCompletion() == "live"
    completer.setCompletionPrefix("10")
    assert completer.currentCompletion() == "105"


def test_scan_index_combobox_invalid_input_flagged(scan_index_combo, qtbot):
    """
    Unknown scan numbers can be typed; they are flagged with a red border, raise on
    read-out, and are not inserted as new items when committed.
    """
    combo = scan_index_combo
    combo.lineEdit().clear()
    qtbot.keyClicks(combo.lineEdit(), "99")
    assert combo.currentText() == "99"
    assert not combo.is_valid_input
    assert "red" in combo.styleSheet()
    with pytest.raises(ValueError):
        _ = combo.scan_id
    with pytest.raises(ValueError):
        _ = combo.scan_number

    qtbot.keyClick(combo.lineEdit(), Qt.Key_Return)
    assert combo.count() == 3

    # A refresh with invalid text falls back to 'live' instead of raising
    combo.refresh_scan_indices()
    assert combo.currentText() == "live"
    assert combo.is_valid_input

    combo.setCurrentText("2")
    assert combo.is_valid_input
    assert combo.styleSheet() == ""
    assert combo.scan_id == "hid2"
