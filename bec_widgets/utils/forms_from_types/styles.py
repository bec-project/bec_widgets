import bec_qthemes


def pretty_display_theme(theme: str = "dark"):
    palette = bec_qthemes.load_palette(theme)
    foreground = palette.text().color().name()
    background = palette.base().color().name()
    border = palette.shadow().color().name()
    accent = palette.accent().color().name()
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
