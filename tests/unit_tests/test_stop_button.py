# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

from unittest.mock import MagicMock, patch

import pytest

from bec_widgets.tests.client_mocks import mocked_client
from bec_widgets.widgets.control.buttons.stop_button.stop_button import StopAction, StopButton


@pytest.fixture
def stop_button(qtbot, mocked_client):
    widget = StopButton(client=mocked_client)
    widget.queue = MagicMock()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget, qtbot


def test_stop_button(stop_button):
    widget, qtbot = stop_button

    assert widget.button.text() == "Stop"

    widget.button.click()

    assert widget.queue.request_scan_abortion.called
    assert widget._emergency_stop_active is True
    qtbot.waitUntil(lambda: widget.button.text() == "Emergency Stop")

    qtbot.wait(widget.EMERGENCY_STOP_TIMEOUT_MS // 2)
    widget.button.click()

    assert widget.queue.request_scan_halt.called

    qtbot.wait((widget.EMERGENCY_STOP_TIMEOUT_MS // 2) + 100)
    assert widget.button.text() == "Emergency Stop"

    qtbot.wait((widget.EMERGENCY_STOP_TIMEOUT_MS // 2) + 100)
    assert widget.button.text() == "Stop"

    widget.close()


def test_stop_button_click_extends_emergency_timeout(stop_button):
    widget, qtbot = stop_button

    widget.button.click()
    qtbot.wait(500)

    widget.button.click()
    assert widget._emergency_stop_active is True
    qtbot.waitUntil(lambda: widget.button.text() == "Emergency Stop")

    qtbot.waitUntil(
        lambda: not widget._reset_timer.isActive(), timeout=widget.EMERGENCY_STOP_TIMEOUT_MS + 500
    )
    assert widget.button.text() == "Stop"
    widget.close()


def test_stop_button_menu_finish_and_halt(stop_button):
    widget, _qtbot = stop_button
    widget.request_id = "rid-7"
    widget.finish_action.trigger()
    widget.queue.request_set_completed.assert_called_once_with(request_id="rid-7")
    assert widget._emergency_stop_active is False
    widget.halt_action.trigger()
    widget.queue.request_scan_halt.assert_called_once_with(request_id="rid-7")
    widget.abort_action.trigger()
    widget.queue.request_scan_abortion.assert_called_once_with(request_id="rid-7")
    widget.close()


def test_a_failed_menu_action_does_not_escape(stop_button):
    widget, _ = stop_button
    with patch.object(widget, "perform", side_effect=RuntimeError("redis is gone")):
        widget.finish_action.trigger()
        widget.halt_action.trigger()
        widget.abort_action.trigger()


def test_stop_button_action_handler_can_take_over(stop_button):
    widget, _qtbot = stop_button
    seen = []
    widget.action_handler = lambda action: seen.append(action) or True
    widget.button.click()
    assert seen == [StopAction.ABORT]
    widget.queue.request_scan_abortion.assert_not_called()
    widget.close()


def test_rest_is_a_light_red_and_hover_fills_with_red(stop_button):
    from qtpy.QtCore import QEvent
    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.theme_utils import css, theme_colors

    widget, _qtbot = stop_button
    bad, on_fill = theme_colors()["bad"], theme_colors()["on_primary"]
    look = widget.style_colors()
    assert look["text"].rgb() == bad.rgb() and look["background"].alphaF() < 0.2
    assert look["hover_background"] == bad and look["hover_text"] == on_fill
    for part in (widget.button, widget.arrow):
        sheet = part.styleSheet()
        assert f"background: {css(look['background'])}" in sheet
        assert f":hover {{ background: {css(bad)}; border-color: {css(bad)};" in sheet
        assert f"color: {css(on_fill)}" in sheet.split(":hover")[1]
    assert widget.arrow.height() == widget.button.height()

    # the icons follow the text colour of the part under the cursor
    def icon_color():
        image = widget.button.icon().pixmap(widget.button.iconSize()).toImage()
        return image.pixelColor(image.width() // 2, image.height() // 2).rgb()

    rest = icon_color()
    QApplication.sendEvent(widget.button, QEvent(QEvent.Type.Enter))
    hovered = icon_color()
    QApplication.sendEvent(widget.button, QEvent(QEvent.Type.Leave))
    assert rest == bad.rgb() and hovered == on_fill.rgb()
    assert icon_color() == bad.rgb()

    widget.finish_action.trigger()
    widget.queue.request_set_completed.assert_called_once_with(request_id=None)
    widget.close()


def test_emergency_stop_is_a_dark_red_distinct_from_hover(stop_button):
    from bec_widgets.utils.theme_utils import theme_colors

    widget, _qtbot = stop_button
    hover = widget.style_colors()["hover_background"]
    widget.button.click()
    emergency = widget.style_colors()
    assert widget.button.text() == widget.EMERGENCY_STOP_LABEL
    assert emergency["background"].alpha() == 255
    assert emergency["background"].lightness() < hover.lightness()
    assert emergency["text"] == theme_colors()["on_primary"]
    assert "font-weight: bold" in widget.button.styleSheet()
    widget.close()


def test_divider_is_never_the_danger_colour(qtbot, mocked_client):
    from bec_widgets.utils.theme_utils import theme_colors

    widget = StopButton(client=mocked_client)
    qtbot.addWidget(widget)
    for emergency in (False, True):
        if emergency:
            widget._activate_emergency_stop()
        divider = widget.arrow.divider_color
        assert divider.rgb() != theme_colors()["bad"].rgb()
        assert divider.alphaF() < 0.5
    widget.close()


def test_required_width_covers_the_measured_label_with_slack(qtbot, mocked_client):
    widget = StopButton(client=mocked_client)
    qtbot.addWidget(widget)
    widget.set_size(height=40, font_px=20, pad=14)
    arrow = widget.arrow_width()
    needed = widget.label_width(widget.ABORT_LABEL) + widget.WIDTH_SLACK + arrow
    assert widget.required_width() >= needed
    assert widget.required_width() >= widget.button.sizeHint().width() + arrow
    widget.compact_emergency = True
    short = widget.label_width(widget.EMERGENCY_STOP_SHORT_LABEL, with_icon=False)
    assert widget.required_width() >= short + widget.WIDTH_SLACK + arrow
    widget.close()


def test_device_stop_has_no_menu_and_leaves_the_scan_alone(stop_button):
    widget, qtbot = stop_button
    assert not widget.device_stop and not widget.arrow.isHidden()
    with_menu = widget.required_width()

    widget.device_stop = True
    assert widget.arrow.isHidden()
    assert widget.required_width() == with_menu - max(widget.arrow.width(), widget.arrow_width())
    # a single button: rounded on both sides, not joined to an arrow
    sheet = widget.button.styleSheet()
    assert "border-right: none" not in sheet and "border-radius:" in sheet
    clicked = []
    widget.button.clicked.connect(lambda: clicked.append(True))
    widget.button.click()
    widget.button.click()
    assert clicked == [True, True]  # the host stops its devices on the click
    widget.queue.request_scan_abortion.assert_not_called()
    widget.queue.request_scan_halt.assert_not_called()
    assert widget.button.text() == widget.ABORT_LABEL  # no switch to Emergency Stop

    widget.device_stop = False
    assert not widget.arrow.isHidden() and "border-right: none" in widget.button.styleSheet()


def test_device_stop_ends_a_pending_emergency_stop(stop_button):
    widget, qtbot = stop_button
    widget.button.click()
    assert widget.button.text() == widget.EMERGENCY_STOP_LABEL
    widget.device_stop = True
    assert widget.button.text() == widget.ABORT_LABEL


def test_toolbar_device_stop_drops_its_menu(qtbot, mocked_client):
    widget = StopButton(client=mocked_client, toolbar=True)
    qtbot.addWidget(widget)
    assert widget.button.menu() is widget.menu
    widget.device_stop = True
    assert widget.button.menu() is None and widget.arrow.isHidden()
    widget.close()
