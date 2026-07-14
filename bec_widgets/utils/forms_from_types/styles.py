from bec_qthemes.qss_editor.qss_editor import (
    THEMES_PATH,
    build_palette_from_mapping,
    read_theme_xml,
)


def pretty_display_theme(theme: str = "dark"):
    _, mapping = read_theme_xml(THEMES_PATH / f"{theme}.xml")
    palette = build_palette_from_mapping(mapping)
    foreground = palette.text().color().name()
    background = palette.base().color().name()
    border = palette.shadow().color().name()
    # palette.highlight() rather than accent(): on Qt 6.10+ accent() returns the
    # platform accent, and bec_qthemes palettes only set Highlight anyway.
    accent = palette.highlight().color().name()
    return f"""
QWidget {{color: {foreground}; background-color: {background}}}
QLabel {{ font-weight: bold; }}
QLineEdit,QLabel,QTreeView {{ border-style: solid; border-width: 2px; border-color: {border} }}
QRadioButton {{ color: {foreground}; }}
QRadioButton::indicator::checked {{ color: {accent}; }}
QCheckBox {{ color: {accent}; }}
"""


if __name__ == "__main__":
    print(pretty_display_theme())
