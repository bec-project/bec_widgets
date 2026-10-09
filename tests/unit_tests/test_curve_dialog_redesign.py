"""Tests for the redesigned curve settings dialog (shared model, QWidget and QML views)."""

# pylint: disable=redefined-outer-name,protected-access

import json

import numpy as np
import pytest

from bec_widgets.tests.client_mocks import dap_plugin_message, mocked_client, mocked_client_with_dap
from bec_widgets.utils.settings_dialog import SettingsDialog
from bec_widgets.widgets.plots.waveform.settings.curve_dialog.curve_dialog_common import (
    create_curve_setting,
    curve_dialog_variant,
)
from bec_widgets.widgets.plots.waveform.settings.curve_dialog.curve_dialog_model import (
    CurveDialogModel,
    normalize_dap,
)
from bec_widgets.widgets.plots.waveform.settings.curve_dialog.curve_dialog_qml import (
    CurveSettingsQml,
)
from bec_widgets.widgets.plots.waveform.settings.curve_dialog.curve_dialog_qwidget import (
    CurveSettingsQWidget,
)
from bec_widgets.widgets.plots.waveform.settings.curve_settings.curve_setting import CurveSetting
from bec_widgets.widgets.plots.waveform.settings.curve_settings.curve_tree import CurveTree
from bec_widgets.widgets.plots.waveform.waveform import Waveform
from tests.unit_tests.conftest import create_widget


@pytest.fixture
def waveform(qtbot, mocked_client_with_dap):
    """Waveform with two device curves, a fit and a custom curve."""
    wf = create_widget(qtbot, Waveform, client=mocked_client_with_dap)
    wf.plot(arg1="bpm4i", dap="GaussianModel")
    wf.plot(arg1="bpm3a")
    wf.plot(x=np.arange(5), y=np.arange(5), label="reference")
    return wf


def _labels(wf):
    return sorted(c.name() for c in wf.curves)


def test_normalize_dap():
    assert normalize_dap(None) == ["GaussianModel"]
    assert normalize_dap("LorentzModel") == ["LorentzModel"]
    assert normalize_dap(["A", "B", "A", ""]) == ["A", "B"]


def test_model_loads_curves_fits_and_custom(waveform):
    model = CurveDialogModel(waveform)
    kinds = [(d.kind, d.parent_uid is not None) for d in model.drafts]
    assert kinds == [("device", False), ("dap", True), ("device", False), ("custom", False)]
    assert model.selected_uid == model.drafts[0].uid
    rows = model.rows()
    assert rows[1]["subtitle"] == "fit of bpm4i"
    assert rows[3]["tag"] == "custom"
    assert model.validate() == {}


def test_model_export_matches_legacy_tree(qtbot, waveform):
    """Without edits the new model exports the same curves as the legacy tree."""
    model = CurveDialogModel(waveform)
    tree = create_widget(qtbot, CurveTree, waveform=waveform)
    legacy = {c["label"]: c for c in tree.export_all_curves()}
    new = {c["label"]: c for c in model.export_curves()}
    assert set(new) == set(legacy)
    for label, config in new.items():
        for key in ("source", "color", "pen_style", "pen_width", "symbol_size", "parent_label"):
            assert config[key] == legacy[label][key], (label, key)
        assert config["signal"]["device"] == legacy[label]["signal"]["device"]
        assert config["signal"]["dap"] == legacy[label]["signal"]["dap"]


def test_add_curve_picks_first_hint_and_free_color(waveform):
    model = CurveDialogModel(waveform)
    used = {d.config.color for d in model.drafts}
    uid = model.add_curve("samx")
    draft = model.draft(uid)
    assert model.selected_uid == uid
    assert draft.signal == "samx"
    assert draft.config.color not in used
    model.apply()
    assert "samx-samx" in _labels(waveform)
    assert "reference" in _labels(waveform)


def test_add_fit_and_composite(waveform):
    model = CurveDialogModel(waveform)
    parent = next(d for d in model.drafts if d.device == "bpm3a")
    fit = model.add_fit(parent.uid)
    model.toggle_extra_model(fit, "LorentzModel")
    assert model.draft(fit).models == ["GaussianModel", "LorentzModel"]
    model.set_primary_model(fit, "LorentzModel")
    assert model.draft(fit).models == ["LorentzModel"]
    model.toggle_extra_model(fit, "SineModel")
    model.apply()
    assert "bpm3a-bpm3a-LorentzModel+SineModel" in _labels(waveform)


