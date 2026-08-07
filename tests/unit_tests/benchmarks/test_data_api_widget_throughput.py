"""
Comparative throughput benchmark of the DataAPI widget rendering path.

Feeds one async 'add' source through the waveform's ``_on_data_update``
(``curve.setData`` mocked out, isolating the data-path cost) and compares it
with a main-style baseline: one ``np.hstack`` of (buffer, fragment) per
readback message for the same total data. The DataAPI path receives the data
in coalesced emissions (10 fragments per emission) and renders each one
incrementally, so it must not be slower than the per-message baseline.
"""

from __future__ import annotations

import sys
import time
from unittest.mock import MagicMock

import numpy as np
import pytest
from bec_lib.data_api.models import SourceData, SubscriptionUpdate

from bec_widgets.widgets.plots.waveform.waveform import Waveform
from tests.unit_tests.client_mocks import mocked_client
from tests.unit_tests.conftest import create_widget

N_EMISSIONS = 150
FRAGMENTS_PER_EMISSION = 10
SAMPLES_PER_FRAGMENT = 500
#: Timing rounds per path; the best round is compared (filters scheduler noise).
ROUNDS = 2


@pytest.fixture
def waveform_widget(qtbot, mocked_client, monkeypatch):
    """A Waveform with a stubbed data bridge and one async curve."""

    def factory(client, sources, scan="live", parent=None, **kwargs):
        bridge = MagicMock()
        bridge.sources = list(sources)
        bridge.scan_id = None if scan == "live" else scan
        bridge.healthy = True
        return bridge

    monkeypatch.setattr("bec_widgets.widgets.plots.waveform.waveform.QtDataSubscription", factory)
    wf = create_widget(qtbot, Waveform, client=mocked_client)
    yield wf


def _build_updates(fragments: list[np.ndarray]) -> list[SubscriptionUpdate]:
    """
    One SubscriptionUpdate per emission, each snapshot extending the previous
    one by FRAGMENTS_PER_EMISSION fragments. The fragment objects are shared
    between snapshots, mimicking the backend's snapshot reuse.
    """
    updates = []
    metadata = {"async_update_type": "add", "max_shape": [None], "acquisition_group": None}
    for emission in range(N_EMISSIONS):
        n_fragments = (emission + 1) * FRAGMENTS_PER_EMISSION
        ordinals = tuple(range(n_fragments))
        source = SourceData(
            device="async_device",
            entry="async_device",
            kind="async",
            ordinals=ordinals,
            values=tuple(fragments[:n_fragments]),
            timestamps=tuple(float(i) for i in ordinals),
            complete=True,
            metadata=metadata,
        )
        updates.append(
            SubscriptionUpdate(
                scan_id="benchmark_scan",
                reason="live",
                sources={source.key: source},
                aligned_ordinals=ordinals,
                complete=True,
                metadata={"group": "scan"},
            )
        )
    return updates


def _measure_dataapi(wf: Waveform, curve, updates: list[SubscriptionUpdate]) -> float:
    """Time one full pass of the DataAPI path over all emissions."""
    curve._data_api_async_cache = None  # each pass starts from an empty cache
    start = time.perf_counter()
    for update in updates:
        wf._on_data_update(update)
    return time.perf_counter() - start


def _measure_baseline(fragments: list[np.ndarray]) -> tuple[float, np.ndarray]:
    """Time main's per-message loop: one np.hstack of (buffer, fragment) each."""
    start = time.perf_counter()
    buffer = np.empty(0)
    for fragment in fragments:
        buffer = np.hstack((buffer, fragment))
    return time.perf_counter() - start, buffer


def test_data_api_waveform_throughput(waveform_widget, monkeypatch):
    """
    The DataAPI rendering path (coalesced emissions, incremental append) must
    match the per-message cost of main's incremental hstack loop for the same
    total data.
    """
    wf = waveform_widget
    curve = wf.plot(arg1="async_device", label="async_device-async_device")
    wf.scan_id = "benchmark_scan"
    wf.x_axis_mode["name"] = "index"
    monkeypatch.setattr(curve, "setData", lambda *args, **kwargs: None)

    rng = np.random.default_rng(42)
    total_fragments = N_EMISSIONS * FRAGMENTS_PER_EMISSION
    fragments = [rng.random(SAMPLES_PER_FRAGMENT) for _ in range(total_fragments)]
    updates = _build_updates(fragments)

    # The mocked BEC client keeps polling threads alive; every numpy GIL
    # release then stalls the timed loop for up to the thread switch interval
    # (5 ms by default), swamping the actual computation. A short interval
    # during the measurement removes that scheduler noise for both paths.
    switch_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-4)
    try:
        # Warm-up: fault in pages and settle CPU scheduling before timing.
        _measure_baseline(fragments[: total_fragments // 5])
        _measure_dataapi(wf, curve, updates[: N_EMISSIONS // 5])

        # Alternate the measurement order between rounds and keep the best
        # round of each path.
        dataapi_times: list[float] = []
        baseline_times: list[float] = []
        baseline_buffer = None
        for round_index in range(ROUNDS):
            if round_index % 2 == 0:
                baseline_time, baseline_buffer = _measure_baseline(fragments)
                baseline_times.append(baseline_time)
                dataapi_times.append(_measure_dataapi(wf, curve, updates))
            else:
                dataapi_times.append(_measure_dataapi(wf, curve, updates))
                baseline_time, baseline_buffer = _measure_baseline(fragments)
                baseline_times.append(baseline_time)
    finally:
        sys.setswitchinterval(switch_interval)
    dataapi_time = min(dataapi_times)
    baseline_time = min(baseline_times)

    # Both paths must have produced the identical series.
    rendered = wf._async_display_values_cached(
        curve, updates[-1], updates[-1].sources[("async_device", "async_device")]
    )
    np.testing.assert_array_equal(rendered, baseline_buffer)

    print(
        f"\nDataAPI path: {dataapi_time * 1000:.1f} ms for {N_EMISSIONS} emissions "
        f"({total_fragments} fragments, {baseline_buffer.size} samples); "
        f"main-style per-message baseline: {baseline_time * 1000:.1f} ms"
    )
    assert dataapi_time <= baseline_time * 1.5, (
        f"DataAPI rendering path too slow: {dataapi_time:.3f}s vs " f"baseline {baseline_time:.3f}s"
    )
