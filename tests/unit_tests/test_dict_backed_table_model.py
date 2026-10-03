"""Regression tests for DictBackedTableModel model notifications (bec_widgets#1319).

Views and proxies attached to a QAbstractItemModel rely on the model announcing every
structural change at its real position and never emitting dataChanged for rows that do not
exist. Qt's QAbstractItemModelTester is used in Warning mode (never Fatal, which aborts the
process); its failures are collected from the Qt log.
"""

# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

import pytest
from qtpy.QtCore import QItemSelectionModel, QSortFilterProxyModel, Qt
from qtpy.QtTest import QAbstractItemModelTester

from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.editors.dict_backed_table import DictBackedTable
from bec_widgets.widgets.editors.scan_metadata.scan_metadata import ScanMetadata

INITIAL_DATA = [["key1", "value1"], ["key2", "value2"], ["key3", "value3"]]


class NotificationRecorder:
    """Record a model's notifications as plain tuples, evaluated at emission time."""

    def __init__(self, model):
        self.model = model
        self.inserted: list[tuple[bool, int, int]] = []
        self.removed: list[tuple[bool, int, int]] = []
        self.data_changed: list[tuple[bool, int, bool, int, int]] = []
        self.resets = 0
        model.rowsAboutToBeInserted.connect(
            lambda parent, first, last: self.inserted.append((parent.isValid(), first, last))
        )
        model.rowsAboutToBeRemoved.connect(
            lambda parent, first, last: self.removed.append((parent.isValid(), first, last))
        )
        model.dataChanged.connect(self._on_data_changed)
        model.modelReset.connect(self._on_reset)

    def _on_data_changed(self, top_left, bottom_right, *_):
        self.data_changed.append(
            (
                top_left.isValid(),
                top_left.row(),
                bottom_right.isValid(),
                bottom_right.row(),
                self.model.rowCount(),
            )
        )

    def _on_reset(self):
        self.resets += 1

    def invalid_data_changed(self):
        """dataChanged emissions with an invalid index or a row outside the model."""
        return [
            entry
            for entry in self.data_changed
            if not (entry[0] and entry[2] and 0 <= entry[1] <= entry[3] < entry[4])
        ]


def _model_rows(model) -> list[str]:
    return [model.index(row, 0).data() for row in range(model.rowCount())]


def _tester_failures(qtlog) -> list[str]:
    return [record.message for record in qtlog.records if record.message.startswith("FAIL!")]


@pytest.fixture
def table(qtbot):
    return create_widget(qtbot, DictBackedTable, initial_data=[list(r) for r in INITIAL_DATA])


@pytest.fixture
def recorder(table):
    return NotificationRecorder(table._table_model)


@pytest.fixture
def emitted(table):
    """Dicts emitted by DictBackedTable.data_changed."""
    received: list[dict] = []
    table.data_changed.connect(received.append)
    return received


@pytest.fixture
def model_tester(table):
    tester = QAbstractItemModelTester(
        table._table_model, QAbstractItemModelTester.FailureReportingMode.Warning
    )
    yield tester
    tester.deleteLater()


def test_add_row_announces_insert_at_end(table, recorder, emitted, capfd):
    table._add_button.click()

    assert table._table_model.rowCount() == 4
    assert recorder.inserted == [(False, 3, 3)]
    assert recorder.invalid_data_changed() == []
    # passing 0 as the roles argument of dataChanged makes shiboken print conversion errors
    assert "Cannot copy-convert" not in capfd.readouterr().err
    assert table.dump_dict() == {"key1": "value1", "key2": "value2", "key3": "value3", "": ""}
    assert emitted[-1] == table.dump_dict()


def test_delete_rows_does_not_touch_removed_rows(table, recorder, emitted):
    selection = table._table_view.selectionModel()
    selection.select(table._table_model.index(1, 0), QItemSelectionModel.SelectionFlag.Select)
    table.delete_selected_rows()

    assert recorder.removed == [(False, 1, 1)]
    assert recorder.data_changed == []
    assert table.dump_dict() == {"key1": "value1", "key3": "value3"}
    # listeners must see the table after the removal, not before it
    assert emitted[-1] == {"key1": "value1", "key3": "value3"}


@pytest.mark.parametrize("new_data", [{"a": "1", "b": "2"}, {}])
def test_replace_data_announces_structural_change(table, recorder, emitted, new_data):
    table.replace_data(new_data)

    assert recorder.invalid_data_changed() == []
    assert recorder.resets == 1
    assert table.dump_dict() == new_data
    assert emitted[-1] == new_data


def test_proxy_model_stays_in_sync(table):
    proxy = QSortFilterProxyModel()
    proxy.setSourceModel(table._table_model)
    proxy.sort(0, Qt.SortOrder.DescendingOrder)

    table._add_button.click()
    assert _model_rows(proxy) == sorted(_model_rows(table._table_model), reverse=True)

    table.replace_data({"a": "1", "b": "2"})
    assert _model_rows(proxy) == ["b", "a"]

    table.clear()
    assert _model_rows(proxy) == []
    proxy.setSourceModel(None)


def test_model_tester_reports_no_failures(table, model_tester, qtlog):
    model = table._table_model
    table._add_button.click()
    model.setData(model.index(3, 0), "key4", Qt.ItemDataRole.EditRole)
    table.update_disallowed_keys(["key2"])
    selection = table._table_view.selectionModel()
    selection.select(model.index(0, 0), QItemSelectionModel.SelectionFlag.Select)
    selection.select(model.index(2, 0), QItemSelectionModel.SelectionFlag.Select)
    table.delete_selected_rows()
    table.replace_data({"a": "1", "b": "2"})
    table.clear()

    assert _tester_failures(qtlog) == []


def test_tables_do_not_share_backing_data(qtbot):
    first = create_widget(qtbot, DictBackedTable)
    second = create_widget(qtbot, DictBackedTable)
    first._add_button.click()

    assert first._table_model.rowCount() == 1
    assert second._table_model.rowCount() == 0


def test_scan_metadata_form_drops_deleted_extra_row(qtbot):
    widget = create_widget(qtbot, ScanMetadata, initial_extras=[["k1", "v1"], ["k2", "v2"]])
    received: list[dict] = []
    widget.form_data_updated.connect(received.append)
    table = widget._additional_metadata

    selection = table._table_view.selectionModel()
    selection.select(table._table_model.index(0, 0), QItemSelectionModel.SelectionFlag.Select)
    table.delete_selected_rows()

    assert table.dump_dict() == {"k2": "v2"}
    assert received, "deleting a row must re-validate the form"
    assert "k1" not in received[-1]
    assert received[-1]["k2"] == "v2"
