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
    assert item.pill.toolTip() == f"x\n{item.EXPAND_HINT}"
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


def _press_in_window(item, global_pos, button=Qt.MouseButton.LeftButton):
    """A mouse press as the platform delivers it: to the window, before any widget."""
    from qtpy.QtCore import QEvent, QPointF
    from qtpy.QtGui import QMouseEvent
    from qtpy.QtWidgets import QApplication

    window = item.window().windowHandle()
    local = QPointF(window.mapFromGlobal(global_pos))
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        local,
        QPointF(global_pos),
        button,
        button,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(window, event)


def test_click_opens_and_closes_the_card_and_hover_only_outlines(generic_item, qtbot, monkeypatch):
    from qtpy.QtCore import QPoint, QPointF
    from qtpy.QtGui import QEnterEvent
    from qtpy.QtWidgets import QApplication

    item = generic_item
    item.show()
    qtbot.waitExposed(item)
    inside = item.pill.mapToGlobal(QPoint(5, 5))
    _cursor_at(monkeypatch, inside)
    point = QPointF(5, 5)
    QApplication.sendEvent(item.pill, QEnterEvent(point, point, QPointF(inside)))
    qtbot.wait(item.GRACE_MS + 150)
    assert item.pill.hovered and not item.card.isVisible()  # hover alone opens nothing
    assert not item._poll.isActive()

    qtbot.mouseClick(item.pill, Qt.MouseButton.LeftButton)
    assert item.card.isVisible() and item.pill.expanded and item.pill.outlined
    _cursor_at(monkeypatch, QPoint(-5000, -5000))
    qtbot.wait(item.GRACE_MS + 150)
    assert item.card.isVisible()  # the cursor leaving does not close it

    _cursor_at(monkeypatch, inside)
    qtbot.mouseClick(item.pill, Qt.MouseButton.LeftButton)  # a second click closes it
    assert not item.card.isVisible() and not item.pill.expanded
    assert item.pill.hovered  # the cursor is still on the pill

    qtbot.mouseClick(item.pill, Qt.MouseButton.RightButton)
    assert not item.card.isVisible()  # the right button is for the settings menu


def test_click_elsewhere_or_esc_closes_the_card_but_not_on_a_trailing_widget(
    generic_item, qtbot, monkeypatch
):
    from qtpy.QtCore import QEvent, QPoint
    from qtpy.QtGui import QKeyEvent
    from qtpy.QtWidgets import QApplication, QPushButton

    item = generic_item
    stop = QPushButton("Stop", item)
    item.add_trailing(stop, reveal=False)
    other = QPushButton("Elsewhere", item)
    item.row.addWidget(other)
    item.show()
    qtbot.waitExposed(item)
    _cursor_at(monkeypatch, QPoint(-5000, -5000))

    _press_in_window(item, item.pill.mapToGlobal(QPoint(5, 5)))
    assert item.card.isVisible()  # the window passes the press on to the pill: it opens
    _press_in_window(item, stop.mapToGlobal(stop.rect().center()))
    assert item.card.isVisible()  # the Stop next to the pill keeps it
    _press_in_window(item, item.pill.mapToGlobal(QPoint(5, 5)))
    assert not item.card.isVisible()  # a second press on the pill closes it

    item.open_card()
    _press_in_window(item, other.mapToGlobal(other.rect().center()))
    assert not item.card.isVisible()  # anywhere else in the window closes it

    item.open_card()
    window = item.window().windowHandle()
    esc = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(window, esc)
    assert not item.card.isVisible()
    assert item.hover._click_window is None  # stops watching the window once closed

    _press_in_window(item, other.mapToGlobal(other.rect().center()))  # nothing open: no effect
    assert not item.card.isVisible()


def test_resizing_the_window_closes_the_card_and_moving_it_takes_it_along(
    generic_item, qtbot, monkeypatch
):
    from qtpy.QtCore import QPoint
    from qtpy.QtGui import QResizeEvent
    from qtpy.QtWidgets import QApplication

    item = generic_item
    item.show()
    qtbot.waitExposed(item)
    _cursor_at(monkeypatch, QPoint(-5000, -5000))
    window = item.window().windowHandle()

    item.open_card()
    size = window.size()
    QApplication.sendEvent(window, QResizeEvent(size, size))
    assert item.card.isVisible()  # Qt sends Resize without a change, e.g. on expose

    item.resize(item.width() + 40, item.height())
    qtbot.waitUntil(lambda: not item.card.isVisible(), timeout=2000)
    assert not item.pill.expanded

    item.open_card()
    before = item.card.pos()
    item.move(item.pos() + QPoint(30, 0))
    qtbot.waitUntil(lambda: item.card.pos() == before + QPoint(30, 0), timeout=2000)
    assert item.card.isVisible()  # dragged: the card goes with the pill
    item.close_card()


