# Repository Guidelines — `bec_widgets`

`bec_widgets` is the core BEC Qt widget toolkit. Prefer focused changes, follow existing local widget
patterns, verify the smallest relevant test scope, and keep generated code plus downstream plugin
compatibility in mind.

This file is an agent-oriented operating manual. User-facing documentation lives at
<https://bec.readthedocs.io> and is authored in the separate
[`bec-project/bec_docs`](https://github.com/bec-project/bec_docs) repository.

## Core Rules

- Import Qt modules from `qtpy`, not `PySide6` — CI greps for `from PySide6.` and fails the build;
  only `PySide6.QtDesigner` and `PySide6.scripts` are exempt.
- Do not hand-edit generated RPC or Designer files; regenerate them with `bw-generate-cli`.
- If a widget exposes `USER_ACCESS` or is available in Qt Designer, treat its generated CLI and plugin
  stubs as part of the change.
- Inherit `BECWidget` first, then the Qt base class.
- Use `MessageEndpoints`, `BECDispatcher`, `SafeSlot`, and existing local widget patterns before
  introducing a new abstraction.
- Do not block the Qt event loop with slow I/O, RPC, or heavy computation. Run slow work off the GUI
  thread and deliver results back through signals — never touch widgets from another thread.
- Clean up dispatcher subscriptions, timers, and long-lived resources in `cleanup()`.
- Beamline-specific widgets usually belong in a plugin repository, not core `bec_widgets`.
- Keep diffs focused. Avoid unrelated refactors while fixing a specific issue.
- Add regression tests for bug fixes.
- Do not commit, push, or open PRs unless explicitly asked.

## First Read

Start here when orienting yourself:

- `bec_widgets/utils/bec_widget.py` — base widget behavior and shortcuts
- `bec_widgets/utils/bec_dispatcher.py` — widget-side subscription wiring
- `bec_widgets/utils/error_popups.py` — `SafeSlot` and user-visible exception handling
- `bec_widgets/utils/generate_cli.py` — generated RPC and Designer code entry point
- `bec_widgets/utils/bec_plugin_helper.py` — plugin discovery and entry points
- `tests/unit_tests/conftest.py` — shared widget fixtures and `create_widget(...)`
- `pyproject.toml` — scripts, tooling, and dependency source of truth

## Repo Layout

Main package and test areas:

- `bec_widgets/widgets/` — reusable Qt widgets grouped by domain
- `bec_widgets/applications/` — assembled applications such as `bec-app` and `bec-gui-server`
- `bec_widgets/utils/` — shared plumbing, widget base classes, CLI generation, and plugin helpers
- `bec_widgets/cli/` — RPC client layer and Designer plugin registry; generated files live here
- `bec_widgets/assets/` — packaged icons, `.ui` files, and templates
- `bec_widgets/examples/` — small runnable examples
- `bec_widgets/tests/` — packaged test helpers for downstream plugin repos
- `tests/unit_tests/` — main test suite
- `tests/end-2-end/` — tests against a real BEC deployment
- `tests/reference_failures/` — failed image-comparison output collected in CI

Console scripts declared in `pyproject.toml`:

- `bec-app` — main dockable application
- `bec-gui-server` — companion GUI server driven by the BEC IPython client
- `bec-designer` — Qt Designer with BEC widget plugins loaded
- `bw-generate-cli` — regenerates RPC client and Designer plugin stubs

Treat `pyproject.toml` as the source of truth for dependencies, scripts, Black, isort, and pylint
behavior.

## Local Overlay

If `AGENTS_PERSONAL.md` exists beside this file, treat it as an extension of this file.
Machine-specific environment and workflow instructions in `AGENTS_PERSONAL.md` take precedence over
the generic guidance here.

- `AGENTS_PERSONAL.md` is untracked and local to one developer machine
- do not commit it
- do not reference it from committed files
- do not assume it exists

## Common Task Routing

If you change:

- a widget's `USER_ACCESS`, a Designer plugin, or any RPC-visible widget API: run
  `bw-generate-cli --target bec_widgets`, inspect the generated diff, and keep generated files in sync
- visible widget layout or rendering behavior: run focused widget tests and update reference images only
  when the visual change is intentional
- `bec_widgets/utils/bec_dispatcher.py`, `bec_widget.py`, or shared plumbing used by many widgets: run
  the relevant focused tests plus the broader affected package test scope before finishing
- test behavior or a flaky widget test: check `tests/unit_tests/conftest.py` and `bec_widgets/tests/`
  for reusable fixtures and helpers before adding new ones
- docs, examples, or commands only: no broad GUI or e2e run is required unless commands or runnable
  examples changed

If the requested change sounds like one of these, it probably belongs elsewhere:

- new core device or hardware behavior: `ophyd_devices`
- server or client service behavior: `bec`
- beamline-specific widget or one-off beamline workflow: that beamline's plugin repo
- published documentation changes: `bec_docs`

## Widget Architecture

Most widgets follow the same pattern:

1. Inherit from `BECWidget` and then the Qt class.
2. Declare `USER_ACCESS` for methods exposed over RPC and to the generated CLI.
3. Subscribe to BEC data through `BECDispatcher` and `MessageEndpoints`.
4. Decorate Qt slots with `@SafeSlot` so failures surface to users without killing the event loop.
5. Call `self.get_bec_shortcuts()` to populate shortcuts such as `self.dev`, `self.scans`, and
   `self.queue`.

```python
from qtpy.QtWidgets import QWidget

from bec_lib.endpoints import MessageEndpoints
from bec_widgets import BECWidget, SafeSlot


class MyMotorWidget(BECWidget, QWidget):
    USER_ACCESS = ["move"]

    def __init__(self, parent=None, motor_name: str = "samx", **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.motor_name = motor_name
        self.get_bec_shortcuts()
        self.bec_dispatcher.connect_slot(
            self.on_readback, MessageEndpoints.device_readback(motor_name)
        )

    @SafeSlot(dict, dict)
    def on_readback(self, data: dict, meta: dict):
        ...

    @SafeSlot(float)
    def move(self, position: float):
        self.dev[self.motor_name].move(position)
```

Generated files:

- `bec_widgets/cli/client.py`
- Designer plugin files
- `bec_widgets/cli/designer_plugins.py`

Do not hand-edit those files. Regenerate them:

```bash
bw-generate-cli --target bec_widgets
```

Beamline plugin widgets are discovered through the `bec.widgets.user_widgets` entry-point group. Keep
core widgets generic; move beamline-specific behavior to plugin repositories.

## Validation

Run the smallest relevant test target first. For substantial UI plumbing changes, generated-code
changes, or work that affects many widgets, run the broader affected package suite before finishing.

Unit tests are the default. CI runs them with `--random-order`, so local validation should do the same
when practical. Create widgets with `create_widget(...)` from `tests/unit_tests/conftest.py`. It
registers the widget with `qtbot` so it is closed at test end; the autouse conftest fixtures handle the
rest of the teardown (dispatcher disconnect, singleton resets) and fail the test if any top-level
widget is left open. Before adding a new fixture, check for reusable fixtures in
`tests/unit_tests/conftest.py` and helpers in `bec_widgets/tests/utils.py`.

Mock BEC, Redis, and hardware in unit tests. Reuse existing helpers such as `FakeDevice`,
`FakePositioner`, `DMMock`, and the shared autouse fixtures rather than rolling your own.

Reference test commands:

```bash
python -m pytest --random-order tests/unit_tests/
python -m pytest -v --files-path ./ --start-servers tests/end-2-end/
```

Use end-to-end tests only when service interaction, live BEC startup, GUI/server integration, or real
Redis-backed behavior is what you are changing.

Benchmarks live in `tests/unit_tests/benchmarks/` and are excluded from normal coverage runs.

## Running Locally

For widget-only unit-test work, a live BEC deployment is not required.

For interactive validation against a running BEC deployment, you usually need:

- Redis reachable by the BEC services
- BEC services started from the `bec` repository
- this repository installed editable in the current environment

Useful local entry points:

```bash
bec-app
bec-gui-server
bec-designer
```

Headless or remote sessions generally need:

```bash
export QT_QPA_PLATFORM=offscreen
export QTWEBENGINE_DISABLE_SANDBOX=1
export QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu
```

CI also relies on `pytest-xvfb` when `xvfb` is available.

## Style And Change Hygiene

- Python 3.11+, 4-space indentation, 100-character line limit
- run Black and isort on changed files or the affected package
- use `f`-strings instead of `%` formatting or `str.format()`
- use `pathlib` instead of manual path-string manipulation
- type-annotate new public methods
- public widgets, public methods, and modules should have docstrings
- avoid formatting or import-order churn in untouched files

Whole-repo formatting equivalents:

```bash
black --line-length=100 --skip-magic-trailing-comma .
isort --line-length=100 --profile=black --multi-line=3 --trailing-comma .
```

Pylint runs in CI. Do not introduce new warnings.

## Development Environment

Requires:

- Python 3.11+
- Qt6 through the pinned `PySide6` dependency
- BEC services and Redis only when validating against a live deployment or running e2e tests

Install this repository editable from the checkout you are actively using. If you switch to another
clone or git worktree, reinstall from that location so the environment does not silently point at a
different checkout.

CI currently tests Python 3.11, 3.12, and 3.13.

## Platform Notes

Code must run on macOS and Linux. Windows is unsupported and untested. Prefer portable `pathlib`
usage and do not add Windows-specific branches unless explicitly requested.

## Related Repositories

- `bec` — core library and services; source of `bec_lib`, `MessageEndpoints`, and the client
- `ophyd_devices` — hardware abstraction layer
- `bec_qthemes` — theming and Material icons used here
- `bec_docs` — published documentation

When a widget change depends on an unreleased `bec` or `ophyd_devices` change, say so explicitly.

## Commit And PR Notes

- Branch from `main` for new work
- use Conventional Commits
- breaking changes need `!` or a `BREAKING CHANGE:` footer
- leave the eventual PR author with a short summary of what changed, why, what you validated, and
  whether `bw-generate-cli --target bec_widgets` produced a diff
- capture a screenshot or short GIF for any visible GUI change
