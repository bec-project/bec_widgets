# Tour guide

Short, task-focused tours for the BEC main app, with the entry points that make people find them.
It replaces nothing: `bec_widgets/utils/guided_tour.py` (the classic tour) is unchanged and stays
in the Help menu as "Classic Guided Tour".

Turn it on with an environment variable:

```bash
BEC_TOUR_UI=qwidget bec-app   # QWidget overlay (ux_kit controls)
BEC_TOUR_UI=qml bec-app       # QML overlay (BecUi controls), same look
```

## What the user gets

| Entry point | Where | Behaviour |
| --- | --- | --- |
| Welcome card | bottom left, pointing at the Help item, on first start | Lists the tours; "Show me around", "Later" (asks again next start), "Don't show again". Does not block the app. |
| Help item | sidebar, above the theme toggle | Opens the tour list. |
| Tour list | F1, Help › Tours…, Help item | Every tour with its length, status (New, Step 3 of 5, Done), Start, Resume or Replay, overall progress, "What's this?". |
| What's this? | Shift+F1, Help menu, tour list | Outlines every documented control on screen; click one to read about it and jump into its tour. |
| View hint | the first time a view with a tour is opened | Small card "New here? Load and check a device config", Start or Not now. Shown once per tour. |
| Command palette | `TourGuide.palette_commands()` | "Show tours", "What's this?", one "Tour: …" or "Resume: …" per tour; also picked up from the Help menu. |
| Welcome screen | `TourGuide.welcome_items()` | Tours as cards with status, progress and a start callback. |

During a tour the highlighted control stays clickable ("Try it"), the card shows segmented
progress, Back/Next, and closing keeps the position for later. Steps whose control is not on
screen are dropped and the count is corrected. A completion card suggests the next tour.

Progress lives in `QSettings("bec", "bec_widgets")` under `tour_guide/`.

## Writing a tour

```python
from bec_widgets.utils.tour_guide import Tour, TourStep

Tour(
    id="workspace",
    title="Build a workspace",                  # a task, not a widget name
    summary="Add plots and device controls, then save the layout as a profile.",
    icon="dashboard_customize",
    view="Docks",                               # offer it when this view is first opened
    steps=[
        TourStep(
            title="Add a plot",
            text="Waveforms, images, heatmaps and more. Each one opens as a dock.",
            target=lambda: toolbar.components.get_action("menu_plots"),
            view="Docks",                       # the guide switches views for you
            hint="Open the menu and pick Waveform.",
        ),
    ],
)
```

* Keep tours to three to six steps; one tour per task.
* `target` is a widget, a `QAction`, a `QRect`, a toolbar action or a callable returning one. Make
  callables side-effect free: "What's this?" resolves them too. Use `view` instead of switching
  views inside the callable.
* `available=lambda: ...` leaves a step out entirely (e.g. experimental features).
* Built-in tours are in `bec_widgets/applications/app_tours.py`; a view can add its own by
  implementing `guide_tours(main_app) -> list[Tour]`.
* `TourGuide.register_help(widget, title, text)` documents a control for "What's this?" without a
  tour.

## Structure

| File | Role |
| --- | --- |
| `model.py` | `Tour`, `TourStep`, `TourProgress` (QSettings) |
| `guide.py` | `TourGuide`: modes, navigation, progress, hooks, keyboard (Esc, Enter, arrows) |
| `geometry.py` | target rectangles, card placement, click-through region; shared by both overlays |
| `overlay_qwidget.py` | QWidget overlay built from `ux_kit` |
| `overlay_qml.py`, `qml/TourOverlay.qml` | QML overlay built from `BecUi` |

The guide hands the overlay a plain state (`TourGuide.state()`), the overlay draws it and emits
`triggered(action, arg)`. Both overlays use `geometry.place_card` and `geometry.interaction_region`,
so they place cards and let clicks through identically.
