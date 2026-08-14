# Repository Guidelines — `bec_widgets`

**BEC Widgets** is a modular **PySide6 / Qt6** toolkit for
[BEC (Beamline Experiment Control)](https://github.com/bec-project/bec). It provides dockable, composable
GUI components that move devices, run scans, and stream live or on-disk data. Widgets stay in sync with a
running BEC deployment through Redis, are scriptable over an RPC layer, and are extensible through a
plugin system so beamlines can add their own widgets without forking this repository.

This file is a quick-reference for AI coding agents (and new contributors). User-facing documentation
lives at <https://bec.readthedocs.io>, authored in the separate
[`bec-project/bec_docs`](https://github.com/bec-project/bec_docs) repository.

## Project Structure & Module Organization

`bec_widgets/` is the importable package:

| Path | What goes there |
| --- | --- |
| `bec_widgets/widgets/` | Reusable Qt widgets, grouped by domain: `plots/`, `control/`, `containers/`, `services/`, `utility/`, `dap/`, `editors/`, `progress/`. This is where most contributions land. |
| `bec_widgets/applications/` | Assembled, launchable applications — `main_app.py` (`bec-app`), `companion_app.py` (`bec-gui-server`), and the launch window. |
| `bec_widgets/utils/` | Shared plumbing: `bec_widget.py`, `bec_connector.py`, `bec_dispatcher.py`, `error_popups.py` (`SafeSlot`), `colors.py`, `generate_cli.py`, the plugin helpers, and Designer glue. |
| `bec_widgets/cli/` | RPC client layer and Designer plugin registry. **`cli/client.py` is generated — see below.** |
| `bec_widgets/assets/` | Packaged icons, `.ui` files, and templates. |
| `bec_widgets/examples/` | Small runnable examples. |
| `bec_widgets/tests/` | Test helpers shipped *with* the package (`FakeDevice`, `FakePositioner`, `DMMock`) so downstream plugin repos can reuse them. |
| `tests/unit_tests/` | The main test suite; mirrors the package layout. |
| `tests/end-2-end/` | Tests against a real BEC deployment. |
| `tests/reference_failures/` | Output directory for failed image comparisons; uploaded as a CI artifact. |

Console scripts declared in `pyproject.toml`:

- `bec-app` — the main dockable application.
- `bec-gui-server` — companion GUI server driven by the BEC IPython client.
- `bec-designer` — Qt Designer with the BEC widget plugins loaded.
- `bw-generate-cli` — regenerates the RPC client and Designer plugin stubs.

## Local Environment Overlay

If a file named **`AGENTS_PERSONAL.md`** exists next to this one, read it and treat it as an extension
of this file. It carries machine-specific setup — interpreter and environment manager, local paths,
private workflow conventions — and **its instructions take precedence over the generic
"Development Environment" section below**. Everything else in this file still applies.

That file is intentionally untracked and personal to one developer's machine. Do not commit it, do not
reference it from committed files, and do not assume it exists — if it is absent, follow this file as
written.

## Development Environment

Requires **Python 3.11+** (CI tests 3.11, 3.12, 3.13). Qt6 comes in via the pinned `PySide6` dependency —
do not install PySide6 separately.

```bash
python -m venv .venv
source .venv/bin/activate          # macOS/Linux only; see "Platform Notes"
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Verify the environment resolves to this checkout rather than a released wheel:

```bash
python -c "import bec_widgets; print(bec_widgets.__file__)"
```

If you work in a git worktree or a second clone, re-run the editable install from that directory. A
virtualenv holds exactly one editable install per package, so give each checkout its own virtualenv
instead of sharing one — otherwise one checkout silently shadows the other.

**Running against a live BEC** additionally needs BEC services and Redis (see the `bec` repository).
Widgets can be developed and unit-tested without them; the test suite mocks the BEC client.

**Headless / remote sessions** need an offscreen Qt platform. CI sets:

```bash
export QT_QPA_PLATFORM=offscreen
export QTWEBENGINE_DISABLE_SANDBOX=1
export QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu
```

On Linux you may also need system Qt libraries (`libgl1`, `libegl1`, `libxkbcommon-x11-0`, `libdbus-1-3`,
`libnss3`, `xvfb`). `pytest-xvfb` is a dev dependency and handles the virtual display automatically when
`xvfb` is installed.

## Generated Code — Do Not Hand-Edit

`bec_widgets/cli/client.py`, the Qt Designer plugin files, and the `cli/designer_plugins.py` registry
are **generated**:

```bash
bw-generate-cli --target bec_widgets
```

Regenerate whenever the RPC surface or the set of Designer plugins changes — that is, when you

- **add a widget that is reachable over RPC** (any widget declaring `USER_ACCESS`) or that is exposed as
  a **Qt Designer plugin**,
- **change an existing widget's RPC API** — the entries in `USER_ACCESS`, or the signature of a method
  or property exposed through it,
- rename or remove such a widget.

CI runs the same command and then `git diff --exit-code`, so a stale `client.py` fails the build.

For a **beamline plugin repository**, `--target` is that repository's own importable package name, and
the package has to be installed in the environment — the tool imports `<plugin_repo>.bec_widgets` and
writes the client to `<plugin_repo>/bec_widgets/widgets/client.py`:

```bash
bw-generate-cli --target my_plugin_repo
```

## The BEC Widget Pattern

Every BEC widget follows the same shape:

1. Inherit from **`BECWidget`** and mix in the Qt class (`QWidget`, `QLabel`, …). `BECWidget` must come first.
2. Declare **`USER_ACCESS`** — the list of method names exposed over RPC and to the CLI.
3. Subscribe to BEC data through **`BECDispatcher`** and `MessageEndpoints`.
4. Decorate slots with **`@SafeSlot`** so exceptions surface as user-visible errors instead of killing
   the Qt event loop.
5. Reach BEC objects through **`self.get_bec_shortcuts()`**, which populates `self.dev`, `self.scans`,
   `self.queue`, and friends.

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
        ...  # update the UI from the readback

    @SafeSlot(float)
    def move(self, position: float):
        self.dev[self.motor_name].move(position)
```

**Clean up after yourself.** Widgets live inside a long-running application. Disconnect dispatcher
subscriptions and stop timers in `cleanup()`; a leaked subscription keeps the widget alive and keeps
firing after the dock is closed.

**Do not block the Qt event loop.** Anything slow — file I/O, RPC round-trips, large array work — belongs
off the GUI thread, and results must come back through a signal, not by touching widgets directly.

### Plugins

Beamline-specific widgets live in separate plugin repositories and are discovered through the
`bec.widgets.user_widgets` entry-point group (see `bec_widgets/utils/bec_plugin_helper.py`). Widgets that
only make sense at one beamline belong in that beamline's plugin repository, not here.

## Testing

```bash
python -m pytest --random-order tests/unit_tests/
```

`--random-order` matches CI and is how order-dependent test pollution gets caught — a test that only
passes in file order is a broken test.

Coverage, as CI measures it — the plain `coverage` CLI:

```bash
coverage run --branch --source=./bec_widgets -m pytest --random-order \
    --ignore=tests/unit_tests/benchmarks tests/unit_tests/
coverage report
```

End-to-end tests need BEC services and GUI dependencies available:

```bash
python -m pytest -v --files-path ./ --start-servers tests/end-2-end/
```

**Conventions:**

- Name files `test_<feature>.py`; name tests after behaviour — `test_widget_updates_on_readback()`, not
  `test_widget_2()`.
- Create widgets with the `create_widget(qtbot, WidgetClass, ...)` helper from
  `tests/unit_tests/conftest.py`. It registers the widget with `qtbot` and waits for exposure, so
  teardown stays consistent. Never instantiate a widget in a test without handing it to `qtbot` — leaked
  widgets cause failures in *other* tests.
- Mock BEC, Redis, and hardware. Reuse `FakeDevice`, `FakePositioner`, and `DMMock` from
  `bec_widgets/tests/utils.py` and the autouse fixtures in `tests/unit_tests/conftest.py` (mock client,
  dispatcher, RPC register, message-box suppression) rather than rolling your own.
- Update reference images only when a visual change is intentional, and say so in the pull request.
- Benchmarks live in `tests/unit_tests/benchmarks/` and are excluded from coverage runs.

## Coding Style & Naming Conventions

- Python 3.11+, 4-space indentation, **100-character** line limit.
- **Black** and **isort** are the source of truth (settings in `pyproject.toml`). CI fails on any diff:

  ```bash
  black --line-length=100 --skip-magic-trailing-comma .
  isort --line-length=100 --profile=black --multi-line=3 --trailing-comma .
  ```

- **Import from `qtpy`, not `PySide6`.** CI explicitly greps for `from PySide6.` and fails the build;
  only `PySide6.QtDesigner` and `PySide6.scripts` are exempt.

  ```python
  from qtpy.QtWidgets import QWidget    # yes
  from PySide6.QtWidgets import QWidget # no — CI rejects this
  ```

- **Pylint** runs in CI and reports a score; do not introduce new warnings.
- `snake_case` for modules, functions, test files, and most widget directories; `PascalCase` for widget
  and Qt class names. Follow existing file patterns — `*_plugin.py` for Designer plugins, `register_*.py`
  for registration helpers.
- Use f-strings; use `pathlib` and forward slashes for resource paths.
- Type-annotate new public methods and give public widgets and methods docstrings — they feed both the
  generated CLI and the API reference.

## Platform Notes

Code must run on **macOS and Linux**. Windows is not supported or tested. Use `pathlib`, never
backslash paths or drive letters.

## Related Repositories

- [`bec`](https://github.com/bec-project/bec) — core library and services; source of `bec_lib`,
  `MessageEndpoints`, and the client.
- [`ophyd_devices`](https://github.com/bec-project/ophyd_devices) — hardware abstraction layer.
- [`bec_qthemes`](https://github.com/bec-project/bec_qthemes) — theming and Material icons used here.
- [`bec_docs`](https://github.com/bec-project/bec_docs) — the published documentation site.

CI installs `bec` and `ophyd_devices` from source, so a breaking change upstream shows up here first.
When a widget change depends on an unreleased `bec_lib` feature, say so in the pull request.

## Commit & Pull Request Guidelines

- **Do not commit or push unless explicitly asked to.** Leave the working tree for the human to review.
- **Never open, update, or merge a pull request.** Submitting the change is the human contributor's
  step. An agent's work ends at a reviewed working tree — or at a local commit on a branch, when a
  commit was explicitly requested.
- Branch from `main` with a descriptive name such as `feat/heatmap-roi` or `fix/waveform-autorange`.
- **Conventional Commits are mandatory** — `<type>(<scope>): <summary>`, e.g.
  `feat(plots): add ROI export to waveform`. Allowed types: `build`, `chore`, `ci`, `docs`, `feat`,
  `fix`, `perf`, `refactor`, `style`, `test`. `feat` triggers a minor release, `fix` and `perf` a patch
  release; breaking changes need `!` or a `BREAKING CHANGE:` footer.
- Commit messages are parsed by python-semantic-release and become the published `CHANGELOG.md`. Keep
  them to a single clean subject line.
- The pull request itself needs a clear description, test evidence, and confirmation that
  `bw-generate-cli --target bec_widgets` produced no diff. Produce that evidence and leave it for
  whoever opens the PR.
- Capture a **screenshot or short GIF for any visible GUI change** — reviewers cannot evaluate a layout
  change from a diff.
