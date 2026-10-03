"""
BECWidget.cleanup() must not leave item views with dangling pointers to the BEC widgets
it deletes from their cells (setCellWidget / setItemWidget / setIndexWidget).

An item view keeps raw pointers to its index widgets. If cleanup deletes such a widget
without the view releasing it first, the next layout pass of the view
(QAbstractItemView::updateEditorGeometries) dereferences freed memory and the process
dies with SIGSEGV. Every scenario therefore runs in a child pytest process, so a native
crash fails one test here instead of taking down the whole session.
"""

import os
import subprocess
import sys

import pytest
import shiboken6
from bec_lib import messages
from qtpy.QtCore import QEvent
from qtpy.QtWidgets import (
    QApplication,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.tests.client_mocks import dap_plugin_message, mocked_client, mocked_client_with_dap
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.control.buttons.button_abort.button_abort import AbortButton
from bec_widgets.widgets.plots.waveform.settings.curve_settings.curve_tree import CurveTree
from bec_widgets.widgets.plots.waveform.waveform import Waveform
from bec_widgets.widgets.services.bec_queue.bec_queue import BECQueue

from .conftest import create_widget

INNER = "BW_CELL_WIDGET_INNER"
inner_only = pytest.mark.skipif(
    os.environ.get(INNER) != "1", reason="runs only inside the child process"
)


def _flush_deferred_deletes():
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()


class CellBECWidget(BECWidget, QWidget):
    """Minimal BEC widget used as a cell widget."""

    PLUGIN = False
    RPC = False


class ViewHost(BECWidget, QWidget):
    """A BEC widget whose table, tree and list hold BEC widgets as cell widgets."""

    PLUGIN = False
    RPC = False

    def __init__(self, parent=None, client=None, **kwargs):
        super().__init__(parent=parent, client=client, **kwargs)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(3, 2, self)
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(2)
        self.list = QListWidget(self)
        for view in (self.table, self.tree, self.list):
            layout.addWidget(view)

        self.cells = []
        for row in range(3):
            table_cell = CellBECWidget(parent=self, client=client)
            self.table.setCellWidget(row, 1, table_cell)

            tree_item = QTreeWidgetItem(self.tree, [f"row {row}"])
            tree_cell = CellBECWidget(parent=self, client=client)
            self.tree.setItemWidget(tree_item, 1, tree_cell)

            list_item = QListWidgetItem(self.list)
            list_cell = CellBECWidget(parent=self, client=client)
            self.list.setItemWidget(list_item, list_cell)

            self.cells += [table_cell, tree_cell, list_cell]

    def views(self):
        return (self.table, self.tree, self.list)


def _queue_entry(scan_number: int, rid: str, status: str = "PENDING") -> dict:
    """Build a single primary-queue entry with one request block."""
    msg = messages.ScanQueueMessage(
        metadata={"RID": rid}, scan_type="line_scan", parameter={"args": {}, "kwargs": {}}
    )
    return {
        "queue_id": f"queue-{scan_number}",
        "scan_id": [f"scan-{scan_number}"],
        "is_scan": [True],
        "request_blocks": [
            {
                "msg": msg,
                "RID": rid,
                "readout_priority": {"monitored": [], "baseline": [], "on_request": []},
                "is_scan": True,
                "scan_number": scan_number,
                "scan_id": f"scan-{scan_number}",
            }
        ],
        "scan_number": [scan_number],
        "status": status,
    }


def _three_row_queue_content() -> dict:
    content = {
        "primary": {
            "info": [
                _queue_entry(1001, "rid-1001", status="RUNNING"),
                _queue_entry(1002, "rid-1002"),
                _queue_entry(1003, "rid-1003"),
            ],
            "status": "RUNNING",
        }
    }
    return messages.ScanQueueStatusMessage(metadata={}, queue=content).content


#####################################################################
# Scenarios, executed only inside the child process
#####################################################################


@inner_only
def test_inner_view_host_close_releases_cell_widgets(qtbot, mocked_client):
    host = create_widget(qtbot, ViewHost, client=mocked_client)
    cells = list(host.cells)
    assert all(isinstance(cell, BECWidget) for cell in cells)

    host.close()  # BECWidget.cleanup() closes and deletes every BECWidget child
    _flush_deferred_deletes()
    for view in host.views():
        view.updateEditorGeometries()  # SIGSEGV if a view still holds a deleted cell widget

    # cleanup still releases the cell widgets, and the views no longer reference them
    assert not any(shiboken6.isValid(cell) for cell in cells)
    assert all(host.table.cellWidget(row, 1) is None for row in range(3))
    for row in range(3):
        assert host.tree.itemWidget(host.tree.topLevelItem(row), 1) is None
        assert host.list.itemWidget(host.list.item(row)) is None


@inner_only
def test_inner_nested_view_close_releases_cell_widgets(qtbot, mocked_client):
    """The view sits deeper in the closed widget, below a plain (non-BEC) container."""
    outer = create_widget(qtbot, CellBECWidget, client=mocked_client)
    container = QWidget(outer)
    QVBoxLayout(outer).addWidget(container)
    table = QTableWidget(3, 1, container)
    QVBoxLayout(container).addWidget(table)
    cells = [CellBECWidget(client=mocked_client) for _ in range(3)]
    for row, cell in enumerate(cells):
        table.setCellWidget(row, 0, cell)

    outer.close()
    _flush_deferred_deletes()
    table.updateEditorGeometries()

    assert not any(shiboken6.isValid(cell) for cell in cells)
    assert all(table.cellWidget(row, 0) is None for row in range(3))


@inner_only
def test_inner_bec_queue_close_then_relayout(qtbot, mocked_client):
    queue = BECQueue(client=mocked_client, refresh_upon_start=False)
    qtbot.addWidget(queue)
    qtbot.waitExposed(queue)
    queue.update_queue(_three_row_queue_content(), {})
    assert queue.table.rowCount() == 3
    buttons = [queue.table.cellWidget(row, 4) for row in range(3)]
    assert all(isinstance(button, AbortButton) for button in buttons)

    queue.close()
    _flush_deferred_deletes()
    queue.table.updateEditorGeometries()  # SIGSEGV on the deleted abort buttons

    assert not any(shiboken6.isValid(button) for button in buttons)
    assert all(queue.table.cellWidget(row, 4) is None for row in range(3))


@inner_only
def test_inner_curve_tree_close_then_relayout(qtbot, mocked_client_with_dap):
    """Guard: CurveTree keeps BEC combo boxes in tree cells and removes its rows on cleanup."""
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    curve_tree = create_widget(qtbot, CurveTree, parent=None, waveform=wf)
    first = curve_tree.add_new_curve(device="bpm4i", signal="bpm4i")
    curve_tree.add_new_curve(device="samx", signal="samx")
    first.add_dap_row()
    cell_widgets = [
        w
        for w in (first.device_edit, first.entry_edit, first.scan_index_combo, first.color_button)
        if isinstance(w, BECWidget)
    ]
    assert cell_widgets

    curve_tree.close()
    _flush_deferred_deletes()
    curve_tree.tree.updateEditorGeometries()

    assert not any(shiboken6.isValid(w) for w in cell_widgets)


#####################################################################
# Child-process wrappers (the tests that actually run in the suite)
#####################################################################


@pytest.mark.parametrize(
    "scenario",
    [
        "test_inner_view_host_close_releases_cell_widgets",
        "test_inner_nested_view_close_releases_cell_widgets",
        "test_inner_bec_queue_close_then_relayout",
        "test_inner_curve_tree_close_then_relayout",
    ],
)
def test_cell_widgets_survive_owner_cleanup(scenario):
    env = dict(os.environ, **{INNER: "1"})
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", f"{__file__}::{scenario}"],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    print(proc.stdout[-3000:], proc.stderr[-3000:])
    assert proc.returncode == 0, f"child exited with {proc.returncode} (negative = signal)"
