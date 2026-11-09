# pylint: skip-file
import time
from unittest import mock

import pytest
from bec_lib.endpoints import MessageEndpoints
from bec_lib.messages import BECStatus, ServiceInfo, ServiceMetricMessage, StatusMessage
from qtpy.QtWidgets import QApplication, QMessageBox

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.containers.main_window.addons.status_pill import ToolSeverity
from bec_widgets.widgets.progress.stage_bar import Tone
from bec_widgets.widgets.services.bec_status_box.bec_status_box import (
    BECServiceInfoContainer,
    BECStatusBox,
)
from bec_widgets.widgets.services.bec_status_box.status_box_widgets import StatusBoxWidgetView
from bec_widgets.widgets.services.bec_status_box.status_model import (
    CORE_GROUP,
    OTHER_GROUP,
    RestartState,
    build_rows,
    format_duration,
    friendly_name,
)


def _versions(lib="3.39.5"):
    return {
        "bec_lib": lib,
        "bec_server": lib,
        "bec_ipython_client": lib,
        "bec_widgets": "3.39.5",
        "ophyd_devices": "1.51.0",
    }


def _status(name, status=BECStatus.RUNNING, lib="3.39.5"):
    info = ServiceInfo(user="e12345", hostname="console", versions=_versions(lib))
    return StatusMessage(name=name, status=status, info=info)


def _metrics(name, **extra):
    metrics = {"pid": 42, "cpu_percent": 4.2, "memory_in_mb": 120.0, "create_time": time.time()}
    metrics.update(extra)
    return ServiceMetricMessage(name=name, metrics=metrics)


def _all_services(extra=(), skip=(), core_status=BECStatus.RUNNING):
    names = [n for n in BECStatusBox.CORE_SERVICES if n not in skip] + list(extra)
    info = {
        n: _status(n, core_status if n in BECStatusBox.CORE_SERVICES else BECStatus.RUNNING)
        for n in names
    }
    metrics = {n: _metrics(n) for n in names}
    return info, metrics


@pytest.fixture
def status_box(qtbot, mocked_client):
    widget = create_widget(
        qtbot, BECStatusBox, client=mocked_client, bec_service_status_mixin=mock.MagicMock()
    )
    yield widget


def test_initial_state(status_box):
    assert status_box.get_server_state() == "IDLE"
    assert status_box.model.rows == []
    assert status_box.model.headline == "Waiting for BEC services"


def test_view_type(status_box):
    assert isinstance(status_box.view, StatusBoxWidgetView)


def test_update_top_item(status_box):
    status_box.update_top_item_status(status="RUNNING")
    assert status_box.get_server_state() == "RUNNING"


def test_bec_service_container(status_box):
    name = "test_service"
    status = BECStatus.IDLE
    info = {"test": "test"}
    metrics = {"metric": "test_metric"}
    expected_return = BECServiceInfoContainer(
        service_name=name, status=status.name, info=info, metrics=metrics
    )
    with mock.patch.object(status_box, "service_update") as service_update:
        status_box._update_status_container(name, status, info, metrics)
        service_update.emit.assert_called_once_with(expected_return)
    assert status_box.status_container[name] == expected_return


def test_all_core_running(status_box):
    status_box.update_service_status(*_all_services(extra=["CLIBECClient/abcdef123"]))
    model = status_box.model
    assert status_box.get_server_state() == "RUNNING"
    assert model.headline == "All core services running"
    assert model.severity == ToolSeverity.OK
    assert model.services_down == 0
    assert model.detail == "5/5 core services up · 1 other"
    rows = model.rows
    assert [r.service_name for r in rows[:5]] == BECStatusBox.CORE_SERVICES
    assert rows[5].display_name == "IPython client"
    assert rows[5].group == OTHER_GROUP
    assert rows[5].subtitle == "e12345@console · #abcdef"


def test_service_info_is_stored_as_dict_without_changing_the_message(status_box):
    services_info, services_metric = _all_services(extra=["CLIBECClient/abcdef123"])
    status_box.update_service_status(services_info, services_metric)
    for name, msg in services_info.items():
        assert isinstance(msg.info, ServiceInfo)
        assert status_box.status_container[name].info == msg.info.model_dump()


def test_core_service_missing(status_box):
    status_box.update_service_status(*_all_services(skip=["ScanBundler"]))
    model = status_box.model
    assert status_box.get_server_state() == "NOTCONNECTED"
    assert model.headline == "Scan bundler: not connected"
    assert model.severity == ToolSeverity.CRITICAL
    assert model.services_down == 1
    row = next(r for r in model.rows if r.service_name == "ScanBundler")
    assert row.status_label == "Not connected"
    assert row.subtitle == "No heartbeat from this service"


