# Heatmap DataAPI draft — audit notes (`draft/heatmap_data_api`)

*Date: 2026-07-28. Audited head: `820afb20` ("wip"). Companion library audit with the full
54-finding registry: `bec_data_api/DATA_API_AUDIT.md` (widget findings appear there with the
same evidence and status fields). Fix commit on this branch: `08200a05`. Nothing was pushed.*

**Reading guide.** The sections up to "Known remaining gaps" audit the **original draft**
(`820afb20`) and keep their line references to that code. Everything from
"Status after the widget migration" onwards records what was built afterwards: the draft's
approach was validated, then rewritten onto the DataAPI v2 contract and generalized to all six
plotting widgets. The bec-side counterpart is `bec_data_api/DATA_API_AUDIT.md` §4.

This draft was assessed as an **integration probe** for the bec-side DataAPI, per its known
"rough" status. Verdict: the shape is right — a live buffered subscription feeding
`update_plot` through a Qt signal is exactly the pattern the DataAPI should serve — but the
draft had one blocking defect that came from the library (mid-scan `add_device`
misalignment froze the plot; fixed on the bec side, commit `d89e9ae9` there) and several
integration defects of its own, four of which are fixed here.

## What was wrong, and what changed in `08200a05`

1. **Setup order could permanently freeze the plot (library defect, widget trigger).**
   `_setup_data_api_subscription` adds x, y, z one by one after `set_callback`; on a scan with
   N recorded points the old library emitted N x-only bundles and then permanently paired
   x point N+k with y/z point k, so the widget's length check skipped every update for the rest
   of the scan. Proven by probe (`x (7) / y (2) / z (2), widget length check passes: False`);
   the probe passes against the fixed library (all series length 7, zero misaligned pairs).
   No widget change needed — but note the new library semantic: adding a device to an active
   bundle re-emits the aligned history, and buffered mode restarts its accumulation.

2. **Legacy fallback was gated on subscription existence, not health.** A live rebind can
   fail per device (e.g. z neither monitored nor async in the new scan — the ValueError is
   swallowed inside the scan-status dispatch); x/y stayed subscribed, z stayed dead, and both
   the DataAPI path (z=None → skip) and the legacy path (disabled because `_data_subscription
   is not None`) produced nothing: a permanently blank heatmap. Fixed with
   `DataSubscription.unbound_devices` (bec commit `f6cd80fa`) + `_data_api_feed_healthy()`:
   the legacy path stays active whenever any device is unbound.
   Test: `test_heatmap_unhealthy_subscription_keeps_legacy_updates`.

3. **A failed setup leaked a half-configured live subscription.** `self._data_subscription`
   was assigned only after all `add_device` calls, so the `except` branch's cleanup closed
   nothing; the orphan (strongly holding `data_api_update.emit`) would rebind on every scan and
   emit forever. Fixed by assigning immediately after `create_subscription`.
   Test: `test_heatmap_failed_subscription_setup_closes_partial_subscription`.

4. **No rate limit on the DataAPI feed.** The legacy path is throttled by a 5 Hz
   `pg.SignalProxy`, but `data_api_update` was connected straight to `update_plot`: one full
   O(N) buffer walk + grid rebuild per point on the GUI thread (measured library-side: 60.4 s
   of buffer-walking alone for a 36000-point scan). Fixed by routing the feed through its own
   5 Hz SignalProxy delivering only the newest payload — lossless, because buffered payloads
   carry the full state.

5. **Stale payloads could redraw over new content.** The buffered branch ignored the payload's
   `scan_id` (and shadowed its `metadata` parameter), so an emission queued on the Qt event
   loop before a scan switch or a history-view entry redrew over the new scan/history. Fixed:
   buffered payloads are dropped when the subscription is gone, a history view is active, or
   `metadata["scan_id"]` mismatches; the shadowing local was renamed.
   Test: `test_heatmap_update_plot_drops_stale_data_api_payload`.

## Known remaining gaps (as of the draft; all closed since — see the next section)

These were consequences of DataAPI scope, recorded in the library audit's recommendations:

- **The legacy fetch machinery must stay** until the DataAPI covers history scans and
  device-readback fallbacks; property-change refreshes (`sync_signal_update`) still perform the
  full legacy fetch even while the feed is active, and both writers share `_grid_index`.
- **Array-valued async z fragments** pass the length check but crash the scalar grid assignment
  (`ValueError: setting an array element with a sequence`, swallowed by SafeSlot) — the buffered
  contract needs an explicit "scalar per aligned point" guarantee or a defined flattening.
- **End-of-scan settle updates are a no-op** on both paths: the `QTimer.singleShot(...,
  self.update_plot)` fallback is skipped by `@SafeSlot(verify_sender=True)` (sender is None),
  and the DataAPI path has no scan-end reconciliation. Pre-existing on main; call it with
  `_override_slot_params={"verify_sender": False}` and add an end-of-scan handler when the
  DataAPI grows a scan-closed notification.
- `_setup_data_api_subscription` is only reached via `plot()`; a widget restored from config
  without a `plot()` call never uses the DataAPI.
- The widget tests still fake the DataAPI; one integration-style test driving a real
  `BECLiveDataPlugin` emission into `update_plot` would tie the payload shapes together
  (the library-side alignment tests currently cover that contract).

## Status after the widget migration (2026-07-29)

The gaps above were the reason this draft could not be shipped as-is. All of them were closed by
the v2 redesign plus the widget migration; the draft's own code no longer exists.