def test_card_stays_open_while_a_dialog_of_its_content_is_open(generic_item, qtbot, monkeypatch):
    from qtpy.QtCore import QPoint, Qt
    from qtpy.QtWidgets import QDialog

    item = generic_item
    item.show()
    qtbot.waitExposed(item)
    _cursor_at(monkeypatch, QPoint(-5000, -5000))
    item.open_card()
    dialog = QDialog(item.card.content)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.show()
    dialog.activateWindow()
    qtbot.waitUntil(dialog.isActiveWindow)
    qtbot.wait(20)
    assert item.card.isVisible()  # the dialog took the focus, but it belongs to the card
    elsewhere = item.mapToGlobal(QPoint(item.width() - 2, item.height() // 2))
    _press_in_window(item, elsewhere)
    assert item.card.isVisible()  # e.g. a restart confirmation of the status box

    dialog.close()
    assert item.card.isVisible()
    _press_in_window(item, elsewhere)
    assert not item.card.isVisible()
    dialog.deleteLater()


def test_another_window_taking_the_focus_closes_the_card(generic_item, qtbot, monkeypatch):
    from qtpy.QtCore import QPoint
    from qtpy.QtWidgets import QWidget

    item = generic_item
    item.show()
    item.activateWindow()
    qtbot.waitUntil(item.isActiveWindow)
    _cursor_at(monkeypatch, QPoint(-5000, -5000))
    item.open_card()
    qtbot.wait(20)
    assert item.card.isVisible()

    other = QWidget()  # e.g. a floating dock or a second window of the app
    qtbot.addWidget(other)
    other.show()
    other.activateWindow()
    qtbot.waitUntil(other.isActiveWindow)
    qtbot.waitUntil(lambda: not item.card.isVisible(), timeout=2000)
    other.close()


def test_esc_closes_the_card_before_a_shortcut_of_the_focused_widget(generic_item, qtbot):
    from qtpy.QtGui import QKeySequence, QShortcut
    from qtpy.QtTest import QTest
    from qtpy.QtWidgets import QLineEdit

    item = generic_item
    edit = QLineEdit(item)
    item.row.addWidget(edit)
    fired = []
    shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), edit)
    shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)  # as in the Log Panel
    shortcut.activated.connect(lambda: fired.append(True))
    item.show()
    qtbot.waitExposed(item)
    window = item.window().windowHandle()

    def focus_edit():  # offscreen hands the focus to a shown card, real platforms do not
        item.activateWindow()
        qtbot.waitUntil(item.isActiveWindow)
        edit.setFocus()
        qtbot.waitUntil(edit.hasFocus)

    item.open_card()
    focus_edit()
    assert item.card.isVisible()
    QTest.keyClick(window, Qt.Key.Key_Escape)
    assert not item.card.isVisible()
    assert not fired  # the open card takes the Esc
    focus_edit()
    QTest.keyClick(window, Qt.Key.Key_Escape)
    assert fired  # with the card closed the shortcut works again


def test_a_click_just_outside_the_pill_closes_the_card(generic_item, qtbot, monkeypatch):
    from qtpy.QtCore import QPoint

    item = generic_item
    item.show()
    qtbot.waitExposed(item)
    _cursor_at(monkeypatch, QPoint(-5000, -5000))
    pill = item.pill
    just_outside = pill.mapToGlobal(QPoint(pill.width() + 1, pill.height() // 2))
    assert item.rect().contains(item.mapFromGlobal(just_outside))

    item.open_card()
    _cursor_at(monkeypatch, just_outside)
    _press_in_window(item, just_outside)
    assert not item.card.isVisible()  # hit testing uses the real bounds, not the hover margin
    assert not item.pill.outlined  # no Leave comes from out there, so no outline is left on


def test_space_or_enter_toggles_the_card_and_tab_only_outlines(generic_item, qtbot, monkeypatch):
    from qtpy.QtCore import QEvent, QPoint
    from qtpy.QtGui import QFocusEvent, QKeyEvent
    from qtpy.QtWidgets import QApplication

    item = generic_item
    item.show()
    qtbot.waitExposed(item)
    _cursor_at(monkeypatch, QPoint(-5000, -5000))
    QApplication.sendEvent(
        item.pill, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason)
    )
    assert item.pill.keyboard_focus and item.pill.outlined
    assert not item.card.isVisible()
    qtbot.keyClick(item.pill, Qt.Key.Key_Space)
    assert item.card.isVisible()
    qtbot.keyClick(item.pill, Qt.Key.Key_Return)
    assert not item.card.isVisible()

    for key in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
        qtbot.keyPress(item.pill, key)
        for _ in range(3):  # holding the key: auto-repeat presses do not toggle again
            repeat = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier, "", True)
            QApplication.sendEvent(item.pill, repeat)
        assert item.card.isVisible()
        qtbot.keyClick(item.pill, key)
        assert not item.card.isVisible()


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
    expand = dockable_item.EXPAND_HINT
    assert hint.isHidden() and dockable_item.pill.accessibleDescription() == expand
    available[0] = True
    dockable_item._prepare_card()  # asked again each time the card opens
    assert not hint.isHidden()
    assert hint.text() == dockable_item.DOCK_HINT
    assert dockable_item.pill.accessibleDescription() == f"{expand}\n{dockable_item.DOCK_HINT}"
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


