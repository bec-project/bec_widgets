from unittest.mock import ANY, MagicMock, call

import pytest
from bec_lib.config_helper import ConfigHelper

from bec_widgets.widgets.services.device_browser.device_item.config_communicator import (
    CommunicateConfigAction,
)


def test_must_have_a_name(qtbot):
    error_occurred = False

    def oops():
        nonlocal error_occurred
        error_occurred = True

    c = CommunicateConfigAction(ConfigHelper(MagicMock()), device=None, config={}, action="add")
    c.signals.error.connect(oops)
    c.run()
    qtbot.waitUntil(lambda: error_occurred, timeout=100)


@pytest.mark.parametrize(
    ["action", "config", "error"],
    [("update", None, True), ("remove", None, False), ("add", {}, False)],
)
def test_action_config_match(action, config, error):
    def init():
        return CommunicateConfigAction(
            ConfigHelper(MagicMock()), device="test", config=config, action=action
        )

    if error:
        with pytest.raises(ValueError):
            init()
    else:
        assert init()


def test_wait_for_reply_on_RID():
    ch = MagicMock(spec=ConfigHelper)
    ch.send_config_request.return_value = "abcde"
    cca = CommunicateConfigAction(config_helper=ch, device="samx", config={}, action="update")
    cca.run()
    ch.wait_for_config_reply.assert_called_once_with("abcde", timeout=ANY)


def test_remove_readd_with_device_config(qtbot):
    ch = MagicMock(spec=ConfigHelper)
    ch.send_config_request.return_value = "abcde"
    cca = CommunicateConfigAction(
        config_helper=ch, device="samx", config={"deviceConfig": {"arg": "val"}}, action="update"
    )
    cca.run()
    ch.send_config_request.assert_has_calls(
        [
            call(action="remove", config=ANY, wait_for_response=False),
            call(action="add", config=ANY, wait_for_response=False),
        ]
    )


def test_cancel_config_action(qtbot):
    ch = MagicMock(spec=ConfigHelper)
    ch.send_config_request.return_value = "abcde"
    cca = CommunicateConfigAction(config_helper=ch, device=None, config=None, action="cancel")
    cca.run()
    ch.send_config_request.assert_called_once_with(
        action="cancel", config=None, wait_for_response=True, timeout_s=10
    )
