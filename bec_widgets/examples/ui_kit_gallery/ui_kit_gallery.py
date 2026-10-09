"""Gallery of the BEC UI kit: every control in QML and in QWidgets, side by side.

Run it to check a change to the kit in both technologies and both themes::

    python -m bec_widgets.examples.ui_kit_gallery.ui_kit_gallery
    python -m bec_widgets.examples.ui_kit_gallery.ui_kit_gallery --theme light
    python -m bec_widgets.examples.ui_kit_gallery.ui_kit_gallery --screenshots ./shots

With ``--screenshots`` the gallery renders offscreen into PNG files and exits.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.quick import create_quick_widget, release_quick_widget
from bec_widgets.utils.quick.tokens import ThemeTokens
from bec_widgets.utils.ux_kit import (
    Badge,
    Banner,
    Card,
    EmptyState,
    FormField,
    IconButton,
    LinearProgress,
    SearchField,
    SegmentedControl,
    Spinner,
    StatusPill,
    SuffixLineEdit,
    TextButton,
    ToggleSwitch,
    field_qss,
)

QML_GALLERY = Path(__file__).with_name("UiKitGallery.qml")


def _row(*widgets, spacing: int = 8, stretch: bool = True) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setSpacing(spacing)
    for widget in widgets:
        if isinstance(widget, int):
            layout.addSpacing(widget)
        else:
            layout.addWidget(widget)
    if stretch:
        layout.addStretch(1)
    return layout


def _muted(text: str) -> QLabel:
    tokens = ThemeTokens.current()
    label = QLabel(text)
    label.setStyleSheet(
        f"color: {tokens.fg_muted.name()}; font-size: {tokens.metrics['fontSmall']}px;"
        " background: none;"
    )
    return label


class QWidgetGallery(QWidget):
    """The QWidget twin of ``UiKitGallery.qml``."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("uxGallery")
        tokens = ThemeTokens.current()
        self.setStyleSheet(f"QWidget#uxGallery {{ background: {tokens.bg.name()}; }}")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        grid = QGridLayout(self)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        cards = [
            self._buttons(),
            self._status(),
            self._inputs(tokens),
            self._feedback(),
            self._cards(tokens),
            self._empty(),
        ]
        for index, card in enumerate(cards):
            grid.addWidget(card, index // 2, index % 2, Qt.AlignmentFlag.AlignTop)
        cards[-1].setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        grid.addWidget(cards[-1], 2, 1)
        grid.setRowStretch(3, 1)

    @staticmethod
    def _buttons() -> Card:
        card = Card("Buttons")
        card.set_title("Buttons", "TextButton · IconButton")
        card.body.addLayout(
            _row(
                TextButton("Start scan", "primary", "play_arrow"),
                TextButton("Resume", "success", "play_arrow"),
                TextButton("Stop", "danger", "stop"),
            )
        )
        card.body.addLayout(
            _row(
                TextButton("Settings", "neutral", "tune"),
                TextButton("Abort queue", "dangerOutline", "cancel"),
                TextButton("Details", "ghost"),
            )
        )
        busy = TextButton("Submitting", "primary")
        busy.set_busy(True)
        disabled = TextButton("Disabled")
        disabled.setEnabled(False)
        card.body.addLayout(
            _row(busy, disabled, TextButton("Compact", icon_name="refresh", compact=True))
        )
        pin = IconButton("push_pin", "Pin")
        pin.setCheckable(True)
        pin.setChecked(True)
        more = IconButton("more_vert", "More")
        more.setEnabled(False)
        card.body.addLayout(
            _row(
                IconButton("pause", "Pause"),
                pin,
                IconButton("content_copy", "Copy"),
                IconButton("delete", "Remove", danger=True),
                more,
                spacing=4,
            )
        )
        return card

    @staticmethod
    def _status() -> Card:
        card = Card()
        card.set_title("Status", "StatusPill · Badge · Spinner · LinearProgress")
        card.body.addLayout(
            _row(
                StatusPill(text="Idle", tone="neutral", outlined=True),
                StatusPill(text="Running", tone="info", pulse=True),
                StatusPill(text="Done", tone="success"),
                StatusPill(text="Paused", tone="warning"),
                StatusPill(text="Failed", tone="danger"),
                spacing=6,
            )
        )
        card.body.addLayout(
            _row(
                StatusPill(text="Moving", tone="info", icon_name="sync"),
                StatusPill(text="Limit", tone="warning", icon_name="warning"),
                StatusPill(text="Offline", tone="danger", icon_name="cloud_off"),
                StatusPill(text="Stale", tone="stale", icon_name="schedule", outlined=True),
                spacing=6,
            )
        )
        inbox = QLabel("Inbox")
        tokens = ThemeTokens.current()
        inbox.setStyleSheet(f"color: {tokens.fg.name()}; font-size: 13px; background: none;")
        row = _row(
            inbox,
            Badge(count=3),
            Badge(count=128, tone="warning"),
            Badge(count=7, tone="primary"),
            spacing=10,
        )
        row.addWidget(Spinner(size=16))
        row.addWidget(_muted("Connecting"))
        card.body.addLayout(row)
        bars = QGridLayout()
        bars.setHorizontalSpacing(10)
        bars.setVerticalSpacing(8)
        for index, (label, value, tone) in enumerate(
            [("Scan 42", 0.64, "primary"), ("Readout", 1.0, "success"), ("Beam", 0.28, "warning")]
        ):
            bar = LinearProgress(tone=tone)
            bar.set_value(value, animate=False)
            bars.addWidget(_muted(label), index, 0)
            bars.addWidget(bar, index, 1)
        waiting = LinearProgress()
        waiting.set_indeterminate(True)
        bars.addWidget(_muted("Waiting"), 3, 0)
        bars.addWidget(waiting, 3, 1)
        bars.setColumnStretch(1, 1)
        card.body.addLayout(bars)
        return card

    @staticmethod
    def _inputs(tokens: ThemeTokens) -> Card:
        card = Card()
        card.set_title("Inputs", "FormField · fields · SegmentedControl")
        card.setStyleSheet(card.styleSheet() + field_qss(tokens))
        card.body.addWidget(SearchField(placeholder="Search devices", shortcut_hint="Ctrl K"))
        start = SuffixLineEdit()
        start.setText("-5.000")
        start.set_suffix("mm")
        steps = SuffixLineEdit()
        steps.setText("1")
        steps_field = FormField("Steps", steps, required=True)
        steps_field.set_error("Must be at least 2")
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(
            FormField("Start", start, required=True, helper="Within soft limits", unit="mm"), 1
        )
        row.addWidget(steps_field, 1)
        card.body.addLayout(row)
        motor = QComboBox()
        motor.addItems(["samx", "samy", "samz"])
        switch = ToggleSwitch()
        switch.setChecked(True)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(FormField("Motor", motor), 1)
        row.addWidget(FormField("Relative", switch), 1)
        card.body.addLayout(row)
        segmented = SegmentedControl(
            [
                {"text": "All", "count": 24},
                {"text": "Errors", "count": 2},
                {"text": "Warnings", "count": 5},
            ]
        )
        segmented.set_current_index(1)
        card.body.addLayout(_row(segmented))
        return card

    @staticmethod
    def _feedback() -> Card:
        card = Card()
        card.set_title("Feedback", "Banner · EmptyState")
        card.body.addWidget(Banner("info", text="Scan queued behind 2 others."))
        card.body.addWidget(
            Banner(
                "warning",
                "Beam intensity low",
                "Ring current is 12 mA below nominal.",
                closable=True,
            )
        )
        card.body.addWidget(
            Banner(
                "danger",
                "Device server not responding",
                "Last heartbeat 40 s ago.",
                action_text="Retry",
            )
        )
        card.body.addWidget(Banner("success", text="Configuration saved."))
        return card

    @staticmethod
    def _cards(tokens: ThemeTokens) -> Card:
        card = Card()
        card.set_title("Cards", "titles, collapsible sections")
        card.add_header_widget(IconButton("refresh", "Refresh", compact=True))
        card.add_header_widget(IconButton("more_vert", "More", compact=True))
        section = Card("Scan arguments", title_style="caption", collapsible=True, surface="sunken")
        section.setStyleSheet(section.styleSheet() + field_qss(tokens))
        motor = SuffixLineEdit()
        motor.setText("samx")
        motor.set_icon_name("precision_manufacturing")
        time = SuffixLineEdit()
        time.setText("0.5")
        time.set_suffix("s")
        time.setFixedWidth(90)
        row = QHBoxLayout()
        row.addWidget(motor, 1)
        row.addWidget(time)
        section.body.addLayout(row)
        card.body.addWidget(section)
        closed = Card("Metadata", title_style="caption", collapsible=True, surface="sunken")
        closed.set_expanded(False)
        card.body.addWidget(closed)
        return card

    @staticmethod
    def _empty() -> Card:
        card = Card("Empty state")
        card.body.addStretch(1)
        card.body.addWidget(
            EmptyState(
                "playlist_play",
                "Queue is empty",
                "Scans you submit appear here with their progress.",
                action_text="Open scan control",
                action_icon="add",
            )
        )
        card.body.addStretch(1)
        return card


class QmlGallery(QWidget):
    """Hosts ``UiKitGallery.qml`` in a QQuickWidget."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = create_quick_widget(self, QML_GALLERY, raise_on_error=True)
        layout.addWidget(self.view)
        root = self.view.rootObject()
        self.setMinimumSize(
            int(root.property("implicitWidth")), int(root.property("implicitHeight"))
        )

    def closeEvent(self, event):  # pylint: disable=invalid-name
        release_quick_widget(self.view)
        super().closeEvent(event)


def _grab(widget: QWidget, path: Path) -> None:
    # QWidget.grab() also captures QQuickWidget content, at any QT_SCALE_FACTOR
    widget.grab().save(str(path))


def main(argv: list[str] | None = None) -> int:
    """Show the gallery, or render screenshots with ``--screenshots DIR``."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--theme", choices=["dark", "light"], default="dark")
    parser.add_argument("--screenshots", type=Path, default=None)
    args = parser.parse_args(argv)
    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(args.theme)
    if args.screenshots is not None:
        args.screenshots.mkdir(parents=True, exist_ok=True)
        for theme in ("dark", "light"):
            apply_theme(theme)
            for name, cls in (("qml", QmlGallery), ("qwidget", QWidgetGallery)):
                widget = cls()
                widget.resize(760, 752)
                widget.show()
                loop_until = QTimer()
                loop_until.setSingleShot(True)
                loop_until.timeout.connect(app.quit)
                loop_until.start(700)
                app.exec()
                _grab(widget, args.screenshots / f"gallery_{name}_{theme}.png")
                widget.close()
                widget.deleteLater()
        return 0
    window = QWidget()
    window.setWindowTitle("BEC UI kit")
    layout = QHBoxLayout(window)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(QmlGallery())
    layout.addWidget(QWidgetGallery())
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