| Gap from the section above | Resolution |
| --- | --- |
| Legacy fetch machinery must stay (no history/readback coverage) | `HistoryDataPlugin` and `DeviceStreamPlugin` (bec `a8448b05`, `63b87bf3`) cover terminal scans and scan-less device streams, so the heatmap port (`e9fe0518`) drives **live and history through the same `_on_data_update`**. At the time of the migration the legacy pull survived as an explicitly health-gated fallback (`_data_api_feed_healthy`); it was **removed entirely afterwards** together with the last legacy data paths of all plot widgets — feed health is surfaced through `bridge.healthy`, and there is deliberately no second data-access path. |
| Array-valued async z fragments crash grid rendering | The columnar contract makes the shape explicit per source (`SourceData.values` + `metadata["async_update_type"]`), and `update.aligned()` guarantees equal-length columns, so the widget no longer infers structure from a buffered list. |
| End-of-scan settle updates are a no-op | Deleted along with the `QTimer.singleShot` hacks in every port. The backend performs a final flush at scan end and re-routes the same live subscription to the authoritative file when the scan-history entry appears (`a8448b05`), which is the real end-of-scan reconciliation the hack was approximating. |
| `_setup_data_api_subscription` only reachable via `plot()` | Closed afterwards: a widget restored from a saved configuration now starts the data feed itself (`_start_data_feed`), without requiring a `plot()` call; while idle it binds to the latest finished scan and switches to live-follow when a scan starts. |
| Widget tests fake the DataAPI; payload shapes untied | Partly closed: the bec side now has real-connector tests (`TestDeviceStreamsThroughRealConnector`) and real-message history fixtures. Widget suites still fake the bridge deliberately (they test rendering, not transport). The real-HDF5 gap is closed: the widget history fixtures write genuine HDF5 files (`create_history_file`, h5py) and the heatmap/waveform history tests read them through the history plugin end to end. |

### What the widgets look like now

All six plotting widgets — Heatmap (`e9fe0518`), ScatterWaveform (`47851dab`), Waveform
(`e0abc7f3`), Image (`235d5614`), MultiWaveform and MotorMap (`2288aa95`) — consume
`bec_widgets/utils/qt_data_subscription.py`:

```python
self._data_bridge = QtDataSubscription(
    self.client, sources=[(dev, entry), ...], scan="live",  # or a scan_id, or None for streams
    parent=self, min_emit_interval=self.update_interval_s,  # driven by the update_rate property
)
self._data_bridge.updated.connect(self._on_data_update)   # SubscriptionUpdate on the Qt thread
```

Deleted across those ports: three verbatim copies of the live/history fetch fork
(`_fetch_scan_data_and_access`), four scan-lifecycle handlers with their
`QTimer.singleShot(100/300)` settle hacks, two hand-rolled async reconstructors
(`on_async_readback`, `adjust_image_buffer`), three history resolvers' data paths, the per-widget
`pg.SignalProxy` **data** throttles (rate limiting is backend-side; presentation proxies stay),
and every direct dispatcher registration for `device_async_signal` / `device_preview` /
`device_monitor_1d` / `device_readback`.

Two things the migration got wrong and had to correct — both worth knowing before porting a
seventh widget:

- **Removing functionality is not the same as deferring it.** The Waveform port deleted the
  large-dataset guard and recorded it as a follow-up; it is critical functionality. It is back
  (bec `af11c666` + widgets `f57949ae`) with the original names, dialog and RPC surface, now
  gated backend-side and loading off-thread.
- **A fake bridge does not prove the transport works.** Three live-only failures (queued Qt
  delivery, pydantic `_StoredDataInfo`, pubsub `MessageObject` payloads) all passed the widget
  suites. See DATA_API_AUDIT.md §4.2.

## What a correct integration looks like (for the next widget)

Create one `QtDataSubscription` per widget configuration, declaring **all** sources at once
(the backend partitions them into correlation groups, so mixing monitored, async and standalone
sources in one call is fine); render from `update.aligned()` and `update.axis(...)` rather than
re-deriving lengths or x data; use `scan="live"` for the running scan, a scan id for history and
`scan=None` for device streams (with `max_points`); gate any remaining fallback on
`bridge.healthy`; and close the bridge in `cleanup()`. The signal bridge, Qt-thread marshalling,
stale-scan filtering, rate limiting and the size gate are all in the wrapper and the backend —
none of it should be re-implemented per widget.

## Post-migration addendum (2026-08-13)

Landed after the sections above were written; recorded here so this document matches the code:

- **Legacy sweep**: the health-gated legacy fallbacks were removed from all six widgets — the
  Data API is the only data path (see the corrected rows above).
- **`update_rate` on `PlotBase`** (1-100 Hz, per-widget defaults, RPC/Designer-visible): wired
  into every bridge through the backend's runtime-adjustable `min_emit_interval`.
- **Incremental async rendering** matching main's update rates, with a throughput benchmark
  (`tests/unit_tests/benchmarks/test_data_api_widget_throughput.py`).
- **Waveform large datasets**: min/max envelope decimation above one million points with
  zoom-window re-rendering down to raw samples, and a labelled progress bar below the plot fed
  by the backend's chunked-read `progress_callback` via `bridge.progress`.
- **Columns may be numpy arrays** (history reads); the widgets' source checks are
  length-based, never truthiness-based — regression-tested with numpy-backed fixtures.
