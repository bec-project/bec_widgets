![banner_opti](https://github.com/user-attachments/assets/44e483be-3f0d-4eb0-bd98-613157456b81)

# BEC Widgets

[![CI](https://github.com/bec-project/bec_widgets/actions/workflows/ci.yml/badge.svg)](https://github.com/bec-project/bec_widgets/actions/workflows/ci.yml)
[![badge](https://img.shields.io/pypi/v/bec-widgets)](https://pypi.org/project/bec-widgets/)
[![License](https://img.shields.io/github/license/bec-project/bec_widgets)](./LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue?logo=python&logoColor=white)](https://www.python.org)
[![PySide6](https://img.shields.io/badge/PySide6-blue?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![Conventional Commits](https://img.shields.io/badge/conventional%20commits-1.0.0-yellow?logo=conventionalcommits&logoColor=white)](https://conventionalcommits.org)
[![codecov](https://codecov.io/gh/bec-project/bec_widgets/graph/badge.svg?token=0Z9IQRJKMY)](https://codecov.io/gh/bec-project/bec_widgets)

A modular PySide6(Qt6) toolkit for [BEC (Beamline Experiment Control)](https://github.com/bec-project/bec). Create
high-performance, dockable GUIs to move devices, run scans, and stream live or disk data—powered by Redis and a modular
plugin system.

## Highlights

- **No-code first** — For ~90% of day-to-day workflows, you can compose, operate, and save workspaces **without writing
  a single line of code**. Just launch, drag widgets, and do your experiment.
- **Flexible layout composition** — Build complex experiment GUIs in seconds with the `BECDockArea`: drag‑dock, tab,
  split, and export profiles/workspaces for reuse.
- **CLI / scripting** — Control your beamline experiment from the command line a robust RPC layer using
  `BECIPythonClient`.
- **Designer integration** — Use Qt Designer plugins to drop BEC widgets next to any Qt control, then launch the `.ui`
  with the custom BEC loader for a zero‑glue workflow.
- **Operational integration** — Widgets stay in sync with your running BEC/Redis as the single source of truth:
  Subscribe to events from BEC and create dynamically updating UIs. BECWidgets also grants you easy access the
  acquisition history.
- **Extensible by design** — Build new widgets with minimal boilerplate using `BECWidget` and `BECDispatcher` for BEC data and
  messaging. Use the generator command to scaffold RPC interfaces and Designer plugin stubs; beamline plugins can extend
  or override behavior as needed.

## Table of Contents

- [Installation](#installation)
- [Features](#features)
    - [1. Dock area interface: build GUIs in seconds](#1-dock-area-interface-build-guis-in-seconds)
    - [2. Qt Designer plugins + BEC Launcher (no glue)](#2-qt-designer-plugins--bec-launcher-no-glue)
    - [3. Robust RPC from CLI & remote scripting](#3-robust-rpc-from-cli--remote-scripting)
    - [4. Rapid development (extensible by design)](#4-rapid-development-extensible-by-design)
- [Widget Library](#widget-library)
- [Documentation](#documentation)
- [License](#license)

## Installation

Use any of the following setups:

### Stable release

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install BEC Widgets:

```bash
pip install bec_widgets
```

### From source (recommended for development)

For development purposes, you can clone the repository and install the package locally in editable mode:

```bash
git clone https://github.com/bec-project/bec_widgets.git
cd bec_widgets
pip install -e .[dev]
```

## Features

### 1. Dock area interface: build GUIs in seconds

The fastest way to explore BEC Widgets. Launch the BEC IPython client with simply `bec` in terminal and the **BECDockArea** opens as the default UI:
drag widgets, dock/tab/split panes, and explore. Everything is live—widgets auto-connect to BEC/Redis, so you can
operate immediately and refine later with RPC or Designer if needed.

![dock_area_example](https://github.com/user-attachments/assets/219a2806-19a8-4a07-9734-b7b554850833)

### 2. Qt Designer plugins + BEC Launcher (no glue)

All BEC Widgets ship as **Qt Designer plugins** with our custom Qt Designer launchable by `bec-designer`. Design your UI
visually in Designer, save a `.ui`, then launch it with
the **BEC Launcher**—no glue code. Widgets auto‑connect to BEC/Redis on startup, so your UI is operational immediately.

![designer_opti](https://github.com/user-attachments/assets/fed4843c-1cce-438a-b41f-6636fa5e1545)

### 3. Robust RPC from CLI & remote scripting

Operate and automate BEC Widgets directly from the `BECIPythonClient`. Create or attach to GUIs, address any sub-widget
via a simple hierarchical API with tab-completion, and script event-driven behavior that reacts to BEC (scan lifecycle,
active devices, topics)—so your UI can be heavily automated.

- Create & control GUIs: launch, load profiles, open/close panels, tweak properties—all from the shell.
- Hierarchical addressing: navigate widgets and sub-widgets with discoverable paths and tab-completion.
- Event scripting: subscribe to BEC events (e.g., scan start/finish, device readiness, topic updates) and trigger
  actions,switch profiles, open diagnostic views, or start specific scans.
- Remote & headless: run automation on analysis nodes or from notebooks without a local GUI process.
- Plays with no-code: Use the Dock Area / BEC Designer to set up the layout and add automation with RPC when needed.

![rpc_opti](https://github.com/user-attachments/assets/666be7fb-9a0d-44c2-8d44-2f9d1dae4497)

### 4. Rapid development (extensible by design)

Build new widgets fast: Inherit from `BECWidget`, list your RPC methods in `USER_ACCESS`, and use `bec_dispatcher` to
bind endpoints. Then run `bw-generate-cli --target <your-plugin-repo>`. This generates the RPC CLI bindings and a Qt
Designer plugin that are immediately usable with your BEC setup. Widgets
come online with live BEC/Redis wiring out of the box. ￼

<details>
<summary> View code: Example Widget </summary>

```python
    from typing import Literal

from qtpy.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QApplication
from qtpy.QtCore import Slot

from bec_lib.endpoints import MessageEndpoints
from bec_widgets import BECWidget, SafeSlot


class SimpleMotorWidget(BECWidget, QWidget):
    USER_ACCESS = ["move"]

    def __init__(self, parent=None, motor_name="samx", step=5.0, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.motor_name = motor_name
        self.step = float(step)

        self.get_bec_shortcuts()

        self.value_label = QLabel(f"{self.motor_name}: —")
        self.btn_left = QPushButton("◀︎ -5")
        self.btn_right = QPushButton("+5 ▶︎")

        row = QHBoxLayout()
        row.addWidget(self.btn_left)
        row.addWidget(self.btn_right)

        col = QVBoxLayout(self)
        col.addWidget(self.value_label)
        col.addLayout(row)

        self.btn_left.clicked.connect(lambda: self.move("left", self.step))
        self.btn_right.clicked.connect(lambda: self.move("right", self.step))

        self.bec_dispatcher.connect_slot(self.on_readback, MessageEndpoints.device_readback(self.motor_name))

    @SafeSlot(dict, dict)
    def on_readback(self, data: dict, meta: dict):
        current_value = data.get("signals").get(self.motor_name).get('value')
        self.value_label.setText(f"{self.motor_name}: {current_value:.3f}")

    @Slot(str, float)
    def move(self, direction: Literal["left", "right"] = "left", step: float = 5.0):
        if direction == "left":
            self.dev[self.motor_name].move(-step, relative=True)
        else:
            self.dev[self.motor_name].move(step, relative=True)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    w = SimpleMotorWidget(motor_name="samx", step=5.0)
    w.setWindowTitle("MotorJogWidget")
    w.resize(280, 90)
    w.show()
    sys.exit(app.exec_())
```

</details>

## Widget Library

A large and growing catalog—plug, configure, run:

### Plotting

Waveform, MultiWaveform, and Image/Heatmap widgets deliver responsive plots with crosshairs and ROIs for live and
history data.

<img width="1108" height="838" alt="plotting_hr" src="https://github.com/user-attachments/assets/f50462a5-178d-44d4-aee5-d378c74b107b" />

### Scan orchestration and motion control.

Start and stop scans, track progress, reuse parameter presets, and browse history from a focused control surface.
Positioner boxes and tweak controls handle precise moves, homing, and calibration for day‑to‑day alignment.

<img width="1496" height="1388" alt="control" src="https://github.com/user-attachments/assets/d4fb2e2e-04f9-4621-8087-790680797620" />

## Documentation

Documentation of BEC Widgets can be found [here](https://bec-widgets.readthedocs.io/en/latest/). The documentation of
the BEC can be found [here](https://bec.readthedocs.io/en/latest/).

## License

[BSD-3-Clause](https://choosealicense.com/licenses/bsd-3-clause/)
