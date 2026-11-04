# pylint: skip-file
from unittest import mock

import pytest
from qtpy.QtCore import QSettings, Qt

from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.containers.main_window.addons.server_status_item import (
    ServerStatusItem,
    server_indicator,
)
from bec_widgets.widgets.containers.main_window.addons.status_pill import (
    PILL_WIDTHS,
    StatusIconPill,
    ToolSeverity,
)
from bec_widgets.widgets.services.bec_status_box.bec_status_box import BECStatusBox
from bec_widgets.widgets.services.bec_status_box.status_model import RestartState

from .test_bec_status_box import _all_services


@pytest.fixture
def settings_path(tmp_path):
    return str(tmp_path / "server_status.ini")


@pytest.fixture
def item(qtbot, mocked_client, settings_path):
    widget = create_widget(
        qtbot,
        ServerStatusItem,
        client=mocked_client,
        settings=lambda: QSettings(settings_path, QSettings.Format.IniFormat),
    )
    yield widget


def test_card_holds_the_status_box(item):
    assert isinstance(item.card.status_box, BECStatusBox)
    assert item.model is item.status_box.model
    assert item.card.card.objectName() == "server_status_card"


def test_pill_waits_for_services(item):
    indicator = item.indicator
    assert indicator.summary == "Waiting for BEC services"
    assert indicator.severity == ToolSeverity.INFO
    assert isinstance(item.pill, StatusIconPill)
    assert (item.pill.icon_name, item.pill.text) == ("pending", "BEC")
    assert not item.badge_reveal.shown


def test_pill_follows_the_core_state(item, qtbot):
    item.status_box.update_service_status(*_all_services(extra=["CLIBECClient/abc"]))
    assert item.indicator.summary == "All core services running"
    assert item.indicator.severity == ToolSeverity.OK
    assert item.indicator.badge is None
    assert (item.pill.icon_name, item.pill.text) == ("check_circle", "BEC")
    assert item.pill.toolTip() == "All core services running\n5/5 core services up · 1 other"
    assert item.pill.accessibleName() == "All core services running"

    item.status_box.update_service_status(*_all_services(skip=["ScanBundler", "SciHub"]))
    indicator = item.indicator
    assert indicator.severity == ToolSeverity.CRITICAL
    assert indicator.badge == "2 down" and indicator.attention
    assert (item.pill.icon_name, item.pill.text) == ("error", "BEC")
    assert item.badge_chip.text() == "2 down"
    assert item.badge_reveal.shown

    item.status_box.update_service_status(*_all_services())
    assert item.indicator.badge is None
    qtbot.waitUntil(lambda: not item.badge_reveal.shown)


def test_pill_shows_the_restart(item):
    item.status_box.update_service_status(*_all_services())
    item.model.set_restart(RestartState.RUNNING, "Restarting BEC server · 2/5")
    assert item.indicator.summary == "Restarting BEC server · 2/5"
    assert item.indicator.active
    assert (item.pill.icon_name, item.pill.spinning) == ("sync", True)
    item.model.set_restart(
        RestartState.FAILED, "Restart not finished: Scan server did not come back"
    )
    assert item.indicator.severity == ToolSeverity.CRITICAL
    assert (item.pill.icon_name, item.pill.spinning) == ("error", False)
    item.model.set_restart(RestartState.DONE, "BEC server restarted")
    assert item.indicator.summary == "BEC server restarted"
    assert item.pill.icon_name == "check_circle"
    item.model.set_restart(RestartState.NONE)
    assert item.indicator.summary == "All core services running"
    assert item.pill.text == "BEC"


def test_pill_shows_idle_services_as_a_warning(item):
    from bec_lib.messages import BECStatus

    item.status_box.update_service_status(*_all_services(core_status=BECStatus.IDLE))
    assert item.indicator.severity == ToolSeverity.WARNING
    assert item.pill.icon_name == "warning"


def test_indicator_changed_only_on_change(item, qtbot):
    item.status_box.update_service_status(*_all_services())
    emitted = []
    item.indicator_changed.connect(emitted.append)
    item.status_box.update_service_status(*_all_services())
    assert emitted == []
    item.status_box.update_service_status(*_all_services(skip=["SciHub"]))
    assert len(emitted) == 1


