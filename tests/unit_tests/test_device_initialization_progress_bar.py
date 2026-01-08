# pylint skip
import pytest
from bec_lib.messages import DeviceInitializationProgressMessage

from bec_widgets.widgets.progress.device_initialization_progress_bar.device_initialization_progress_bar import (
    DeviceInitializationProgressBar,
)


@pytest.fixture
def progress_bar(qtbot):
    widget = DeviceInitializationProgressBar()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_progress_bar_initialization(progress_bar):
    """Test the initial state of the DeviceInitializationProgressBar."""
    assert progress_bar.failed_devices == []
    assert progress_bar._user_value == 0
    assert progress_bar._user_maximum == 1
    assert progress_bar.toolTip() == "No device initialization failures."


def test_update_device_initialization_progress(progress_bar, qtbot):
    """Test updating the progress bar with different device initialization messages."""

    # I. Update with message of running DeviceInitializationProgressMessage, finished=False, success=False
    msg = DeviceInitializationProgressMessage(
        device="DeviceA", index=1, total=3, finished=False, success=False
    )

    progress_bar._update_device_initialization_progress(msg.model_dump(), {})
    assert progress_bar._user_value == 1
    assert progress_bar._user_maximum == 3
    assert (
        f"Device initialization for '{msg.device}' is in progress..."
        in progress_bar.center_label.text()
    )

    # II. Update with message of finished DeviceInitializationProgressMessage, finished=True, success=True
    msg.finished = True
    msg.success = True
    progress_bar._update_device_initialization_progress(msg.model_dump(), {})
    assert progress_bar._user_value == 1
    assert progress_bar._user_maximum == 3
    assert (
        f"Device initialization for '{msg.device}' succeeded!" in progress_bar.center_label.text()
    )

    # III. Update with message of finished DeviceInitializationProgressMessage, finished=True, success=False
    msg.finished = True
    msg.success = False
    msg.device = "DeviceB"
    msg.index = 2
    with qtbot.waitSignal(progress_bar.failed_devices_changed) as signal_blocker:
        progress_bar._update_device_initialization_progress(msg.model_dump(), {})
        assert progress_bar._user_value == 2
        assert progress_bar._user_maximum == 3
        assert (
            f"Device initialization for '{msg.device}' failed!" in progress_bar.center_label.text()
        )
        assert signal_blocker.args == [[msg.device]]

        assert progress_bar.toolTip() == f"Failed devices: {msg.device}"
