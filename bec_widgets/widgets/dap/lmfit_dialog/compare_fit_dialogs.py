"""Show the current, QWidget and QML fit dialogs side by side with the same simulated fits.

Run with ``python -m bec_widgets.widgets.dap.lmfit_dialog.compare_fit_dialogs [--light] [--live]``.
"""

from __future__ import annotations

import math
import sys

from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QApplication, QGroupBox, QHBoxLayout, QVBoxLayout, QWidget

from bec_widgets.utils.colors import apply_theme
from bec_widgets.widgets.dap.lmfit_dialog.lmfit_dialog import LMFitDialog
from bec_widgets.widgets.dap.lmfit_dialog.lmfit_dialog_qml import LMFitDialogQml
from bec_widgets.widgets.dap.lmfit_dialog.lmfit_dialog_qwidget import LMFitDialogQWidget


def sample_fit(curve_id: str, step: int = 0) -> dict:
    """Return a DAP-like LMFit summary for the demo curves.

    Args:
        curve_id (str): One of the demo curve names.
        step (int): Update counter, used to jitter the values like a live fit.

    Returns:
        dict: A fit summary in the LMFit DAP format.
    """
    jitter = 1 + 0.02 * math.sin(step)
    if curve_id == "bpm4i-gauss":
        center = -0.0412 * jitter
        return {
            "model": "Model(gaussian)",
            "method": "leastsq",
            "ndata": 101,
            "nvarys": 3,
            "nfev": 31,
            "chisqr": 0.0421 * jitter,
            "redchi": 0.000429 * jitter,
            "rsquared": 0.9987,
            "success": True,
            "message": "Fit succeeded.",
            "params": [
                [
                    "amplitude",
                    12.84 * jitter,
                    True,
                    None,
                    -math.inf,
                    math.inf,
                    None,
                    0.071,
                    {},
                    1.0,
                    None,
                ],
                ["center", center, True, None, -math.inf, math.inf, None, 0.0009, {}, 0.0, None],
                [
                    "sigma",
                    0.2471,
                    True,
                    None,
                    0,
                    math.inf,
                    None,
                    0.0016,
                    {"amplitude": 0.58},
                    1.0,
                    None,
                ],
                [
                    "fwhm",
                    0.5819,
                    False,
                    "2.3548200*sigma",
                    -math.inf,
                    math.inf,
                    None,
                    0.0038,
                    {},
                    None,
                    None,
                ],
            ],
        }
    if curve_id == "diode-breit_wigner":
        return {
            "model": "Model(breit_wigner)",
            "method": "leastsq",
            "ndata": 4,
            "nvarys": 4,
            "nfev": 2498,
            "chisqr": 1.2583,
            "redchi": 1.2583,
            "rsquared": 0.8650 + 0.05 * math.sin(step),
            "success": True,
            "message": "Fit succeeded.",
            "params": [
                [
                    "amplitude",
                    1.5824,
                    True,
                    None,
                    -math.inf,
                    math.inf,
                    None,
                    1.3249,
                    {"center": 0.843},
                    1.0,
                    None,
                ],
                [
                    "center",
                    -2.8415 * jitter,
                    True,
                    None,
                    -math.inf,
                    math.inf,
                    None,
                    0.5077,
                    {"sigma": -0.9988},
                    0.0,
                    None,
                ],
                [
                    "sigma",
                    0.000255,
                    True,
                    None,
                    0.0,
                    math.inf,
                    None,
                    113.25,
                    {"q": 0.99999},
                    1.0,
                    None,
                ],
                [
                    "q",
                    -259.85,
                    True,
                    None,
                    -math.inf,
                    math.inf,
                    None,
                    114893884.6,
                    {"sigma": 0.99999},
                    1.0,
                    None,
                ],
            ],
        }
    return {
        "model": "Model(lorentzian) + Model(linear)",
        "method": "leastsq",
        "ndata": 41,
        "nvarys": 5,
        "nfev": 10000,
        "chisqr": 88.1,
        "redchi": 2.448,
        "rsquared": 0.41,
        "success": False,
        "message": "Fit aborted: number of function evaluations > 10000",
        "params": [
            ["amplitude", 3.1, True, None, -math.inf, math.inf, None, None, {}, 1.0, None],
            ["center", 0.88, True, None, -math.inf, math.inf, None, None, {}, 0.0, None],
            ["slope", 0.0, False, None, -math.inf, math.inf, None, None, {}, 0.0, None],
        ],
    }


CURVES = ["bpm4i-gauss", "diode-breit_wigner", "temp-lorentz"]


def main():  # pragma: no cover - interactive demo
    """Open the comparison window."""
    app = QApplication(sys.argv)
    apply_theme("light" if "--light" in sys.argv else "dark")
    window = QWidget()
    window.setWindowTitle("Fit dialog: current vs QWidget vs QML")
    layout = QHBoxLayout(window)
    dialogs = []
    for title, cls in (
        ("Current", LMFitDialog),
        ("QWidget redesign", LMFitDialogQWidget),
        ("QML redesign", LMFitDialogQml),
    ):
        box = QGroupBox(title)
        box_layout = QVBoxLayout(box)
        dialog = cls(parent=box)
        dialog.active_action_list = ["center"]
        dialog.move_action.connect(lambda action, t=title: print(f"{t}: move {action}"))
        box_layout.addWidget(dialog)
        layout.addWidget(box)
        dialogs.append(dialog)

    step = {"n": 0}

    def tick():
        step["n"] += 1
        for curve_id in CURVES:
            for dialog in dialogs:
                dialog.update_summary_tree(sample_fit(curve_id, step["n"]), {"curve_id": curve_id})

    tick()
    timer = QTimer(window)
    timer.timeout.connect(tick)
    if "--live" in sys.argv:
        timer.start(500)
    window.resize(1250, 520)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
