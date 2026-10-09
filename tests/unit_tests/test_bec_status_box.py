# pylint: skip-file
import time
from unittest import mock

import pytest
from bec_lib.messages import BECStatus, ServiceInfo, ServiceMetricMessage, StatusMessage
from qtpy.QtQuickWidgets import QQuickWidget
from qtpy.QtWidgets import QApplication

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.services.bec_status_box.bec_status_box import (
    BECServiceInfoContainer,
    BECStatusBox,
)
from bec_widgets.widgets.services.bec_status_box.status_box_widgets import StatusBoxWidgetView
from bec_widgets.widgets.services.bec_status_box.status_model import (
    CORE_GROUP,
    OTHER_GROUP,
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


@pytest.fixture(params=["qml", "widgets"])
def status_box(request, qtbot, mocked_client):
    widget = create_widget(
        qtbot,
        BECStatusBox,
        client=mocked_client,
        bec_service_status_mixin=mock.MagicMock(),
        view=request.param,
    )
    assert widget.view_kind == request.param
    yield widget


def test_initial_state(status_box):
    assert status_box.get_server_state() == "IDLE"
    assert status_box.model.rowCount() == 0
    assert status_box.model.headline == "Waiting for BEC services"


def test_view_type(status_box):
    expected = QQuickWidget if status_box.view_kind == "qml" else StatusBoxWidgetView
    assert isinstance(status_box.view, expected)


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
    assert model.tone == "success"
    assert model.detail == "5/5 core services up · 1 other"
    rows = model.rows
    assert [r.service_name for r in rows[:5]] == BECStatusBox.CORE_SERVICES
    assert rows[5].display_name == "IPython client"
    assert rows[5].group == OTHER_GROUP
    assert rows[5].subtitle == "e12345@console · #abcdef"


def test_core_service_missing(status_box):
    status_box.update_service_status(*_all_services(skip=["ScanBundler"]))
    model = status_box.model
    assert status_box.get_server_state() == "NOTCONNECTED"
    assert model.headline == "Scan bundler: not connected"
    assert model.tone == "emergency"
    row = next(r for r in model.rows if r.service_name == "ScanBundler")
    assert row.status_label == "Not connected"
    assert row.subtitle == "No heartbeat from this service"


def test_compact_led_follows_summary(status_box):
    with mock.patch.object(status_box, "set_global_state") as set_state:
        status_box.update_service_status(*_all_services(skip=["SciHub"]))
        set_state.assert_called_with("emergency")
        status_box.update_service_status(*_all_services())
        set_state.assert_called_with("success")


def test_stale_services_removed(status_box):
    status_box.update_service_status(*_all_services(extra=["CLIBECClient/1", "CLIBECClient/2"]))
    assert status_box.model.rowCount() == 7
    status_box.update_service_status(*_all_services(extra=["CLIBECClient/2"]))
    assert status_box.model.rowCount() == 6
    assert "CLIBECClient/1" not in status_box.status_container


def test_rows_updated_in_place(status_box):
    """A status change emits dataChanged for one row instead of resetting the model."""
    status_box.update_service_status(*_all_services())
    model = status_box.model
    resets, changes = [], []
    model.modelReset.connect(lambda: resets.append(True))
    model.dataChanged.connect(lambda first, last, roles: changes.append(first.row()))
    info, metrics = _all_services()
    info["ScanServer"] = _status("ScanServer", BECStatus.BUSY)
    metrics = {k: v for k, v in metrics.items()}
    status_box.update_service_status(info, metrics)
    assert not resets
    idx = BECStatusBox.CORE_SERVICES.index("ScanServer")
    assert idx in changes
    assert model.rows[idx].status_label == "Busy"


def test_version_mismatch(status_box):
    info, metrics = _all_services(extra=["CLIBECClient/old"])
    info["CLIBECClient/old"] = _status("CLIBECClient/old", lib="3.0.0")
    status_box.update_service_status(info, metrics)
    mismatched = [r.service_name for r in status_box.model.rows if r.version_mismatch]
    assert mismatched == ["CLIBECClient/old"]
    assert "1 version mismatch" in status_box.model.detail


def test_copy_details(status_box):
    status_box.update_service_status(*_all_services())
    status_box.model.copyDetails("DeviceServer")
    text = QApplication.clipboard().text()
    assert text.startswith("DeviceServer: Running")
    assert "Host: console" in text
    assert "PID: 42" in text


def test_widget_view_expand_and_reuse(qtbot, mocked_client):
    box = create_widget(
        qtbot,
        BECStatusBox,
        client=mocked_client,
        bec_service_status_mixin=mock.MagicMock(),
        view="widgets",
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


def test_qml_view_loads(qtbot, mocked_client):
    box = create_widget(
        qtbot,
        BECStatusBox,
        client=mocked_client,
        bec_service_status_mixin=mock.MagicMock(),
        view="qml",
    )
    box.update_service_status(*_all_services())
    root = box.view.rootObject()
    assert root is not None
    assert not box.view.errors()
    service_list = root.findChild(object, "serviceList")
    assert service_list.property("count") == 5
    root.setProperty("expandedService", "DeviceServer")
    assert root.property("expandedService") == "DeviceServer"


def test_qml_falls_back_to_widgets(qtbot, mocked_client):
    with mock.patch(
        "bec_widgets.utils.quick.create_quick_widget", side_effect=RuntimeError("no GL")
    ):
        box = create_widget(
            qtbot,
            BECStatusBox,
            client=mocked_client,
            bec_service_status_mixin=mock.MagicMock(),
            view="qml",
        )
    assert box.view_kind == "widgets"
    assert isinstance(box.view, StatusBoxWidgetView)


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
    assert rows[1].tone == "emergency"
    assert rows[3].status == "NOTCONNECTED"
