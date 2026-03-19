from unittest.mock import MagicMock

import numpy as np
import pyqtgraph as pg

from bec_widgets.widgets.plots.waveform.utils.alignment_controller import (
    AlignmentContext,
    WaveformAlignmentController,
)
from bec_widgets.widgets.plots.waveform.utils.alignment_panel import WaveformAlignmentPanel

from .client_mocks import mocked_client
from .conftest import create_widget
from .test_waveform import make_alignment_fit_summary


def create_alignment_controller(qtbot, mocked_client):
    plot_widget = pg.PlotWidget()
    qtbot.addWidget(plot_widget)
    panel = create_widget(qtbot, WaveformAlignmentPanel, client=mocked_client)
    controller = WaveformAlignmentController(plot_widget.plotItem, panel, parent=plot_widget)
    return plot_widget, panel, controller


def test_alignment_controller_shows_marker_only_when_visible(qtbot, mocked_client):
    _, panel, controller = create_alignment_controller(qtbot, mocked_client)

    controller.update_context(
        AlignmentContext(visible=False, positioner_name="samx", precision=3, readback=1.0)
    )
    controller.update_position(4.2)
    assert controller.marker_line is None

    controller.update_context(
        AlignmentContext(visible=True, positioner_name="samx", precision=3, readback=4.2)
    )

    assert controller.marker_line is not None
    assert np.isclose(controller.marker_line.value(), 4.2)
    assert panel.target_toggle.isEnabled() is True

    controller.update_context(AlignmentContext(visible=False, positioner_name="samx"))
    assert controller.marker_line is None


def test_alignment_controller_target_line_uses_readback_and_limits(qtbot, mocked_client):
    _, panel, controller = create_alignment_controller(qtbot, mocked_client)

    controller.update_context(
        AlignmentContext(
            visible=True, positioner_name="samx", precision=3, limits=(0.0, 2.0), readback=5.0
        )
    )

    panel.target_toggle.setChecked(True)
    assert controller.target_line is not None
    assert np.isclose(controller.target_line.value(), 2.0)

    panel.target_toggle.setChecked(False)
    assert controller.target_line is None

    controller.update_context(
        AlignmentContext(
            visible=True, positioner_name="samx", precision=3, limits=None, readback=5.0
        )
    )
    panel.target_toggle.setChecked(True)
    assert controller.target_line is not None
    assert np.isclose(controller.target_line.value(), 5.0)


def test_alignment_controller_preserves_dragged_target_on_context_refresh(qtbot, mocked_client):
    _, panel, controller = create_alignment_controller(qtbot, mocked_client)

    controller.update_context(
        AlignmentContext(
            visible=True, positioner_name="samx", precision=3, limits=(0.0, 5.0), readback=1.0
        )
    )
    panel.target_toggle.setChecked(True)
    controller.target_line.setValue(3.0)

    controller.update_context(
        AlignmentContext(
            visible=True, positioner_name="samx", precision=3, limits=(0.0, 5.0), readback=2.0
        )
    )

    assert controller.target_line is not None
    assert np.isclose(controller.target_line.value(), 3.0)


def test_alignment_controller_emits_move_request_for_fit_center(qtbot, mocked_client):
    _, panel, controller = create_alignment_controller(qtbot, mocked_client)

    move_callback = MagicMock()
    controller.move_absolute_requested.connect(move_callback)

    controller.update_context(
        AlignmentContext(visible=True, positioner_name="samx", precision=3, readback=1.0)
    )
    controller.update_dap_summary(make_alignment_fit_summary(center=2.5), {"curve_id": "fit"})

    assert panel.fit_dialog.action_buttons["center"].isEnabled() is True
    panel.fit_dialog.action_buttons["center"].click()

    move_callback.assert_called_once_with(2.5)


def test_alignment_controller_emits_move_request_for_target(qtbot, mocked_client):
    _, panel, controller = create_alignment_controller(qtbot, mocked_client)

    move_callback = MagicMock()
    controller.move_absolute_requested.connect(move_callback)

    controller.update_context(
        AlignmentContext(
            visible=True, positioner_name="samx", precision=3, limits=(0.0, 5.0), readback=1.0
        )
    )
    panel.target_toggle.setChecked(True)
    controller.target_line.setValue(1.25)
    panel.move_to_target_button.click()

    move_callback.assert_called_once_with(1.25)


def test_alignment_controller_removes_deleted_dap_curve(qtbot, mocked_client):
    _, panel, controller = create_alignment_controller(qtbot, mocked_client)

    controller.update_context(
        AlignmentContext(visible=True, positioner_name="samx", precision=3, readback=1.0)
    )
    controller.update_dap_summary(make_alignment_fit_summary(center=1.5), {"curve_id": "fit"})

    assert "fit" in panel.fit_dialog.summary_data

    controller.remove_dap_curve("fit")

    assert "fit" not in panel.fit_dialog.summary_data
    assert panel.fit_dialog.fit_curve_id is None
    assert panel.fit_dialog.enable_actions is False
