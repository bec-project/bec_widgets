"""Tests for the shared BEC UI kit: tokens, QML host and the QWidget controls."""

# pylint: disable=redefined-outer-name

from pathlib import Path

import pytest
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QColor
from qtpy.QtQuickWidgets import QQuickWidget
from qtpy.QtWidgets import QLineEdit, QWidget

from bec_widgets.examples.ui_kit_gallery.ui_kit_gallery import QML_GALLERY, QWidgetGallery
from bec_widgets.tests.utils import create_widget
from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.quick import (
    QML_IMPORT_PATH,
    MaterialIconProvider,
    QmlTheme,
    ThemeTokens,
    create_quick_widget,
    quick_theme,
    release_quick_widget,
)
from bec_widgets.utils.quick.tokens import FALLBACK_PALETTES
from bec_widgets.utils.ux_kit import (
    Badge,
    Banner,
    Card,
    FormField,
    IconButton,
    LinearProgress,
    SearchField,
    SegmentedControl,
    Spinner,
    StatusPill,
    TextButton,
    refresh_kit_theme,
)

BEC_UI = QML_IMPORT_PATH / "BecUi"


@pytest.fixture
def dark_theme():
    apply_theme("dark")
    yield
    apply_theme("light")


def test_fallback_palettes_match_bec_qthemes():
    from bec_qthemes._main import read_theme_xml
    from bec_qthemes.qss_editor.qss_editor import THEMES_PATH

    for name, palette in FALLBACK_PALETTES.items():
        _, mapping = read_theme_xml(THEMES_PATH / f"{name}.xml")
        for key, value in palette.items():
            assert QColor(mapping[key]) == QColor(value), (name, key)


def test_tokens_follow_application_theme(dark_theme):
    dark = ThemeTokens()
    assert dark.name == "dark" and dark.dark
    apply_theme("light")
    light = ThemeTokens()
    assert light.name == "light" and not light.dark
    assert light.card != dark.card
    assert ThemeTokens.current().card == light.card


@pytest.mark.parametrize(
    "alias, canonical",
    [
        ("ok", "success"),
        ("warn", "warning"),
        ("err", "danger"),
        ("busy", "info"),
        ("stale", "subtle"),
    ],
)
def test_tone_aliases(alias, canonical):
    tokens = ThemeTokens()
    assert tokens.tone(alias) == tokens.tone(canonical)
    assert tokens.tone_text(alias) == tokens.tone_text(canonical)
    assert tokens.tone_tint(alias) == tokens.tone_tint(canonical)


def test_light_warning_text_is_darker_than_accent():
    tokens = ThemeTokens()
    assert tokens.warning_text.lightnessF() < tokens.warning.lightnessF()


def test_qml_theme_aliases_match_canonical_names(dark_theme):
    theme = QmlTheme()
    pairs = [
        ("muted", "fgMuted"),
        ("faint", "fgSubtle"),
        ("text", "fg"),
        ("foreground", "fg"),
        ("background", "bg"),
        ("busy", "info"),
        ("ok", "success"),
        ("warn", "warning"),
        ("err", "danger"),
        ("emergency", "danger"),
        ("errText", "dangerText"),
        ("okTint", "successTint"),
        ("window", "bg"),
        ("base", "field"),
        ("button", "card"),
        ("onAccent", "onPrimary"),
    ]
    for alias, canonical in pairs:
        assert theme.property(alias) == theme.property(canonical), alias
    assert theme.property("isDark") is True
    assert theme.property("radiusLarge") == 10
    assert theme.toneText("warn") == theme.property("warningText")
    assert QColor(theme.property("c")["CARD_BG"]) == theme.property("card")


def test_qml_theme_emits_changed_on_theme_switch(qtbot):
    theme = quick_theme()
    with qtbot.waitSignal(theme.changed):
        apply_theme("dark")
    assert theme.property("dark") is True
    apply_theme("light")
    assert theme.property("dark") is False


@pytest.mark.parametrize("color", ["%23ff0000", "ff0000", "red"])
def test_icon_provider_accepts_colour_forms(color):
    provider = MaterialIconProvider()
    size = QSize()
    pixmap = provider.requestPixmap(f"check?color={color}&filled=1", size, QSize(20, 20))
    assert not pixmap.isNull()
    assert size.width() == pixmap.width()


def test_icon_provider_unknown_icon_returns_empty_pixmap():
    provider = MaterialIconProvider()
    assert provider.requestPixmap("no_such_icon_xyz", QSize(), QSize(20, 20)).isNull()


def test_qmldir_lists_every_control():
    listed = {
        line.split()[0]
        for line in (BEC_UI / "qmldir").read_text().splitlines()
        if line and not line.startswith("module")
    }
    files = {path.stem for path in BEC_UI.glob("*.qml")}
    assert listed == files


