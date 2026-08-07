# GPU acceleration for BEC Widgets plots (pyqtgraph 0.14)

Branch `pg-gpu`, worktree `bec_widgets_pg-gpu`, env `bec_312_pg-gpu`.

## Summary

**The migration is already done.** `pyproject.toml` pins `pyqtgraph==0.14.0` and that is what
`bec_312` has installed. There is no 0.13 → 0.14 port to carry out.

**Enabling GPU acceleration is small** — one viewport swap at a single choke point — but it is
*not* free, and it does not help the widgets people usually assume it will.

| | |
|---|---|
| Migration effort | none (already on 0.14.0) |
| Enablement effort | ~1 day incl. the screenshot fix and tests |
| Widgets that benefit | `Waveform`, `MultiWaveform` |
| Widgets that gain nothing | `Image`, `Heatmap`, `ScatterWaveform`, `MotorMap` |
| Main hazard | screenshots come back blank; software GL on remote consoles |

## What pyqtgraph 0.14 actually accelerates

0.14 rewrote the OpenGL path as a self-contained shader program (no PyOpenGL needed) and dropped
the `enableExperimental` gate. It applies to exactly two items:

- `PlotCurveItem` — `paintGL` at `graphicsItems/PlotCurveItem.py:1013`
- `PColorMeshItem` — `paintGL` at `graphicsItems/PColorMeshItem.py:469`

Everything else — `ImageItem`, `ScatterPlotItem`, `TextItem`, `InfiniteLine`, the ROIs, the axes —
has no `paintGL` and still goes through `QPainter`. There is no GPU path for image display in the
`QGraphicsView` stack at all.

This matters because `ImageItem` is by far the most-used pyqtgraph item in this repo (27 call
sites vs. 9 for `PlotDataItem`). **The Image and Heatmap widgets get no benefit from this work.**

## Measured

Apple M1 Pro, PySide6 6.11.1, `swapInterval=0`, data pre-generated so only render cost is timed
(`gpu_bench.py`, 5 curves):

| points/curve | raster | opengl | speedup |
|---:|---:|---:|---:|
| 1,000 | 170.1 fps | 319.1 fps | 1.9× |
| 5,000 | 74.3 fps | 292.3 fps | 3.9× |
| 20,000 | 29.5 fps | 248.1 fps | 8.4× |
| 100,000 | 6.7 fps | 155.5 fps | 23.2× |
| 500,000 | 1.4 fps | 51.4 fps | 36.5× |

Raster cost scales with sample count; the OpenGL path stays roughly flat. Note the practical
threshold, though: with vsync on, a real app is capped at the display refresh anyway, so below
~5–10k points per curve both paths are already "fast enough" and the win is invisible. The change
pays off for long line scans and for `MultiWaveform`.

For comparison, a 2048×2048 `ImageItem` measured 39.0 fps raster vs. 42.6 fps OpenGL — 1.09×,
i.e. noise. That is the expected result given there is no GL path for images.

## Symbols dominate everything above (fixed)

Profiling the Waveform update path turned up a cost far larger than anything the viewport choice
buys. Curves default to `symbol="o"`, and pyqtgraph draws symbols through `ScatterPlotItem`, whose
`SymbolAtlas._keys` builds a style tuple **per point in Python** — 2 `getId` calls per point, linear
in sample count.

At 50,000 points, `curve.setData()` measured **92.1 ms with a symbol and 0.49 ms without**; the full
`_on_data_update()` went from 108.7 ms to 7.2 ms. The scaling makes the mechanism plain — the symbol
cost is per point, the rest is flat:

| points | symbols on | symbols off |
|---:|---:|---:|
| 1,000 | 1.16 ms | 0.05 ms |
| 10,000 | 18.36 ms | 0.06 ms |
| 50,000 | 89.56 ms | 0.09 ms |

`Curve.setData` now hides the symbol above `CurveConfig.symbol_point_limit` (default 1000) and
restores it when the data shrinks. The suppression is a display-level `setSymbol(None)`; `config.symbol`
keeps the user's choice, so a custom symbol comes back rather than being reset to `"o"`. Setting
`symbol_point_limit = None` opts out.

This lives in `Curve.setData` rather than in the Waveform update slots so every data path is covered
— sync, async, history, DAP, and the `data_api` branch's `_render_*` helpers. `_auto_adjust_async_curve_settings`
previously did this for async curves only, and reset the symbol to a hardcoded `"o"`; its symbol
handling was removed in favour of the shared path (it still manages pen width and downsampling).

Note this was never a `data_api` regression: the default is identical on `main`. Pen width is left
alone — thick pens are also costly, but width 1 is a visual regression nobody asked for.

## The two real hazards

### 1. Screenshots come back blank (fixed here)

`BECWidget` captures via `self.grab()` in three places — `screenshot`, `screenshot_bytes` and
`screenshot_to_scilog`. `QWidget.grab()` renders the widget tree through `QPainter` and never
reaches a `QOpenGLWidget`, so the plot area is empty. Measured directly: 6.5% non-background
pixels on the raster viewport, **0.0%** on the OpenGL viewport.

Left unfixed this silently uploads blank plots to SciLog.

