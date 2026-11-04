import pytest
from qtpy.QtCore import QSettings, Qt
from qtpy.QtWidgets import QLabel, QSizePolicy

from bec_widgets.tests.utils import create_widget
from bec_widgets.widgets.containers.main_window.addons.status_pill import (
    PILL_WIDTHS,
    PillStyle,
    StatusIconPill,
    StatusPillItem,
    ToolIndicator,
    ToolSeverity,
    indicator_icon,
    stage_mode,
)
from bec_widgets.widgets.progress.stage_bar import BarMode, Tone


@pytest.mark.parametrize(
    "indicator, expected",
    [
        (ToolIndicator(), (BarMode.IDLE, 0.0)),
        (ToolIndicator(severity=ToolSeverity.OK), (BarMode.DONE, 1.0)),
        (ToolIndicator(severity=ToolSeverity.INFO, active=True), (BarMode.BUSY, 0.0)),
        (ToolIndicator(severity=ToolSeverity.INFO, progress=0.25), (BarMode.PROGRESS, 0.25)),
        (ToolIndicator(severity=ToolSeverity.OK, progress=0.5), (BarMode.PROGRESS, 0.5)),
        (ToolIndicator(severity=ToolSeverity.WARNING, progress=0.4), (BarMode.PAUSED, 0.4)),
        (ToolIndicator(severity=ToolSeverity.WARNING, active=True), (BarMode.PAUSED, 0.0)),
        (ToolIndicator(severity=ToolSeverity.CRITICAL, progress=0.3), (BarMode.ERROR, 1.0)),
    ],
)
def test_indicator_maps_to_a_bar_mode(indicator, expected):
    assert stage_mode(indicator) == expected


def test_a_paused_bar_is_filled_to_its_fraction(qtbot):
    from qtpy.QtGui import QColor

    from bec_widgets.widgets.progress.stage_bar import StageBar

    bar = StageBar()
    qtbot.addWidget(bar)
    bar.resize(200, 20)

    def filled_columns(fraction):
        bar.set_state(BarMode.PAUSED, fraction)
        image = bar.grab().toImage()
        row = image.height() // 2
        track = QColor(image.pixel(image.width() - 3, row))
        return sum(
            1 for x in range(image.width()) if QColor(image.pixel(x, row)).rgb() != track.rgb()
        )

    quarter, three_quarters = filled_columns(0.25), filled_columns(0.75)
    assert quarter < three_quarters
    assert three_quarters == pytest.approx(3 * quarter, rel=0.25)


@pytest.fixture
def generic_item(qtbot, mocked_client, tmp_path):
    content = QLabel("All good")
    widget = create_widget(
        qtbot,
        StatusPillItem,
        client=mocked_client,
        settings=lambda: QSettings(str(tmp_path / "pill.ini"), QSettings.Format.IniFormat),
        settings_prefix="demo_pill",
        card_content=content,
        card_width=260,
    )
    widget.apply_sizes()
    yield widget


def test_generic_item_shows_any_indicator_and_content(generic_item, qtbot):
    item = generic_item
    assert item.card.content.text() == "All good"
    assert item.card.card.width() == 260
    seen = []
    item.indicator_changed.connect(seen.append)

    down = ToolIndicator(
        severity=ToolSeverity.CRITICAL,
        summary="2 services down",
        badge="2 down",
        attention=True,
        tooltip="x",
    )
    item.set_indicator(down)
    item.set_indicator(down)  # unchanged: no second signal
    assert seen == [down]
    assert (item.pill.mode, item.pill.text) == (BarMode.ERROR, "2 services down")
    assert item.pill.toolTip() == "x"
    assert item.badge_chip.text() == "2 down" and item.badge_chip._tone == Tone.BAD
    assert item.badge_reveal.shown

    item.set_indicator(ToolIndicator(severity=ToolSeverity.OK, summary="BEC running"))
    assert item.pill.mode == BarMode.DONE
    qtbot.waitUntil(lambda: not item.badge_reveal.shown, timeout=2000)  # after the hide delay
    qtbot.waitUntil(lambda: not item.badge_reveal.active, timeout=2000)


