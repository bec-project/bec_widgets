# CLAUDE.md — `bec_widgets`

@AGENTS.md

The guidelines above are imported from [`AGENTS.md`](AGENTS.md) (single source of
truth). The points that matter most in day-to-day work:

- **Check for `AGENTS_PERSONAL.md` first.** If it exists, it extends `AGENTS.md` with
  machine-specific environment setup and takes precedence over the generic venv/pip instructions there.
  It is untracked and personal — never commit it, and never assume it exists.
- **If `graphify-out/` exists, route through it before grepping** — `graphify query/path/explain/affected`
  answer "what talks to what" faster than a repo-wide search. It is optional and gitignored; if it is
  missing, just work from the code. Before trusting a downloaded map, check it against the checkout —
  not the installed package, which can lag — with the `git rev-list --count` snippet in `AGENTS.md`.
  Anything but `0` means the map is behind your working tree: say so and verify against the code
  instead of answering from the graph.
- **Import from `qtpy`, never `PySide6.*`.** CI greps for `from PySide6.` and fails the build (only
  `PySide6.QtDesigner` and `PySide6.scripts` are exempt).
- **`bec_widgets/cli/client.py` and the Designer plugin files are generated — never hand-edit them.**
  Regenerate with `bw-generate-cli --target bec_widgets` whenever a widget's RPC API changes
  (`USER_ACCESS` entries or an exposed signature) or a new widget with RPC access or a Qt Designer
  plugin is added; CI runs the same command and `git diff --exit-code`. For a beamline plugin repo,
  `--target` is that repository's importable package name (`bw-generate-cli --target my_plugin_repo`).
- **Widget pattern**: inherit `BECWidget` first, then the Qt class; declare `USER_ACCESS`; subscribe via
  `BECDispatcher` + `MessageEndpoints`; decorate slots with `@SafeSlot`; reach BEC through
  `self.get_bec_shortcuts()`. Disconnect subscriptions and stop timers in `cleanup()`, and never block
  the Qt event loop.
- **Tests**: `python -m pytest --random-order tests/unit_tests/`. Build widgets with
  `create_widget(qtbot, WidgetClass, ...)` from `tests/unit_tests/conftest.py` so `qtbot` owns teardown;
  reuse `FakeDevice`/`FakePositioner`/`DMMock` from `bec_widgets/tests/utils.py`. Headless runs need
  `QT_QPA_PLATFORM=offscreen`.
- **Format before finishing**: `black --line-length=100 --skip-magic-trailing-comma .` and
  `isort --line-length=100 --profile=black --multi-line=3 --trailing-comma .`.
- **Beamline-specific widgets belong in a plugin repo**, discovered via the `bec.widgets.user_widgets`
  entry-point group — not in this repository.
- **Do not commit or push unless explicitly asked, and never open a pull request.** If you do commit,
  write a single Conventional Commits line — it is parsed into the published changelog. Opening the PR
  is the human's step; leave them the summary, test output, and a screenshot or GIF of any visible GUI
  change.
