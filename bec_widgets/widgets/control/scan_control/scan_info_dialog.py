"""Reusable dialog for displaying styled scan documentation."""

from qtpy.QtGui import QPalette
from qtpy.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout, QWidget

from bec_widgets.widgets.control.scan_control.scan_docstring import render_scan_docstring_html


class ScanInfoDialog(QDialog):
    """Modeless, theme-aware viewer for a scan docstring."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setModal(False)
        self.resize(640, 480)

        layout = QVBoxLayout(self)
        self.text_browser = QTextBrowser(self)
        self.text_browser.setReadOnly(True)
        self.text_browser.setOpenExternalLinks(False)
        layout.addWidget(self.text_browser)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

    def _update_style(self) -> None:
        palette = self.text_browser.palette()
        accent = palette.color(QPalette.ColorRole.Link).name()
        muted = palette.color(QPalette.ColorRole.PlaceholderText).name()
        alternate_base = palette.color(QPalette.ColorRole.AlternateBase).name()
        self.text_browser.document().setDefaultStyleSheet(f"""
            h1 {{ color: {accent}; margin-bottom: 12px; }}
            h2 {{ color: {accent}; margin-top: 18px; margin-bottom: 6px; }}
            small {{ color: {muted}; }}
            table {{ margin-left: 2px; }}
            td {{ padding: 3px 8px 3px 0; }}
            pre {{
                background-color: {alternate_base};
                padding: 8px;
                margin: 4px 0;
                white-space: pre-wrap;
            }}
            """)

    def show_scan(self, scan_name: str, docstring: str | None) -> None:
        """Render and show documentation for ``scan_name``."""
        self.setWindowTitle(f"Scan information: {scan_name}")
        self._update_style()
        self.text_browser.setHtml(render_scan_docstring_html(scan_name, docstring))
        self.show()
        self.raise_()
        self.activateWindow()
