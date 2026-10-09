import math
from unittest import mock

import pytest
from qtpy.QtWidgets import QApplication

from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.dap.lmfit_dialog.compare_fit_dialogs import sample_fit
from bec_widgets.widgets.dap.lmfit_dialog.fit_dialog_factory import FIT_DIALOG_ENV, fit_dialog_class
from bec_widgets.widgets.dap.lmfit_dialog.fit_summary import FitParam, FitSummary, format_number
from bec_widgets.widgets.dap.lmfit_dialog.lmfit_dialog import LMFitDialog
from bec_widgets.widgets.dap.lmfit_dialog.lmfit_dialog_qml import LMFitDialogQml
from bec_widgets.widgets.dap.lmfit_dialog.lmfit_dialog_qwidget import LMFitDialogQWidget

GAUSS = "bpm4i-gauss"
BREIT = "diode-breit_wigner"
FAILED = "temp-lorentz"


@pytest.mark.parametrize(
    "value, expected",
    [
        (1.5824142042890903, "1.582"),
        (-2.8415356591834326, "−2.842"),
        (0.0002550847234503717, "2.551e−4"),
        (114893884.64553572, "1.149e8"),
        (0, "0"),
        (None, "—"),
        (math.inf, "∞"),
        (math.nan, "—"),
        (True, "—"),
    ],
)
def test_format_number(value, expected):
    assert format_number(value) == expected


def test_fit_summary_quality_and_flags():
    good = FitSummary.from_dap(GAUSS, sample_fit(GAUSS))
    assert good.model_name == "gaussian"
    assert good.quality == "good"
    assert not good.show_message
    assert [p.state for p in good.params] == ["ok", "ok", "ok", "derived"]

    loose = FitSummary.from_dap(BREIT, sample_fit(BREIT))
    assert loose.quality == "fair"
    assert loose.loose_params == ["sigma", "q"]
    sigma = loose.params[2]
    assert sigma.relative_error_text == ">999%"
    assert "Strongly correlated with q" in sigma.tooltip

    failed = FitSummary.from_dap(FAILED, sample_fit(FAILED))
    assert failed.quality == "failed"
    assert failed.model_name == "lorentzian + linear"
    assert failed.show_message
    assert [p.state for p in failed.params] == ["unknown", "unknown", "fixed"]


def test_fit_summary_tolerates_bad_input():
    assert FitSummary.from_dap("x", None).params == []
    summary = FitSummary.from_dap("x", {"params": [["a", 1.0], "bad", None]})
    assert [p.name for p in summary.params] == ["a"]
    assert FitParam.from_lmfit({"name": "b", "value": 0.0, "stderr": 0.1}).state == "ok"


@pytest.fixture(params=[LMFitDialogQWidget, LMFitDialogQml], ids=["qwidget", "qml"])
def dialog(request, qtbot, mocked_client):
    yield create_widget(qtbot, request.param, client=mocked_client)


def _feed(dialog, *curves):
    for curve_id in curves:
        dialog.update_summary_tree(sample_fit(curve_id), {"curve_id": curve_id})


def test_first_fit_is_selected_and_emitted(dialog):
    callback = mock.MagicMock()
    dialog.selected_fit.connect(callback)
    assert dialog.current_summary is None
    _feed(dialog, GAUSS, BREIT)
    assert dialog.fit_curve_id == GAUSS
    callback.assert_called_once_with(GAUSS)
    assert dialog.curve_ids == [GAUSS, BREIT]
    assert dialog.show_curve_selection()


def test_select_curve_switches_displayed_fit(dialog):
    _feed(dialog, GAUSS, BREIT)
    dialog.select_curve(BREIT)
    assert dialog.current_summary.model_name == "breit_wigner"


def test_always_show_latest_follows_updates(dialog):
    dialog.always_show_latest = True
    _feed(dialog, GAUSS, BREIT)
    assert dialog.fit_curve_id == BREIT