`QOpenGLWidget.grabFramebuffer()` is not a usable substitute — it also returned an empty image on
macOS, before and after a forced `repaint()`, because the framebuffer is not retained after
compositing. Swapping the viewport back to raster for the duration of the grab is worse: pyqtgraph
parents its `OpenGLState` to the GL viewport widget (`PlotCurveItem.py:49`), so destroying that
widget leaves `PlotCurveItem.glstate` dangling.

The fix in `bec_widgets/utils/gpu_acceleration.py` re-renders the affected `GraphicsView`'s
*scene* through `QPainter` into the grabbed pixmap. No OpenGL state is touched and the output
matches the raster path. One subtlety: `GraphicsView.render` forwards to `QGraphicsView.render`,
not `QWidget.render`, so it stretches the scene across the whole painter unless an explicit target
and source rect are passed — without that the capture comes out zoomed.

### 2. Software OpenGL on remote consoles

The `renderer` string decides this. An X-forwarded or VNC session typically lands on Mesa
`llvmpipe`, where the OpenGL path is *slower* than raster. Given how BEC GUIs are deployed on
beamline nodes this is the common case, not the exotic one, so acceleration is gated on the
renderer not being software.

## What was implemented

- **`bec_widgets/utils/gpu_acceleration.py`** (new) — caches an offscreen-context probe of the GL
  renderer, refuses software rasterisers, honours `BEC_WIDGETS_OPENGL=auto|1|0`, and provides
  `grab_widget()` for OpenGL-safe screenshots.
- **`plot_base.py`** — `use_opengl` `SafeProperty(bool)`, default `True` via `PlotBase.USE_OPENGL`,
  switchable at runtime and exposed over RPC. The viewport is swapped after construction because
  `GraphicsLayoutWidget.__init__` forwards no viewport argument to `GraphicsView`.
- **`bec_widget.py`** — the three `self.grab()` screenshot sites now call `grab_widget(self)`.
- **`tests/unit_tests/`** — 13 tests in `test_gpu_acceleration.py` plus 3 in
  `test_plot_base_next_gen.py`, covering the renderer gate, the env var, non-blank captures over an
  OpenGL viewport, and the runtime toggle.

Set per widget rather than via a global `pg.setConfigOption("useOpenGL", True)`, so a single plot can
be dropped back to raster without disturbing the rest of the application.

## Runtime switching

The viewport *can* be swapped after construction, but not naively. pyqtgraph parents each item's
`OpenGLState` to the **viewport widget**, so `useOpenGL()` deletes it on the C++ side while the item
keeps a stale Python reference. The next `paintGL` then raises
`RuntimeError: Signal source has been deleted` — and because `PlotCurveItem.paint` is wrapped in
`@debug.warnOnException`, the exception is swallowed: **the curve silently stops rendering instead of
crashing.**

Measured over 4 toggle cycles: **29 swallowed GL paint exceptions** without a reset, **0** when the
stale state is released first. `set_view_opengl()` therefore disconnects `sigPlotChanged` and clears
`glstate` on every affected item before swapping, so the item rebuilds against the new context.

`use_opengl` reflects the *live* viewport rather than the requested value — setting it `True` on a
software renderer leaves it `False`.

## Test status

Full unit suite on this machine: **2051 passed, 3 skipped, 1 failed, 7 errors** (9m29s). None of
the failures are attributable to this change:

- `test_client_utils.py::test_check_gui_display_available_reports_missing_display_for_ssh_session`
  — pre-existing, macOS-only. `client_utils.py:72` returns `True, None` unconditionally when
  `sys.platform == "darwin"`, so the assertion can only hold on Linux.
- 7 × `test_plugin_creator.py::TestAddWidgetVariants` — environmental. The copier template task
  runs `pyside6-uic`, which exits 127 (not found) in the cloned `bec_312_pg-gpu` env.

Targeted runs after adding the property: 16/16 new tests, 183 passed across
waveform/multi-waveform/plot_base/lifecycle/scatter, and 402 passed in a
plot/image/heatmap/crosshair/roi/export/rpc/client sweep (same single pre-existing failure). An
`AttributeError` traceback logged during `test_waveform.py` is also pre-existing — it appears with
`BEC_WIDGETS_OPENGL=0` too.

`bw-generate-cli --target bec_widgets` was re-run; the only change to the generated
`bec_widgets/cli/client.py` is the new `use_opengl` accessor on the plot classes.

## Not addressed

- **Antialiasing/appearance differences.** The GL path renders lines through its own shader;
  hairlines and `antialias=True` will not be pixel-identical to raster. No reference-image tests
  cover the plot canvas, so nothing failed, but it is worth an eyeball before deploying.
- **`ScatterWaveform` / `MotorMap`.** Left on raster. Their `ScatterPlotItem` has no GL path, so
  accelerating them needs upstream work.
- **The `useOpenGL` viewport is still flagged experimental by Qt** for `QGraphicsView`. That is
  Qt's wording, not a specific known bug.
- **Not verified on Linux/NVIDIA or on a real beamline console** — only on Apple M1 Pro. The
  software-renderer gate is unit-tested with a faked renderer string, not against real llvmpipe.

## Try it

```bash
conda activate bec_312_pg-gpu && cd /Users/janwyzula/PSI/bec_widgets_pg-gpu && python gpu_bench.py 100000 5
```

`gpu_risks.py` prints the grab-blankness comparison and the renderer identity for the current
session.
