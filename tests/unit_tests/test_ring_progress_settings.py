import pytest

from bec_widgets.utils.settings_dialog import SettingsDialog
from bec_widgets.widgets.progress.ring_progress_bar.ring_progress_bar import RingProgressBar
from bec_widgets.widgets.progress.ring_progress_bar.ring_progress_settings_cards import RingSettings
from tests.unit_tests.client_mocks import mocked_client


@pytest.fixture
def ring_progress_bar_widget(qtbot, mocked_client):
    widget = RingProgressBar(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.fixture
def rpb_settings_dialog(qtbot, ring_progress_bar_widget):
    settings = RingSettings(
        parent=ring_progress_bar_widget, target_widget=ring_progress_bar_widget, popup=True
    )
    dialog = SettingsDialog(
        ring_progress_bar_widget,
        settings_widget=settings,
        window_title="Ring Progress Bar Settings",
        modal=False,
    )
    qtbot.addWidget(dialog)
    qtbot.waitExposed(dialog)
    yield dialog


@pytest.fixture
def rpb_settings_dialog_with_rings(qtbot, ring_progress_bar_widget):
    ring_progress_bar_widget.add_ring()
    ring_progress_bar_widget.add_ring()
    settings = RingSettings(
        parent=ring_progress_bar_widget, target_widget=ring_progress_bar_widget, popup=True
    )
    dialog = SettingsDialog(
        ring_progress_bar_widget,
        settings_widget=settings,
        window_title="Ring Progress Bar Settings",
        modal=False,
    )
    qtbot.addWidget(dialog)
    qtbot.waitExposed(dialog)
    yield dialog


def test_ring_progress_settings_dialog_opens(rpb_settings_dialog):
    """Test that the Ring Progress Bar settings dialog opens correctly."""
    dialog = rpb_settings_dialog
    dialog.show()
    assert dialog.isVisible()
    assert dialog.windowTitle() == "Ring Progress Bar Settings"
    dialog.accept()


def test_ring_progress_settings_dialog_with_rings(rpb_settings_dialog_with_rings):
    """Test that the Ring Progress Bar settings dialog opens correctly with rings."""
    dialog = rpb_settings_dialog_with_rings
    dialog.show()
    assert dialog.isVisible()
    assert dialog.windowTitle() == "Ring Progress Bar Settings"
    dialog.accept()  # Close the dialog