def test_gallery_loads_every_control_without_errors(qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    view = create_quick_widget(host, QML_GALLERY, raise_on_error=True)
    assert view.status() == QQuickWidget.Status.Ready
    source = QML_GALLERY.read_text()
    for path in BEC_UI.glob("*.qml"):
        if path.stem in ("FieldFrame", "Icon"):  # used inside every other control
            continue
        assert f"{path.stem} {{" in source, f"{path.stem} missing from the gallery"
    release_quick_widget(view)


def test_create_quick_widget_with_context_uses_own_engine(qtbot, tmp_path: Path):
    qml = tmp_path / "View.qml"
    qml.write_text(
        "import QtQuick\nimport BecUi\nRectangle { color: theme.card; "
        "property string label: backend.objectName; StatusPill { text: 'x'; tone: 'ok' } }\n"
    )
    host = QWidget()
    qtbot.addWidget(host)
    backend = QWidget()
    backend.setObjectName("demo")
    view = create_quick_widget(host, qml, context={"backend": backend}, raise_on_error=True)
    assert view.rootObject().property("label") == "demo"
    shared = create_quick_widget(host, qml.with_name("Plain.qml"), raise_on_error=False)
    assert view.engine() is not shared.engine()
    release_quick_widget(view)
    release_quick_widget(shared)
    backend.deleteLater()


def test_create_quick_widget_raises_on_error(qtbot, tmp_path: Path):
    qml = tmp_path / "Broken.qml"
    qml.write_text("import QtQuick\nRectangle { nonsense: }\n")
    host = QWidget()
    qtbot.addWidget(host)
    with pytest.raises(RuntimeError):
        create_quick_widget(host, qml, raise_on_error=True)


def test_qwidget_gallery_builds(qtbot):
    gallery = create_widget(qtbot, QWidgetGallery)
    assert gallery.findChildren(Card)
    for spinner in gallery.findChildren(Spinner):
        spinner.cleanup()
    for button in gallery.findChildren(TextButton):
        button.set_busy(False)
    for bar in gallery.findChildren(LinearProgress):
        bar.cleanup()


def test_controls_follow_theme_switch(qtbot):
    card = create_widget(qtbot, Card, "Title")
    light_qss = card.styleSheet()
    apply_theme("dark")
    try:
        assert card.styleSheet() != light_qss
        assert ThemeTokens.current().card.name() in card.styleSheet()
    finally:
        apply_theme("light")


def test_refresh_kit_theme_reaches_children(qtbot):
    card = create_widget(qtbot, Card, "Title")
    button = TextButton("Go", "primary", parent=card)
    card.body.addWidget(button)
    button.setStyleSheet("")
    refresh_kit_theme(card)
    assert "QPushButton" in button.styleSheet()


def test_text_button_busy_and_variants(qtbot):
    button = create_widget(qtbot, TextButton, "Submit", "primary")
    button.set_busy(True)
    assert button.busy
    button.set_busy(False)
    for variant in ("danger", "success", "neutral", "dangerOutline", "ghost"):
        button.set_variant(variant)
        assert "QPushButton" in button.styleSheet()


def test_icon_button_danger_and_checked(qtbot):
    button = create_widget(qtbot, IconButton, "delete", "Remove", danger=True)
    assert button.accessibleName() == "Remove"
    button.setCheckable(True)
    button.setChecked(True)
    assert not button.icon().isNull()


def test_status_pill_named_and_colour_tones(qtbot):
    pill = create_widget(qtbot, StatusPill, text="Running", tone="busy", pulse=True)
    assert pill.pulsing
    pill.set_status("Failed", QColor("red"), icon_name="error")
    assert not pill.pulsing
    assert pill.text == "Failed"
    assert pill.sizeHint().width() > 30
    pill.cleanup()


def test_badge_label_and_visibility(qtbot):
    badge = create_widget(qtbot, Badge, count=150)
    assert badge.label == "99+"
    badge.set_count(0)
    assert not badge.isVisible()


def test_linear_progress_clamps(qtbot):
    bar = create_widget(qtbot, LinearProgress)
    bar.set_value(1.5, animate=False)
    assert bar.value == 1.0
    bar.set_indeterminate(True)
    bar.set_indeterminate(False)
    bar.cleanup()


def test_banner_close_and_action(qtbot):
    banner = create_widget(
        qtbot, Banner, "err", "Title", "Text", action_text="Retry", closable=True
    )
    with qtbot.waitSignal(banner.action_triggered):
        qtbot.mouseClick(banner.action_button, Qt.MouseButton.LeftButton)
    with qtbot.waitSignal(banner.closed):
        qtbot.mouseClick(banner.close_button, Qt.MouseButton.LeftButton)
    assert not banner.isVisible()


def test_form_field_error_marks_control_invalid(qtbot):
    edit = QLineEdit()
    field = create_widget(qtbot, FormField, "Steps", edit, required=True, helper="At least 2")
    assert field.message.text() == "At least 2"
    field.set_error("Must be at least 2")
    assert edit.property("invalid") is True
    assert field.message.text() == "Must be at least 2"
    field.set_error("")
    assert edit.property("invalid") is False
    assert field.message.text() == "At least 2"


def test_search_field_escape_clears(qtbot):
    field = create_widget(qtbot, SearchField, shortcut_hint="Ctrl K")
    field.setText("samx")
    with qtbot.waitSignal(field.cleared):
        qtbot.keyClick(field, Qt.Key.Key_Escape)
    assert field.text() == ""


def test_segmented_control_emits_on_click_only(qtbot):
    control = create_widget(qtbot, SegmentedControl, ["All", {"text": "Errors", "count": 2}])
    control.set_current_index(1)
    assert control.current_index == 1
    with qtbot.waitSignal(control.activated) as blocker:
        qtbot.mouseClick(control._buttons[0], Qt.MouseButton.LeftButton)
    assert blocker.args == [0]
    control.set_count(1, 5)
    assert "5" in control._buttons[1].text()


def test_collapsible_card_toggles_body(qtbot):
    card = create_widget(qtbot, Card, "Section", collapsible=True, title_style="caption")
    assert card.title_label.text() == "SECTION"
    card.set_expanded(False)
    assert card.body_widget.isHidden()
    card.set_expanded(True)
    assert not card.body_widget.isHidden()