def test_remove_dap_data_switches_then_clears(dialog):
    callback = mock.MagicMock()
    _feed(dialog, GAUSS, BREIT)
    dialog.selected_fit.connect(callback)
    dialog.remove_dap_data(GAUSS)
    assert dialog.fit_curve_id == BREIT
    callback.assert_called_once_with(BREIT)
    dialog.remove_dap_data("not-there")
    assert dialog.curve_ids == [BREIT]
    dialog.remove_dap_data(BREIT)
    assert dialog.fit_curve_id is None
    assert dialog.current_summary is None


def test_move_action_and_enable_actions(dialog):
    received = []
    dialog.move_action.connect(received.append)
    dialog.active_action_list = ["center"]
    _feed(dialog, GAUSS)
    assert list(dialog.action_buttons) == ["center"]
    dialog.action_buttons["center"].click()
    assert received == [("center", sample_fit(GAUSS)["params"][1][1])]

    dialog.enable_actions = False
    assert dialog.action_buttons["center"].isEnabled() is False
    dialog.action_buttons["center"].click()
    dialog.request_move("center")
    assert len(received) == 1


def test_curve_selection_hidden_for_single_fit_or_by_property(dialog):
    _feed(dialog, GAUSS)
    assert not dialog.show_curve_selection()
    _feed(dialog, BREIT)
    dialog.hide_curve_selection = True
    assert not dialog.show_curve_selection()


def test_copy_to_clipboard(dialog):
    dialog.copy_to_clipboard("1.25")
    assert QApplication.clipboard().text() == "1.25"


def test_qwidget_view_renders_rows_and_buttons(qtbot, mocked_client):
    dialog = create_widget(qtbot, LMFitDialogQWidget, client=mocked_client)
    dialog.active_action_list = ["center"]
    _feed(dialog, GAUSS, FAILED)
    assert dialog.body.isVisibleTo(dialog)
    assert not dialog.empty_label.isVisibleTo(dialog)
    assert dialog.model_label.text() == "gaussian"
    assert dialog.quality_pill.text() == "Good fit"
    assert set(dialog._curve_buttons) == {GAUSS, FAILED}
    assert dialog._curve_buttons[GAUSS].isChecked()
    assert dialog._move_buttons["center"].isEnabled()

    dialog._curve_buttons[FAILED].click()
    assert dialog.fit_curve_id == FAILED
    assert dialog.quality_pill.text() == "Fit failed"
    assert "Fit aborted" in dialog.message_label.text()

    dialog.enable_actions = False
    assert not dialog._move_buttons["center"].isEnabled()


def test_qml_view_loads_and_exposes_state(qtbot, mocked_client):
    dialog = create_widget(qtbot, LMFitDialogQml, client=mocked_client)
    assert dialog.quick.errors() == []
    assert dialog.bridge.state["hasData"] is False
    dialog.active_action_list = ["center"]
    _feed(dialog, BREIT, GAUSS)
    state = dialog.bridge.state
    assert state["model"] == "breit_wigner"
    assert state["qualityLabel"] == "Fair fit"
    assert state["message"] == "Poorly constrained: sigma, q"
    assert [c["id"] for c in state["curves"]] == [BREIT, GAUSS]
    assert [p["movable"] for p in state["params"]] == [False, True, False, False]

    received = []
    dialog.move_action.connect(received.append)
    dialog.bridge.move("center")
    dialog.bridge.selectCurve(GAUSS)
    assert received and received[0][0] == "center"
    assert dialog.bridge.state["model"] == "gaussian"


@pytest.mark.parametrize(
    "value, cls", [("", LMFitDialog), ("qml", LMFitDialogQml), ("QWidget", LMFitDialogQWidget)]
)
def test_fit_dialog_factory(monkeypatch, value, cls):
    monkeypatch.setenv(FIT_DIALOG_ENV, value)
    assert fit_dialog_class() is cls