def test_stale_services_removed(status_box):
    status_box.update_service_status(*_all_services(extra=["CLIBECClient/1", "CLIBECClient/2"]))
    assert len(status_box.model.rows) == 7
    status_box.update_service_status(*_all_services(extra=["CLIBECClient/2"]))
    assert len(status_box.model.rows) == 6
    assert "CLIBECClient/1" not in status_box.status_container


def test_rows_updated_in_place(status_box):
    """A status change updates the existing row widget instead of rebuilding the list."""
    status_box.update_service_status(*_all_services())
    view = status_box.view
    row_widget = view.rows["ScanServer"]
    info, metrics = _all_services()
    info["ScanServer"] = _status("ScanServer", BECStatus.BUSY)
    status_box.update_service_status(info, metrics)
    idx = BECStatusBox.CORE_SERVICES.index("ScanServer")
    assert status_box.model.rows[idx].status_label == "Busy"
    assert view.rows["ScanServer"] is row_widget
    assert row_widget.chip.text() == "Busy"
    assert row_widget.busy and view._spinner.isActive()


def test_version_mismatch(status_box):
    info, metrics = _all_services(extra=["CLIBECClient/old"])
    info["CLIBECClient/old"] = _status("CLIBECClient/old", lib="3.0.0")
    status_box.update_service_status(info, metrics)
    mismatched = [r.service_name for r in status_box.model.rows if r.version_mismatch]
    assert mismatched == ["CLIBECClient/old"]
    assert "1 version mismatch" in status_box.model.detail


def test_copy_details(status_box):
    status_box.update_service_status(*_all_services())
    status_box.model.copy_details("DeviceServer")
    text = QApplication.clipboard().text()
    assert text.startswith("DeviceServer: Running")
    assert "Host: console" in text
    assert "PID: 42" in text


def test_widget_view_expand_and_reuse(qtbot, mocked_client):
    box = create_widget(
        qtbot, BECStatusBox, client=mocked_client, bec_service_status_mixin=mock.MagicMock()
    )
    box.update_service_status(*_all_services())
    view = box.view
    row_widget = view.rows["DeviceServer"]
    view._toggle("DeviceServer")
    assert row_widget.expanded and not row_widget.details.isHidden()
    view._toggle("ScanServer")
    assert not row_widget.expanded
    assert view.rows["ScanServer"].expanded
    box.update_service_status(*_all_services())
    assert view.rows["DeviceServer"] is row_widget
    assert view.rows["ScanServer"].expanded


def test_friendly_name():
    assert friendly_name("DeviceServer") == ("Device server", "")
    assert friendly_name("CLIBECClient/0123456789") == ("IPython client", "012345")
    assert friendly_name("MyNewService") == ("My new service", "")


def test_format_duration():
    assert format_duration(5) == "5 s"
    assert format_duration(125) == "2 min"
    assert format_duration(3 * 3600 + 300) == "3 h 5 min"
    assert format_duration(2 * 86400 + 4 * 3600) == "2 d 4 h"


def test_build_rows_order_and_groups():
    services = [
        BECServiceInfoContainer("CLIBECClient/b", "RUNNING", {}, None),
        BECServiceInfoContainer("ScanServer", "ERROR", {}, None),
        BECServiceInfoContainer("DeviceServer", "IDLE", {}, None),
        BECServiceInfoContainer("Weird", "SOMETHING", {}, None),
    ]
    rows = build_rows(services, ["DeviceServer", "ScanServer"])
    assert [r.service_name for r in rows] == [
        "DeviceServer",
        "ScanServer",
        "CLIBECClient/b",
        "Weird",
    ]
    assert [r.group for r in rows] == [CORE_GROUP, CORE_GROUP, OTHER_GROUP, OTHER_GROUP]
    assert rows[1].tone == Tone.BAD
    assert rows[3].status == "NOTCONNECTED"


def test_widget_view_follows_theme(qtbot, mocked_client):
    from bec_widgets.utils.colors import apply_theme

    box = create_widget(
        qtbot, BECStatusBox, client=mocked_client, bec_service_status_mixin=mock.MagicMock()
    )
    box.update_service_status(*_all_services())
    apply_theme("dark")
    dark = box.view.styleSheet()
    apply_theme("light")
    qtbot.waitUntil(lambda: box.view.styleSheet() != dark)
    apply_theme("dark")
    qtbot.waitUntil(lambda: box.view.styleSheet() == dark)