def test_generic_item_saves_its_choices_under_its_prefix(generic_item, tmp_path):
    generic_item.set_width_mode("wide")
    generic_item.set_large(True)
    settings = QSettings(str(tmp_path / "pill.ini"), QSettings.Format.IniFormat)
    assert settings.value("demo_pill/pill_width") == "wide"
    assert settings.value("demo_pill/large", type=bool) is True
    assert settings.value("scan_status/pill_width") is None


def _cursor_at(monkeypatch, point):
    from bec_widgets.utils import hover_card

    monkeypatch.setattr(hover_card.QCursor, "pos", staticmethod(lambda: point))


def _outer_rect(item):
    from qtpy.QtCore import QPoint, QRect

    return QRect(item.card.card.mapToGlobal(QPoint(0, 0)), item.card.card.size())


def test_card_stays_on_screen_and_follows_the_pill(generic_item, qtbot, monkeypatch):
    from qtpy.QtCore import QPoint
    from qtpy.QtWidgets import QPushButton

    item = generic_item
    button = QPushButton("Stop", item)
    reveal = item.add_trailing(button)
    area = item.screen().availableGeometry()
    item.move(area.right() - item.sizeHint().width() + 1, area.bottom() - 60)
    item.show()
    qtbot.waitExposed(item)
    _cursor_at(monkeypatch, QPoint(-5000, -5000))
    item.open_card()
    window = item.card.frameGeometry()
    assert area.contains(window), (area, window)  # clamped at the right edge of the screen

    # the content grows: the card stays bottom-anchored above the pill
    pill_top = item.pill.mapToGlobal(QPoint(0, 0)).y()
    item.card.content.setText("All good\nbut a much longer\nexplanation\nover four lines")
    qtbot.waitUntil(lambda: item.card.height() > window.height(), timeout=2000)
    qtbot.waitUntil(lambda: _outer_rect(item).bottom() < pill_top, timeout=2000)

    # a widget slides in next to the pill and moves it: the card follows
    item.move(area.left() + 40, area.bottom() - 60)
    qtbot.wait(50)
    item.close_card()
    item.open_card()
    before = item.pill.mapToGlobal(QPoint(0, 0)).x() - item.card.x()
    reveal.set_shown(True)
    qtbot.waitUntil(lambda: not reveal.active, timeout=2000)
    after = item.pill.mapToGlobal(QPoint(0, 0)).x() - item.card.x()
    assert after == before
    item.close_card()


def test_card_stays_open_while_a_dialog_of_its_content_is_open(generic_item, qtbot, monkeypatch):
    from qtpy.QtCore import QPoint, Qt
    from qtpy.QtGui import QCursor
    from qtpy.QtWidgets import QDialog

    item = generic_item
    item.show()
    qtbot.waitExposed(item)
    _cursor_at(monkeypatch, QPoint(-5000, -5000))
    item.open_card()
    dialog = QDialog(item.card.content)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.show()
    qtbot.waitUntil(dialog.isVisible)
    qtbot.wait(item.GRACE_MS + 300)
    assert item.card.isVisible()  # e.g. a restart confirmation of the status box

    away = item.card.frameGeometry().bottomRight() + QPoint(2000, 2000)
    QCursor.setPos(away)  # so Qt itself does not re-enter the card when the dialog closes
    _cursor_at(monkeypatch, away)
    dialog.close()
    qtbot.waitUntil(lambda: not item.card.isVisible(), timeout=2000)
    dialog.deleteLater()


class DockablePill(StatusPillItem):
    DOCK_WIDGET = "BECQueue"


