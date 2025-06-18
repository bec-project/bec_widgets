from unittest.mock import ANY, MagicMock

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


def test_wait_for_reply_on_RID():
    ch = MagicMock(spec=ConfigHelper)
    ch.send_config_request.return_value = "abcde"
    cca = CommunicateConfigAction(config_helper=ch, device="samx", config={}, action="update")
    cca.run()
    ch.wait_for_config_reply.assert_called_with("abcde", timeout=ANY)
