# pylint: skip-file
from unittest import mock

import pytest

from bec_widgets.applications.main_app import BECMainApp
from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.services.bec_status_box.bec_status_box import BECStatusBox
from bec_widgets.widgets.services.bec_status_box.status_pill import BECStatusPill

from .test_bec_status_box import _all_services


@pytest.fixture
def pill(qtbot, mocked_client):
    widget = create_widget(qtbot, BECStatusPill, view="widgets", client=mocked_client)
    yield widget
    widget.popup.hide()
    widget.cleanup()


def test_pill_text_follows_state(pill):
    assert pill.text() == "BEC: waiting"
    pill.status_box.update_service_status(*_all_services())
    assert pill.text() == "BEC running"
    assert pill.tone == "success"
    pill.status_box.update_service_status(*_all_services(skip=["ScanBundler"]))
    assert pill.text() == "Scan bundler: not connected"
    assert pill.tone == "emergency"


def test_pill_shows_restart(pill):
    pill.status_box.update_service_status(*_all_services())
    pill.model.set_restart("running", "Restarting BEC server · 2/5")
    assert pill.text() == "Restarting BEC · 2/5"
    assert pill.tone == "progress"


def test_pill_toggles_popup(pill, qtbot):
    pill.click()
    qtbot.waitUntil(pill.popup.isVisible)
    pill.click()
    qtbot.waitUntil(lambda: not pill.popup.isVisible())


def test_dock_button_requests_dock(pill, qtbot):
    pill.click()
    with qtbot.waitSignal(pill.dock_requested):
        pill.popup.dock_button.click()
    assert not pill.popup.isVisible()


def test_main_app_docks_one_status_box(qtbot, mocked_client):
    app = BECMainApp(client=mocked_client, anim_duration=60, show_examples=False)
    qtbot.addWidget(app)
    assert isinstance(app.status_pill, BECStatusPill)

    def docked():
        return [w for w in app.dock_area.dock_area.widget_list() if isinstance(w, BECStatusBox)]

    before = len(docked())
    app.dock_status_box()
    assert len(docked()) == before + 1
    app.dock_status_box()
    assert len(docked()) == before + 1