def test_small_pill_and_large_size_saved_per_user(item, qtbot, mocked_client, settings_path):
    item.status_box.update_service_status(*_all_services())
    assert item.pill.sizeHint().width() < PILL_WIDTHS["compact"][0] / 2
    item.set_width_mode("wide")  # no width modes for the icon pill
    assert item.width_mode == "compact"
    item.set_large(True)
    again = create_widget(
        qtbot,
        ServerStatusItem,
        client=mocked_client,
        settings=lambda: QSettings(settings_path, QSettings.Format.IniFormat),
    )
    assert again.large and again.pill.height() == 34
    settings = QSettings(settings_path, QSettings.Format.IniFormat)
    assert settings.value("server_status/large") in (True, "true")


def test_restart_dialog_keeps_the_card_open(item, qtbot):
    """The restart confirmation is a modal of the card; the controller keeps the card for it."""
    item.status_box.update_service_status(*_all_services())
    with mock.patch(
        "bec_widgets.widgets.services.bec_status_box.bec_status_box.QMessageBox.warning",
        return_value=mock.MagicMock(),
    ) as dialog:
        item.status_box.view.header.restart_button.click()
    dialog.assert_called_once()
    assert dialog.call_args.args[0] is item.status_box


def test_cleanup_stops_the_status_box(item, qtbot):
    poller = item.poller
    with mock.patch.object(poller, "_get_service_status"):
        item.show()
        qtbot.waitExposed(item)
        assert poller.polling
        item.close()
    assert not poller.polling


def test_server_indicator_without_widget():
    model = mock.MagicMock()
    model.services_down = 0
    model.headline = "Device server: error"
    model.detail = "4/5 core services up"
    model.severity = ToolSeverity.CRITICAL
    model.restart_state = RestartState.NONE
    indicator = server_indicator(model)
    assert indicator.summary == "Device server: error"
    assert indicator.badge is None
    assert indicator.severity == ToolSeverity.CRITICAL


def test_polls_only_while_shown(item, qtbot):
    poller = item.poller
    assert poller is item.status_box.bec_service_status
    assert not item.isVisible()
    assert not poller.polling
    with mock.patch.object(poller, "_get_service_status") as read:
        item.show()
        qtbot.waitExposed(item)
        assert poller.polling
        assert poller._service_update_timer.interval() == 3000
        read.assert_called_once()  # a fresh read right away, not after the first interval
        item.hide()
        assert not poller.polling


def test_pills_of_two_windows_share_one_poll(qtbot, mocked_client, tmp_path):
    def pill(name):
        return create_widget(
            qtbot,
            ServerStatusItem,
            client=mocked_client,
            settings=lambda: QSettings(str(tmp_path / f"{name}.ini"), QSettings.Format.IniFormat),
        )

    first, second = pill("first"), pill("second")
    poller = first.poller
    assert second.poller is poller
    with mock.patch.object(poller, "_get_service_status") as read:
        first.show()
        second.show()
        qtbot.waitExposed(second)
        read.assert_called_once()  # one poll for both windows
        first.hide()
        assert poller.polling  # the other window still shows its pill
        second.hide()
        assert not poller.polling
        first.show()
        qtbot.waitExposed(first)
        assert poller.polling and read.call_count == 2  # resumes with a fresh read
        first.close()
        assert not poller.polling


def test_server_pill_opens_the_status_box_in_the_dock_area(
    qtbot, mocked_client, monkeypatch, tmp_path
):
    from bec_widgets.applications.main_app import BECMainApp

    monkeypatch.setenv("BECWIDGETS_PROFILE_DIR", str(tmp_path))
    app = create_widget(qtbot, BECMainApp, client=mocked_client)
    dock_area = app.dock_area.dock_area
    item = app._server_status_item
    item._prepare_card()
    assert not item.card.hint.isHidden()

    def docked():
        return [w for w in dock_area.widget_list() if isinstance(w, BECStatusBox)]

    before = len(docked())
    qtbot.mouseDClick(item.pill, Qt.MouseButton.LeftButton)
    assert len(docked()) == before + 1
    # the docked box is its own widget, not the one in the card
    assert item.status_box not in docked()
    qtbot.mouseDClick(item.pill, Qt.MouseButton.LeftButton)
    assert len(docked()) == before + 1