def _restarted(started):
    info, metrics = _all_services()
    for name in BECStatusBox.CORE_SERVICES:
        metrics[name].metrics["create_time"] = started
    return info, metrics


@pytest.fixture
def send(status_box):
    with mock.patch.object(status_box.client.connector, "send") as send_mock:
        yield send_mock


def test_restart_needs_scihub(status_box, send):
    status_box.update_service_status(*_all_services(skip=["SciHub"]))
    assert not status_box.model.can_restart
    status_box.model.request_restart()
    send.assert_not_called()
    status_box.update_service_status(*_all_services())
    assert status_box.model.can_restart


def test_restart_confirm_cancel(status_box, send):
    status_box.update_service_status(*_all_services())
    with mock.patch(
        "bec_widgets.widgets.services.bec_status_box.bec_status_box.QMessageBox.warning",
        return_value=QMessageBox.StandardButton.Cancel,
    ) as dialog:
        status_box.model.request_restart()
    dialog.assert_called_once()
    send.assert_not_called()


def test_restart_progress_and_done(qtbot, status_box, send):
    old_start = time.time() - 100
    status_box.update_service_status(*_restarted(old_start))
    with (
        mock.patch(
            "bec_widgets.widgets.services.bec_status_box.bec_status_box.QMessageBox.warning",
            return_value=QMessageBox.StandardButton.Yes,
        ),
        mock.patch.object(status_box, "_reload_client") as reload_client,
    ):
        status_box.model.request_restart()
        endpoint, msg = send.call_args[0]
        assert endpoint == MessageEndpoints.service_request()
        assert msg.action == "restart"
        model = status_box.model
        assert model.restart_state == RestartState.RUNNING
        assert not model.can_restart
        # old processes are still reporting: nothing counts as restarted yet
        status_box.update_service_status(*_restarted(old_start))
        assert model.restart_text.endswith("0/5")
        status_box.update_service_status(*_all_services(skip=BECStatusBox.CORE_SERVICES))
        assert model.restart_state == RestartState.RUNNING
        status_box.update_service_status(*_restarted(time.time() + 1))
        assert model.restart_state == RestartState.DONE
        assert model.can_restart
        # the client reload runs on the thread pool
        qtbot.waitUntil(lambda: reload_client.called)
    reload_client.assert_called_once()


def test_restart_is_detected_when_the_server_clock_lags(qtbot, status_box, send):
    status_box.update_service_status(*_restarted(time.time() - 100))
    with mock.patch.object(status_box, "_reload_client") as reload_client:
        status_box.request_restart()
        # the new processes report a start time before the GUI host's request time
        status_box.update_service_status(*_restarted(time.time() - 5))
        assert status_box.model.restart_state == RestartState.DONE
        qtbot.waitUntil(lambda: reload_client.called)


def test_restart_timeout(status_box, send):
    status_box.update_service_status(*_all_services())
    with mock.patch.object(status_box.model, "restart_requested"):
        status_box.request_restart()
    status_box._restart_timed_out()
    assert status_box.model.restart_state == RestartState.FAILED
    assert "Device server" in status_box.model.restart_text


def test_header_follows_restart(status_box):
    status_box.update_service_status(*_all_services())
    header = status_box.view.header
    assert header._tone == Tone.OK
    status_box.model.set_restart(RestartState.RUNNING, "Restarting BEC server · 1/5")
    assert header.headline.text() == "Restarting BEC server · 1/5"
    assert header._tone == Tone.ACCENT
    assert header._spin.isActive() and not header.restart_button.isEnabled()
    status_box.model.set_restart(RestartState.FAILED, "Restart not finished")
    assert header._tone == Tone.BAD and header._pulse.isActive()
    status_box.model.set_restart(RestartState.NONE)
    assert header.headline.text() == "All core services running"
    assert not header._pulse.isActive() and not header._spin.isActive()


def test_service_status_read_off_the_gui_thread(qtbot):
    import threading

    from bec_widgets.widgets.services.bec_status_box.bec_status_box import BECServiceStatusMixin

    client = mock.MagicMock()
    read_threads, release = [], threading.Event()

    def read():
        read_threads.append(threading.get_ident())
        release.wait(5)
        client._services_info = {"DeviceServer": "info"}
        client._services_metric = {"DeviceServer": "metric"}

    client._update_existing_services.side_effect = read
    service_status = BECServiceStatusMixin(None, client)
    try:
        updates = []
        service_status.services_update.connect(lambda info, metric: updates.append((info, metric)))
        service_status._get_service_status()
        # a tick while the read is still running does not start a second one
        service_status._get_service_status()
        qtbot.waitUntil(lambda: bool(read_threads))
        assert read_threads[0] != threading.main_thread().ident
        assert not updates
        release.set()
        qtbot.waitUntil(lambda: bool(updates))
        assert updates == [({"DeviceServer": "info"}, {"DeviceServer": "metric"})]
        assert client._update_existing_services.call_count == 1
        assert service_status._worker is None
    finally:
        release.set()
        service_status.cleanup()


