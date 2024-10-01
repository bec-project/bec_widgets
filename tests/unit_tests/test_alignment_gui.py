from unittest import mock

import pytest
from bec_lib import messages

from bec_widgets.applications.alignment.alignment_1d.alignment_1d import Alignment1D

from .client_mocks import mocked_client
from .conftest import create_widget


@pytest.fixture(scope="function")
def alignment_1d(qtbot, mocked_client):
    """Fixture for Alignment1D widget"""
    with mock.patch(
        "bec_widgets.applications.alignment.alignment_1d.alignment_1d.Alignment1D.init_ui"
    ):
        widget = create_widget(qtbot, Alignment1D, client=mocked_client)
        yield widget


def test_scan_status_callback(qtbot, alignment_1d):
    """Test the scan status callback."""
    container = []

    def callback(*args, **kwargs):
        """Callback function to store signal calls."""
        container.append(args)

    alignment_1d.motion_is_active.connect(callback)
    with mock.patch.object(alignment_1d, "enable_ui") as mock_enable_ui:
        for status in ["open", "aborted", "halted", "closed"]:
            msg = messages.ScanStatusMessage(scan_id="tmp_id", status=status, info={})
            alignment_1d.scan_status_callback(msg.content, {})
            qtbot.wait(100)
            if status in ["open"]:
                assert mock.call(False) == mock_enable_ui.call_args_list[-1]
                assert container[-1] == (True,)
            else:
                assert mock.call(True) == mock_enable_ui.call_args_list[-1]
                assert container[-1] == (False,)
        container.clear()
        alignment_1d.scan_status_callback({"status": "invalid_status"}, {})
        qtbot.wait(100)
        assert not container
