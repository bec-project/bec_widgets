from __future__ import annotations

import pytest
from bec_lib.messages import BeamlineConditionUpdateEntry
from qtpy.QtWidgets import QToolBar

from bec_widgets.utils.toolbars.actions import StatusIndicatorAction, StatusIndicatorWidget
from bec_widgets.utils.toolbars.status_bar import BECStatusBroker, StatusToolBar

from .client_mocks import mocked_client
from .conftest import create_widget


class TestStatusIndicators:
    """Widget/action level tests independent of broker wiring."""

    def test_indicator_widget_state_and_text(self, qtbot):
        widget = StatusIndicatorWidget(text="Ready", state="success")
        qtbot.addWidget(widget)
        qtbot.waitExposed(widget)
        widget.set_state("warning")
        widget.set_text("Alert")
        assert widget._state.value == "warning"
        assert widget._text_label.text() == "Alert"

    def test_indicator_action_updates_widget_and_action(self, qtbot):
        qt_toolbar = QToolBar()
        qtbot.addWidget(qt_toolbar)

        action = StatusIndicatorAction(text="Ready", tooltip="Initial")
        action.add_to_toolbar(qt_toolbar, qt_toolbar)

        action.set_tooltip("Updated tooltip")
        action.set_text("Running")

        assert action.action.toolTip() == "Updated tooltip"
        assert action.widget.toolTip() == "Updated tooltip"  # type: ignore[union-attr]
        assert action.widget._text_label.text() == "Running"  # type: ignore[union-attr]


class TestStatusBar:
    """Status bar + broker integration using fake redis client (mocked_client)."""

    @pytest.fixture(params=[{}, {"names": ["alpha"]}])
    def status_toolbar(self, qtbot, mocked_client, request):
        broker = BECStatusBroker(client=mocked_client)
        toolbar = create_widget(qtbot, StatusToolBar, **request.param)
        yield toolbar
        broker.reset_singleton()

    def test_allowed_names_precreates_placeholder(self, status_toolbar):
        status_toolbar.broker.refresh_available = lambda: None
        status_toolbar.refresh_from_broker()

        # We parametrize the fixture so one invocation has allowed_names set.
        if status_toolbar.allowed_names:
            name = next(iter(status_toolbar.allowed_names))
            assert status_toolbar.components.exists(name)
            act = status_toolbar.components.get_action(name)
            assert isinstance(act, StatusIndicatorAction)
            assert act.widget._text_label.text() == name  # type: ignore[union-attr]

    def test_on_available_adds_and_removes(self, status_toolbar):
        conditions = [
            BeamlineConditionUpdateEntry(name="c1", title="Cond 1", condition_type="test"),
            BeamlineConditionUpdateEntry(name="c2", title="Cond 2", condition_type="test"),
        ]
        status_toolbar.on_available_updated(conditions)
        assert status_toolbar.components.exists("c1")
        assert status_toolbar.components.exists("c2")

        conditions2 = [
            BeamlineConditionUpdateEntry(name="c1", title="Cond 1", condition_type="test")
        ]
        status_toolbar.on_available_updated(conditions2)
        assert status_toolbar.components.exists("c1")
        assert not status_toolbar.components.exists("c2")

    def test_on_status_updated_sets_title_and_message(self, status_toolbar):
        status_toolbar.add_status_item("beam", text="Initial", state="default", tooltip=None)
        payload = {"name": "beam", "status": "warning", "title": "New Title", "message": "Detail"}
        status_toolbar.on_status_updated("beam", payload)

        action = status_toolbar.components.get_action("beam")
        assert isinstance(action, StatusIndicatorAction)
        assert action.widget._text_label.text() == "New Title"  # type: ignore[union-attr]
        assert action.action.toolTip() == "Detail"

    def test_on_status_updated_keeps_existing_text_when_no_title(self, status_toolbar):
        status_toolbar.add_status_item("beam", text="Keep Me", state="default", tooltip=None)
        payload = {"name": "beam", "status": "normal", "message": "Note"}
        status_toolbar.on_status_updated("beam", payload)

        action = status_toolbar.components.get_action("beam")
        assert isinstance(action, StatusIndicatorAction)
        assert action.widget._text_label.text() == "Keep Me"  # type: ignore[union-attr]
        assert action.action.toolTip() == "Note"