def test_tooltip_tells_how_to_expand_and_dock(dockable_item, generic_item):
    expand, dock = dockable_item.EXPAND_HINT, dockable_item.DOCK_HINT
    assert expand == "Click to expand" and "current dock area" in dock
    dockable_item.set_indicator(ToolIndicator(summary="ok", tooltip="All good"))
    assert dockable_item.pill.toolTip() == f"All good\n{expand}"  # no dock area yet
    dockable_item.set_dock_handler(lambda: True)
    assert dockable_item.pill.toolTip() == f"All good\n{expand}\n{dock}"
    dockable_item.set_indicator(ToolIndicator(summary="ok", tooltip="Still good"))
    assert dockable_item.pill.toolTip() == f"Still good\n{expand}\n{dock}"
    generic_item.set_dock_handler(lambda: True)  # no DOCK_WIDGET: no dock hint
    generic_item.set_indicator(ToolIndicator(summary="ok", tooltip="Plain"))
    assert generic_item.pill.toolTip() == f"Plain\n{expand}"
    generic_item.set_indicator(ToolIndicator(summary="ok"))
    assert generic_item.pill.toolTip() == expand


def test_no_tooltip_over_an_open_card(generic_item, qtbot, monkeypatch):
    from qtpy.QtCore import QEvent, QPoint
    from qtpy.QtGui import QHelpEvent

    item = generic_item
    item.show()
    qtbot.waitExposed(item)
    _cursor_at(monkeypatch, QPoint(-5000, -5000))

    def tooltip_shown() -> bool:
        event = QHelpEvent(QEvent.Type.ToolTip, QPoint(5, 5), item.pill.mapToGlobal(QPoint(5, 5)))
        item.pill.event(event)
        return event.isAccepted()

    assert tooltip_shown()
    item.open_card()
    assert not tooltip_shown()
    item.close_card()
    assert tooltip_shown()


def test_tooltip_survives_a_resize_of_the_pill(generic_item, qtbot):
    """The bar's own cut-label tooltip used to replace the pill's tooltip on every resize."""
    item = generic_item
    item.set_indicator(ToolIndicator(summary="ok", tooltip="All good"))
    item.show()
    qtbot.waitExposed(item)
    item.set_width_mode("wide")
    assert item.pill.toolTip() == f"All good\n{item.EXPAND_HINT}"
    long = "A very long label that does not fit into the compact pill at all"
    item.set_indicator(ToolIndicator(summary=long, tooltip="All good"))
    item.set_width_mode("compact")
    assert item.pill.toolTip() == f"{long}\nAll good\n{item.EXPAND_HINT}"


def test_hover_cleanup_can_run_twice(generic_item, recwarn):
    generic_item.hover.cleanup()
    generic_item.hover.cleanup()
    assert not [w for w in recwarn if "Failed to disconnect" in str(w.message)]


def test_late_enter_does_not_outline_a_hidden_pill_and_cleanup_stops_clicks(generic_item, qtbot):
    from qtpy.QtCore import QPointF
    from qtpy.QtGui import QEnterEvent
    from qtpy.QtWidgets import QApplication

    item = generic_item
    point = QPointF(5, 5)
    # Qt can still deliver a queued Enter after the window was hidden or closed
    QApplication.sendEvent(item.pill, QEnterEvent(point, point, point))
    assert not item.pill.hovered and not item.card.isVisible()

    item.show()
    qtbot.waitExposed(item)
    item.open_card()
    window = item.hover._click_window
    assert window is item.window().windowHandle()
    item.hover.cleanup()
    assert item.hover._click_window is None and not item.card.isVisible()
    qtbot.mouseClick(item.pill, Qt.MouseButton.LeftButton)
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