@pytest.fixture
def dockable_item(qtbot, mocked_client, tmp_path):
    widget = create_widget(
        qtbot,
        DockablePill,
        client=mocked_client,
        settings=lambda: QSettings(str(tmp_path / "dock.ini"), QSettings.Format.IniFormat),
        settings_prefix="dock_pill",
        card_content=QLabel("details"),
    )
    widget.apply_sizes()
    yield widget


def test_dock_hint_only_with_a_dock_widget_and_a_handler(generic_item, dockable_item):
    assert generic_item.card.hint is None  # no DOCK_WIDGET, no hint
    hint = dockable_item.card.hint
    assert hint is not None and hint.isHidden()  # no handler yet
    available = [False]
    dockable_item.set_dock_handler(lambda: available[0])
    assert hint.isHidden() and dockable_item.pill.accessibleDescription() == ""
    available[0] = True
    dockable_item._prepare_card()  # asked again each time the card opens
    assert not hint.isHidden()
    assert hint.text() == dockable_item.DOCK_HINT
    assert dockable_item.pill.accessibleDescription() == dockable_item.DOCK_HINT
    dockable_item.set_dock_handler(None)
    assert hint.isHidden()


def test_double_click_requests_its_widget_and_closes_the_card(dockable_item, qtbot):
    dockable_item.set_dock_handler(lambda: True)
    dockable_item.open_card()
    qtbot.waitUntil(dockable_item.card.isVisible)
    with qtbot.waitSignal(dockable_item.dock_requested) as blocker:
        qtbot.mouseDClick(dockable_item.pill, Qt.MouseButton.LeftButton)
    assert blocker.args == ["BECQueue"]
    assert not dockable_item.card.isVisible()
    assert not dockable_item.pill.hasFocus()  # a double-click does not focus the pill


def test_double_click_does_nothing_without_a_dock_area(dockable_item, generic_item, qtbot):
    dockable_item.set_dock_handler(lambda: False)
    with qtbot.assertNotEmitted(dockable_item.dock_requested):
        qtbot.mouseDClick(dockable_item.pill, Qt.MouseButton.LeftButton)
    with qtbot.assertNotEmitted(generic_item.dock_requested):
        qtbot.mouseDClick(generic_item.pill, Qt.MouseButton.LeftButton)
    with qtbot.assertNotEmitted(dockable_item.dock_requested):
        dockable_item.set_dock_handler(lambda: True)
        qtbot.mouseDClick(dockable_item.pill, Qt.MouseButton.RightButton)


def test_tooltip_tells_how_to_dock(dockable_item, generic_item):
    dockable_item.set_indicator(ToolIndicator(summary="ok", tooltip="All good"))
    assert dockable_item.pill.toolTip() == "All good"  # no dock area yet
    dockable_item.set_dock_handler(lambda: True)
    assert dockable_item.pill.toolTip() == f"All good\n{dockable_item.DOCK_HINT}"
    assert "current dock area" in dockable_item.DOCK_HINT
    dockable_item.set_indicator(ToolIndicator(summary="ok", tooltip="Still good"))
    assert dockable_item.pill.toolTip() == f"Still good\n{dockable_item.DOCK_HINT}"
    generic_item.set_dock_handler(lambda: True)  # no DOCK_WIDGET: no hint
    generic_item.set_indicator(ToolIndicator(summary="ok", tooltip="Plain"))
    assert generic_item.pill.toolTip() == "Plain"


def test_hover_cleanup_can_run_twice(generic_item, recwarn):
    generic_item.hover.cleanup()
    generic_item.hover.cleanup()
    assert not [w for w in recwarn if "Failed to disconnect" in str(w.message)]


def test_late_enter_opens_no_card_for_a_hidden_or_cleaned_up_pill(generic_item, qtbot):
    from qtpy.QtCore import QPointF
    from qtpy.QtGui import QEnterEvent
    from qtpy.QtWidgets import QApplication

    item = generic_item

    def enter():
        point = QPointF(5, 5)
        QApplication.sendEvent(item.pill, QEnterEvent(point, point, point))

    enter()  # Qt can still deliver a queued Enter after the window was hidden or closed
    assert not item.card.isVisible()

    item.show()
    qtbot.waitExposed(item)
    enter()
    assert item.card.isVisible()
    item.close_card()

    item.hover.cleanup()
    enter()
    assert not item.card.isVisible()


