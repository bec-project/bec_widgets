"""
Show the original, QML and QWidget beamline-state views side by side.

Run against a live BEC session: ``python -m bec_widgets.widgets.services.beamline_states.modern.compare_demo``
"""

from __future__ import annotations

import sys

from qtpy.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from bec_widgets.utils.colors import apply_theme
from bec_widgets.widgets.services.beamline_states.beamline_state_manager import BeamlineStateManager
from bec_widgets.widgets.services.beamline_states.modern.beamline_states_qml import (
    BeamlineStatesQML,
)
from bec_widgets.widgets.services.beamline_states.modern.beamline_states_widget import (
    BeamlineStatesWidget,
)
from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)
    apply_theme("dark")
    window = QWidget()
    window.setWindowTitle("Beamline States: original vs QML vs QWidget")
    columns = QHBoxLayout()
    for title, cls in (
        ("Original", BeamlineStateManager),
        ("QML", BeamlineStatesQML),
        ("QWidget", BeamlineStatesWidget),
    ):
        column = QVBoxLayout()
        column.addWidget(QLabel(f"<b>{title}</b>"))
        column.addWidget(cls(parent=window), 1)
        columns.addLayout(column, 1)
    top = QHBoxLayout()
    top.addStretch(1)
    top.addWidget(DarkModeButton(parent=window))
    layout = QVBoxLayout(window)
    layout.addLayout(top)
    layout.addLayout(columns, 1)
    window.resize(1800, 700)
    window.show()
    sys.exit(app.exec())