def test_fit_parameters_kept_only_while_model_unchanged(waveform):
    curve = next(c for c in waveform.curves if c.config.source == "dap")
    curve.config.signal.dap_parameters = {"amplitude": {"value": 2.0}}
    model = CurveDialogModel(waveform)
    fit = next(d for d in model.drafts if d.kind == "dap")
    assert model.export_curves()[1]["signal"]["dap_parameters"] == {"amplitude": {"value": 2.0}}
    model.set_primary_model(fit.uid, "LorentzModel")
    exported = next(c for c in model.export_curves() if c["source"] == "dap")
    assert exported["signal"]["dap_parameters"] is None


def test_remove_curve_removes_its_fits_but_never_custom(waveform):
    model = CurveDialogModel(waveform)
    top = model.drafts[0]
    model.remove(top.uid)
    assert all(d.parent_uid != top.uid for d in model.drafts)
    custom = next(d for d in model.drafts if d.kind == "custom")
    model.remove(custom.uid)
    assert model.draft(custom.uid) is not None
    model.apply()
    assert _labels(waveform) == ["bpm3a-bpm3a", "reference"]


def test_validation_blocks_apply(waveform):
    model = CurveDialogModel(waveform)
    uid = model.add_curve("")
    assert model.validate()[uid] == "Choose a device."
    with pytest.raises(ValueError):
        model.apply()
    model.set_device(uid, "bpm4i")
    assert model.validate()[uid] == "The same curve is already listed."
    model.set_device(uid, "samy")
    assert uid not in model.validate()
    model.set_x_mode("device")
    assert model.x_axis_error()
    model.set_x_device("samx")
    assert model.x_signal == "samx"
    model.apply()
    assert waveform.x_axis_mode["name"] == "samx"


def test_style_edits_reach_device_and_custom_curves(waveform):
    model = CurveDialogModel(waveform)
    top = model.drafts[0]
    custom = next(d for d in model.drafts if d.kind == "custom")
    model.set_style(top.uid, "pen_style", "dash")
    model.set_style(top.uid, "pen_width", 50)
    model.set_style(top.uid, "symbol", "")
    model.set_style(custom.uid, "color", "#123456")
    model.apply()
    curves = {c.name(): c for c in waveform.curves}
    assert curves["bpm4i-bpm4i"].config.pen_style == "dash"
    assert curves["bpm4i-bpm4i"].config.pen_width == 20
    assert curves["bpm4i-bpm4i"].config.symbol is None
    assert curves["reference"].config.color == "#123456"


def test_palette_recolors_all(waveform):
    model = CurveDialogModel(waveform)
    model.set_palette("viridis")
    colors = [d.config.color for d in model.drafts]
    assert len(set(colors)) == len(colors)
    model.apply()
    assert waveform.color_palette == "viridis"


def test_history_scan_selection(waveform, scan_history_factory):
    from bec_widgets.tests.client_mocks import inject_scan_history

    inject_scan_history(waveform, scan_history_factory, ("scan-a", 7))
    # inject_scan_history fills the scan ids only
    waveform.client.history._scan_numbers.append(7)
    model = CurveDialogModel(waveform)
    assert model.scans()[1] == ("Scan #7", "scan-a")
    top = model.drafts[0]
    model.set_scan(top.uid, "scan-a")
    assert model.row(top)["subtitle"] == "bpm4i · scan #7"
    exported = model.export_curves()[0]
    assert exported["source"] == "history"
    assert exported["label"] == "bpm4i-bpm4i-scan-7"
    # the fit follows the renamed parent
    assert model.export_curves()[1]["parent_label"] == "bpm4i-bpm4i-scan-7"


def test_variant_from_environment(monkeypatch, waveform, qtbot):
    monkeypatch.delenv("BEC_CURVE_DIALOG", raising=False)
    assert curve_dialog_variant() == "legacy"
    monkeypatch.setenv("BEC_CURVE_DIALOG", "QML")
    assert curve_dialog_variant() == "qml"
    monkeypatch.setenv("BEC_CURVE_DIALOG", "nonsense")
    assert curve_dialog_variant() == "legacy"
    widget = create_curve_setting(waveform, "legacy")
    qtbot.addWidget(widget)
    assert isinstance(widget, CurveSetting)


