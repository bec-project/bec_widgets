import pytest

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.services.bec_queue.bec_queue_qt import BECQueueQt

from .test_bec_queue import _status_msg, busy_queue  # pylint: disable=unused-import


@pytest.fixture
def qt_queue(qtbot, mocked_client):
    widget = create_widget(qtbot, BECQueueQt, client=mocked_client, refresh_upon_start=False)
    qtbot.waitExposed(widget)
    yield widget


def test_qt_view_shows_rows_and_sections(qt_queue, busy_queue):
    qt_queue.update_queue(busy_queue.content, {})
    view = qt_queue.view
    assert len(view._rows) == 4
    assert set(view._section_labels) == {"Now", "Waiting"}
    assert view.state_pill._text.text() == "Running"
    assert view.counts.text() == "1 running · 3 waiting"
    assert view.abort_button.isEnabled()


def test_qt_view_reuses_row_widgets(qt_queue, busy_queue):
    qt_queue.update_queue(busy_queue.content, {})
    before = dict(qt_queue.view._rows)
    qt_queue.update_queue(busy_queue.content, {})
    assert all(qt_queue.view._rows[k] is w for k, w in before.items())


def test_qt_view_inline_remove(qt_queue, busy_queue):
    qt_queue.update_queue(busy_queue.content, {})
    row = [w for w in qt_queue.view._rows.values() if w.row.section == "Waiting"][2]
    row.remove.click()
    assert row.actions.currentIndex() == 1
    qt_queue.client.queue.request_scan_abortion.assert_not_called()
    row.confirm_remove.click()
    qt_queue.client.queue.request_scan_abortion.assert_called_once_with(
        request_id=row.row.request_id
    )
    assert row.pill._text.text() == "Removing…"


def test_qt_view_paused_banner_and_empty_state(qt_queue, busy_queue):
    info = busy_queue.queue["primary"].info
    qt_queue.update_queue(_status_msg(info, status="PAUSED").content, {})
    assert not qt_queue.view.banner_box.isHidden()
    assert qt_queue.view.pause_button.text() == "Resume"
    qt_queue.update_queue({}, {})
    assert qt_queue.view._rows == {}
    assert not qt_queue.view.empty.isHidden()
