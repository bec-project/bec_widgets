from unittest.mock import MagicMock

from bec_widgets.widgets.plots.waveform.utils.alignment_panel import WaveformAlignmentPanel

from .client_mocks import mocked_client
from .conftest import create_widget


def test_alignment_panel_forwards_position_and_target_signals(qtbot, mocked_client):
    panel = create_widget(qtbot, WaveformAlignmentPanel, client=mocked_client)

    position_callback = MagicMock()
    target_toggle_callback = MagicMock()
    target_move_callback = MagicMock()

    panel.position_readback_changed.connect(position_callback)
    panel.target_toggled.connect(target_toggle_callback)
    panel.target_move_requested.connect(target_move_callback)

    panel.positioner.position_update.emit(1.25)
    panel.target_toggle.setChecked(True)
    panel.move_to_target_button.setEnabled(True)
    panel.move_to_target_button.click()

    position_callback.assert_called_once_with(1.25)
    target_toggle_callback.assert_called_once_with(True)
    target_move_callback.assert_called_once_with()


def test_alignment_panel_emits_only_center_fit_actions(qtbot, mocked_client):
    panel = create_widget(qtbot, WaveformAlignmentPanel, client=mocked_client)

    fit_center_callback = MagicMock()
    panel.fit_center_requested.connect(fit_center_callback)

    panel.fit_dialog.move_action.emit(("sigma", 0.5))
    fit_center_callback.assert_not_called()

    panel.fit_dialog.move_action.emit(("center", 2.5))
    fit_center_callback.assert_called_once_with(2.5)