def test_service_status_poller_is_shared_and_follows_its_viewers(qtbot, mocked_client):
    """Two status boxes (e.g. in two windows) share one poller; it reads only while one is shown."""
    from bec_widgets.widgets.services.bec_status_box.bec_status_box import BECServiceStatusMixin

    first = create_widget(qtbot, BECStatusBox, client=mocked_client)
    second = create_widget(qtbot, BECStatusBox, client=mocked_client)
    poller = first.bec_service_status
    assert poller is second.bec_service_status is BECServiceStatusMixin.shared(mocked_client)
    assert poller._service_update_timer.interval() == 3000
    assert not poller.polling  # nothing shown yet

    with mock.patch.object(poller, "_get_service_status") as read:
        first.show()
        qtbot.waitExposed(first)
        assert poller.polling
        read.assert_called_once()  # the first viewer starts with a read
        second.show()
        qtbot.waitExposed(second)
        read.assert_called_once()  # the second one shares the running poll
        first.hide()
        assert poller.polling
        second.hide()
        assert not poller.polling  # nothing shows the status: no polling
        first.show()
        qtbot.waitExposed(first)
        assert poller.polling and read.call_count == 2  # resumes with a fresh read
        first.close()
        second.close()
    assert not poller.polling


def test_a_new_status_box_gets_the_last_result_at_once(qtbot, mocked_client):
    from bec_widgets.widgets.services.bec_status_box.bec_status_box import BECServiceStatusMixin

    poller = BECServiceStatusMixin.shared(mocked_client)
    poller.last_update = _all_services()
    box = create_widget(qtbot, BECStatusBox, client=mocked_client)
    assert box.get_server_state() == "RUNNING"
    assert len(box.model.rows) == len(BECStatusBox.CORE_SERVICES)


def test_cleanup_of_one_box_keeps_the_shared_poll_for_the_other(qtbot, mocked_client):
    first = create_widget(qtbot, BECStatusBox, client=mocked_client)
    second = create_widget(qtbot, BECStatusBox, client=mocked_client)
    poller = first.bec_service_status
    with mock.patch.object(poller, "_get_service_status"):
        first.show()
        second.show()
        qtbot.waitExposed(second)
        first.cleanup()
        assert poller.polling  # the second box still shows it
        updates = []
        poller.services_update.connect(lambda *_: updates.append(True))
        with mock.patch.object(first, "update_service_status") as first_update:
            poller.services_update.emit(*_all_services())
        first_update.assert_not_called()  # the cleaned-up box is disconnected
        second.cleanup()
        assert not poller.polling
    second.close()


def test_icons_render_at_the_screen_pixel_ratio(status_box, monkeypatch):
    """The icons are drawn at the device pixel ratio, so they are sharp on HiDPI screens."""
    from qtpy.QtGui import QColor

    from bec_widgets.utils import theme_utils
    from bec_widgets.widgets.services.bec_status_box.status_box_widgets import rotated_pixmap

    asked = []

    def ratio(widget):
        asked.append(widget)
        return 2.0

    # QLabel.pixmap() hands back a copy at the label's own ratio, so check the lookup instead
    monkeypatch.setattr(theme_utils, "_device_pixel_ratio", ratio)
    info, metrics = _all_services()
    info["ScanServer"] = _status("ScanServer", BECStatus.BUSY)
    status_box.update_service_status(info, metrics)
    view = status_box.view
    view.apply_theme()
    row, busy = view.rows["DeviceServer"], view.rows["ScanServer"]
    busy.rotate_icon()
    for widget in (
        row.icon,
        row.chevron,
        row.copy_button,
        busy.icon,
        view.header.spinner,
        view.header.restart_button,
    ):
        assert widget in asked
    # a spinning icon keeps its pixel ratio and its size after the rotation
    pixmap = theme_utils.crisp_pixmap("progress_activity", 20, QColor("red"), widget=busy.icon)
    turned = rotated_pixmap(pixmap, 30)
    assert turned.devicePixelRatio() == 2.0
    assert turned.size() == pixmap.size()
