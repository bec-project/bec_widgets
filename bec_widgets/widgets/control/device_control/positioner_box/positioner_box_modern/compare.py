"""Show the current, QML and QWidget positioner boxes side by side against a running BEC.

Usage: python -m bec_widgets.widgets.control.device_control.positioner_box.positioner_box_modern.compare samx [dark|light]
"""

import sys

from qtpy.QtWidgets import QApplication, QGridLayout, QLabel, QWidget

from bec_widgets.utils.colors import apply_theme
from bec_widgets.widgets.control.device_control.positioner_box import PositionerBox
from bec_widgets.widgets.control.device_control.positioner_box.positioner_box_modern import (
    PositionerBoxQML,
    PositionerBoxWidgets,
)


def main():  # pragma: no cover
    """Open the comparison window."""
    app = QApplication(sys.argv)
    device = sys.argv[1] if len(sys.argv) > 1 else "samx"
    apply_theme(sys.argv[2] if len(sys.argv) > 2 else "dark")
    window = QWidget()
    window.setWindowTitle(f"Positioner box comparison: {device}")
    grid = QGridLayout(window)
    for column, (title, cls) in enumerate(
        (("Current", PositionerBox), ("QML", PositionerBoxQML), ("QWidget", PositionerBoxWidgets))
    ):
        grid.addWidget(QLabel(title), 0, column)
        grid.addWidget(cls(device=device), 1, column)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