@pytest.mark.parametrize("cls", [CurveSettingsQWidget, CurveSettingsQml])
def test_views_apply_through_settings_dialog(qtbot, waveform, cls):
    widget = cls(parent=waveform, target_widget=waveform)
    dialog = SettingsDialog(waveform, settings_widget=widget, window_title="Curves")
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    widget.model.add_curve("samx")
    qtbot.wait(20)
    dialog.apply_changes()
    assert "samx-samx" in _labels(waveform)
    dialog.reject()


def test_qwidget_view_follows_model(qtbot, waveform):
    widget = CurveSettingsQWidget(parent=None, target_widget=waveform)
    qtbot.addWidget(widget)
    widget.show()
    model = widget.model
    assert len(widget.curve_list.rows) == 4
    assert widget.count_badge._count == 3
    fit = model.drafts[1]
    model.select(fit.uid)
    assert widget._inspector_uid == fit.uid
    assert not widget.device_picker.isVisible()
    model.select(model.drafts[0].uid)
    assert widget.device_picker.currentText() == "bpm4i"
    # picking a device in the inspector changes the curve and resets its signal
    widget.device_picker.picker_controller.picked.emit("samy")
    assert model.drafts[0].device == "samy"
    assert model.drafts[0].signal == "samy"
    # the add picker adds a curve
    widget.add_picker.picker_controller.picked.emit("samz")
    assert model.selected.device == "samz"
    assert len(widget.curve_list.rows) == 5
    # an incomplete curve shows the problem banner
    model.add_curve("")
    assert not widget.problem_banner.isHidden()
    widget.curve_list.delete_requested.emit(model.selected_uid)
    assert widget.problem_banner.isHidden()
    widget.cleanup()


def test_qml_view_backend(qtbot, waveform):
    widget = CurveSettingsQml(parent=None, target_widget=waveform)
    qtbot.addWidget(widget)
    widget.show()
    backend = widget.backend
    assert backend.curveCount == 3
    assert len(backend.rows) == 4
    assert backend.selected["device"] == "bpm4i"
    backend.move(1)
    assert backend.selected["kind"] == "dap"
    assert [e["name"] for e in backend.selected["extras"]] == ["LorentzModel", "SineModel"]
    backend.toggleExtraModel(backend.selected["uid"], "SineModel")
    assert backend.selected["extras"][1]["checked"]
    backend.setStyle(backend.selected["uid"], "pen_style", "dot")
    assert backend.selected["penStyle"] == "dot"
    # a picker request anchors the QML popup and the pick adds a curve
    backend.openPicker("add", 10, 10, 200, 30)
    qtbot.wait(50)
    assert widget.device_picker.is_popup_open()
    widget.device_picker.picker_controller.picked.emit("samx")
    assert backend.selected["device"] == "samx"
    backend.setXMode(3)
    assert backend.xInvalid
    backend.openPicker("xdevice", 10, 10, 200, 30)
    widget.device_picker.picker_controller.picked.emit("samy")
    assert backend.xDevice == "samy" and not backend.xInvalid
    widget.cleanup()


def test_waveform_opens_chosen_variant(qtbot, monkeypatch, waveform):
    monkeypatch.setenv("BEC_CURVE_DIALOG", "qwidget")
    waveform.show_curve_settings_popup()
    assert isinstance(waveform.curve_settings_dialog.widget, CurveSettingsQWidget)
    waveform.curve_settings_dialog.reject()


def test_adding_a_plotted_device_selects_its_curve(waveform):
    model = CurveDialogModel(waveform)
    count = len(model.drafts)
    model.select(model.drafts[-1].uid)
    uid = model.add_curve("bpm4i")
    assert len(model.drafts) == count
    assert uid == model.drafts[0].uid == model.selected_uid


def test_fit_of_custom_curve_addresses_parent_by_label(waveform):
    model = CurveDialogModel(waveform)
    custom = next(d for d in model.drafts if d.kind == "custom")
    model.add_fit(custom.uid, "LorentzModel")
    model.apply()
    fit = next(c for c in waveform.curves if c.name() == "reference-LorentzModel")
    assert fit.config.signal.device == "reference"
    assert fit.config.signal.signal == "custom"
    assert fit.config.parent_label == "reference"
