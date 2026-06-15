from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel

from bec_widgets.utils.eliding_label import ElidingLabel


def test_eliding_label_keeps_full_text_but_elides_display(qtbot):
    label = ElidingLabel()
    qtbot.addWidget(label)
    full = "a very long label text that will not fit in a narrow widget"
    label.setText(full)

    label.resize(50, 20)
    label._elide()

    # The logical value is preserved, while the rendered text is shortened with an ellipsis.
    assert label.text() == full
    assert QLabel.text(label) != full
    assert QLabel.text(label).endswith("…")


def test_eliding_label_shows_full_text_when_wide_enough(qtbot):
    label = ElidingLabel()
    qtbot.addWidget(label)
    label.setText("short")

    label.resize(400, 20)
    label._elide()

    assert label.text() == "short"
    assert QLabel.text(label) == "short"


def test_eliding_label_respects_elide_mode(qtbot):
    label = ElidingLabel()
    qtbot.addWidget(label)
    label.setText("a very long label text that will not fit in a narrow widget")
    label.resize(50, 20)

    label.set_elide_mode(Qt.TextElideMode.ElideMiddle)

    assert "…" in QLabel.text(label)
    assert not QLabel.text(label).endswith("…")