@pytest.mark.parametrize(
    "indicator, expected",
    [
        (ToolIndicator(severity=ToolSeverity.OK), ("check_circle", "ok", False)),
        (ToolIndicator(severity=ToolSeverity.INFO), ("pending", "muted", False)),
        (ToolIndicator(severity=ToolSeverity.WARNING), ("warning", "warn", False)),
        (ToolIndicator(severity=ToolSeverity.CRITICAL), ("error", "bad", False)),
        (ToolIndicator(severity=ToolSeverity.INFO, active=True), ("sync", "primary", True)),
        (ToolIndicator(severity=ToolSeverity.OK, active=True), ("sync", "primary", True)),
        # an error wins over something that still runs
        (ToolIndicator(severity=ToolSeverity.CRITICAL, active=True), ("error", "bad", False)),
    ],
)
def test_indicator_maps_to_an_icon(indicator, expected):
    assert indicator_icon(indicator) == expected


class IconPill(StatusPillItem):
    PILL_STYLE = PillStyle.ICON

    def pill_text(self) -> str:
        return "BEC"


@pytest.fixture
def icon_item(qtbot, mocked_client, tmp_path):
    widget = create_widget(
        qtbot,
        IconPill,
        client=mocked_client,
        settings=lambda: QSettings(str(tmp_path / "icon.ini"), QSettings.Format.IniFormat),
        settings_prefix="icon_pill",
        card_content=QLabel("details"),
    )
    widget.apply_sizes()
    yield widget


def test_icon_pill_shows_icon_and_short_label_at_content_width(icon_item):
    pill = icon_item.pill
    assert isinstance(pill, StatusIconPill)
    icon_item.set_indicator(
        ToolIndicator(severity=ToolSeverity.CRITICAL, summary="Scan server: error", badge="1 down")
    )
    assert (pill.icon_name, pill.text) == ("error", "BEC")
    assert pill.accessibleName() == "Scan server: error"
    assert icon_item.badge_chip.text() == "1 down"
    narrow = pill.sizeHint().width()
    assert narrow < PILL_WIDTHS["compact"][0]  # much smaller than the smallest bar pill
    assert pill.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Fixed
    icon_item.set_large(True)
    assert pill.sizeHint().width() > narrow and pill.height() == 34


def test_icon_pill_has_no_width_modes(icon_item):
    assert icon_item.width_mode == "compact"
    icon_item.set_width_mode("fill")
    assert icon_item.width_mode == "compact"
    menu = icon_item.build_menu()
    assert [a.text() for a in menu.actions() if a.text()] == ["Large status bar"]
    menu.deleteLater()


def test_icon_pill_spins_only_while_active_and_shown(icon_item, qtbot):
    pill = icon_item.pill
    icon_item.set_indicator(ToolIndicator(severity=ToolSeverity.INFO, active=True))
    assert pill.spinning and not pill._spin_timer.isActive()  # not shown yet
    icon_item.show()
    qtbot.waitExposed(icon_item)
    assert pill._spin_timer.isActive()
    icon_item.hide()
    assert not pill._spin_timer.isActive()
    icon_item.show()
    assert pill._spin_timer.isActive()
    icon_item.set_indicator(ToolIndicator(severity=ToolSeverity.OK))
    assert not pill.spinning and not pill._spin_timer.isActive()


def test_icon_pill_paints_in_both_themes(icon_item):
    from bec_widgets.utils.colors import apply_theme

    icon_item.set_indicator(ToolIndicator(severity=ToolSeverity.OK))
    for theme in ("light", "dark"):
        apply_theme(theme)
        image = icon_item.pill.grab().toImage()
        assert not image.isNull() and image.width() == icon_item.pill.width()
    apply_theme("light")
