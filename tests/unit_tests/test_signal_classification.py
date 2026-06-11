from types import SimpleNamespace

from bec_widgets.utils.signal_classification import (
    SignalCategory,
    classify_device_signal,
    classify_signal_info,
)


def _info(signal_class=None, role=None, with_embedded=False):
    info = {"signal_class": signal_class, "component_name": "comp", "obj_name": "dev_comp"}
    if with_embedded:
        info["describe"] = {"signal_info": {"role": role or "main", "signals": [["comp", 5]]}}
    return info


def _device(signals: dict):
    return SimpleNamespace(_info={"signals": signals})


def test_sync_signal_classes_are_sync():
    for cls in ("Signal", "EpicsSignal", "EpicsSignalRO", "SetableSignal", "ReadOnlySignal"):
        assert classify_signal_info(_info(signal_class=cls)) == SignalCategory.SYNC


def test_async_signal_classes_are_async():
    for cls in ("AsyncSignal", "AsyncMultiSignal", "DynamicSignal"):
        assert classify_signal_info(_info(signal_class=cls)) == SignalCategory.ASYNC


def test_dynamic_signal_subclass_detected_via_embedded_info():
    """A DynamicSignal subclass serializes its concrete class name; the
    embedded signal_info block must still classify it as async."""
    info = _info(signal_class="MyBeamlineAsyncSignal", with_embedded=True)
    assert classify_signal_info(info) == SignalCategory.ASYNC


def test_non_curve_roles_are_unknown():
    for role in ("preview", "diagnostic", "file_event", "progress"):
        info = _info(signal_class="PreviewSignal", role=role, with_embedded=True)
        assert classify_signal_info(info) == SignalCategory.UNKNOWN


def test_missing_or_empty_info_is_unknown():
    assert classify_signal_info(None) == SignalCategory.UNKNOWN
    assert classify_signal_info({}) == SignalCategory.UNKNOWN
    assert classify_signal_info({"signal_class": None}) == SignalCategory.UNKNOWN


def test_monitored_device_with_mixed_signals():
    """One (monitored) device exposing both
    a synchronous and an asynchronous signal must classify per signal, not
    per device."""

    device = _device(
        {
            "readback": _info(signal_class="Signal"),
            "stream": _info(signal_class="AsyncSignal"),
            "multi": _info(signal_class="AsyncMultiSignal"),
        }
    )
    assert classify_device_signal(device, "readback") == SignalCategory.SYNC
    assert classify_device_signal(device, "stream") == SignalCategory.ASYNC
    assert classify_device_signal(device, "multi") == SignalCategory.ASYNC


def test_entry_resolved_via_obj_name():
    info = _info(signal_class="AsyncSignal")
    info["obj_name"] = "dev1_stream"
    device = _device({"stream": info})
    assert classify_device_signal(device, "dev1_stream") == SignalCategory.ASYNC


def test_unresolvable_device_or_entry_is_unknown():
    assert classify_device_signal(None, "x") == SignalCategory.UNKNOWN
    assert classify_device_signal(SimpleNamespace(), "x") == SignalCategory.UNKNOWN
    assert classify_device_signal(_device({}), "missing") == SignalCategory.UNKNOWN
    assert classify_device_signal(_device({"a": _info("Signal")}), "") == SignalCategory.UNKNOWN
