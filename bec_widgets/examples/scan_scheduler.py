"""Open a scheduler with an editable example using a running BEC deployment.

Run with ``python -m bec_widgets.examples.scan_scheduler``. Opening the example does
not execute it; inspect the description before choosing Execute.
"""

from __future__ import annotations

import sys

from bec_lib.scan_sequencer.components import ForEach, Repeat, ScanCall, Schedule, Sequence, Set
from qtpy.QtWidgets import QApplication

from bec_widgets.widgets.control.scan_scheduler import ScanScheduler


def example_sequence() -> Schedule:
    """Compose four time scans interleaved with alternating device moves.

    Returns:
        Schedule: Editable example requiring samx and the advertised time_scan scan.
    """
    return Schedule(
        id="alternating_positions",
        revision=1,
        root=Repeat(
            id="repeat",
            count=2,
            body=ForEach(
                id="positions",
                variable="position",
                values=[1, -1],
                body=Sequence(
                    id="steps",
                    children=[
                        Set(id="move", device="samx", value={"ref": "position"}, wait=True),
                        ScanCall(id="scan", name="time_scan", positional=[1, 0.1]),
                    ],
                ),
            ),
        ),
    )


def main() -> None:
    """Open the scheduler; execution requires an explicit Execute action."""
    app = QApplication.instance() or QApplication(sys.argv)
    widget = ScanScheduler()
    widget.setWindowTitle("BEC Scan Scheduler")
    widget.resize(1400, 1000)
    widget.load_json(example_sequence().model_dump_json())
    widget.show()
    app.exec()
    widget.cleanup()


if __name__ == "__main__":
    main()
