"""Editable combobox for selecting a scan from history or live acquisition."""

from __future__ import annotations

from qtpy.QtCore import Slot
from qtpy.QtWidgets import QComboBox

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot

LIVE_ENTRY = "live"


class ScanIndexComboBox(BECWidget, QComboBox):
    """
    Editable combobox listing 'live' and the scan numbers available in the BEC scan
    history. Scan numbers are displayed as text while the corresponding scan IDs are
    stored as item data, so a selection maps to either live mode (scan_id is None)
    or a historical scan.

    Typing is not restricted: input that matches neither 'live' nor a listed scan
    number is flagged with a red border while editing, and reading scan_id or
    scan_number for such input raises ValueError. The default editable-combobox
    completer autocompletes against the listed entries while typing.
    """

    ICON_NAME = "history"
    RPC = False
    PLUGIN = True

    def __init__(
        self,
        parent=None,
        client=None,
        config: ConnectionConfig | None = None,
        gui_id: str | None = None,
        **kwargs,
    ):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)
        self._is_valid_input = False
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.currentTextChanged.connect(self.check_validity)
        self.refresh_scan_indices()

    @SafeSlot()
    def refresh_scan_indices(self):
        """Repopulate the combobox with 'live' and all scan numbers from the scan history."""
        # Unlike the scan_id property, tolerate invalid typed text here: a refresh
        # simply falls back to 'live' instead of raising.
        index = self.findText(self.currentText())
        current_scan_id = self.itemData(index) if index >= 0 else None
        self.clear()
        self.addItem(LIVE_ENTRY, None)

        # client.history is None until the client services are started (e.g. in Qt Designer)
        history = self.client.history
        scan_number_list = history._scan_numbers if history is not None else []
        scan_id_list = history._scan_ids if history is not None else []

        # Add items: show scan numbers, store scan IDs as item data,
        # ordered live -> latest scan -> oldest scan
        pairs = sorted(zip(scan_number_list, scan_id_list), key=lambda pair: pair[0], reverse=True)
        for num, sid in pairs:
            self.addItem(str(num), sid)

        self.set_scan_id(current_scan_id)
        # The current text may be unchanged while the item list changed, so no
        # currentTextChanged signal is emitted; re-check validity explicitly.
        self.check_validity(self.currentText())

    @property
    def is_valid_input(self) -> bool:
        """Whether the current text is 'live' or one of the listed scan numbers."""
        return self._is_valid_input

    @property
    def scan_id(self) -> str | None:
        """The scan ID of the selected scan, or None for 'live'.

        Raises:
            ValueError: If the current text is neither 'live' nor a listed scan number.
        """
        text = self.currentText()
        # Look up by text: typing into the editable combobox does not move the
        # current index, so currentData() could return a stale scan ID.
        index = self.findText(text)
        if index < 0:
            raise ValueError(
                f"'{text}' is not a valid scan selection; choose '{LIVE_ENTRY}' or one of the "
                "listed scan numbers."
            )
        return self.itemData(index)

    @property
    def scan_number(self) -> int | None:
        """The scan number of the selected scan, or None for 'live'.

        Raises:
            ValueError: If the current text is neither 'live' nor a listed scan number.
        """
        if self.scan_id is None:
            return None
        return int(self.currentText())

    @SafeSlot(str)
    @SafeSlot()
    def set_scan_id(self, scan_id: str | None = None):
        """
        Select the scan with the given scan ID, or 'live' if the scan ID is None or not found.

        Args:
            scan_id (str | None): The scan ID to select.
        """
        if scan_id is not None:
            for i in range(self.count()):
                if self.itemData(i) == scan_id:
                    self.setCurrentIndex(i)
                    return
        self.setCurrentText(LIVE_ENTRY)

    @Slot(str)
    def check_validity(self, input_text: str) -> None:
        """Validate the current text and update the visual state.

        Args:
            input_text: Current combobox text.
        """
        self._is_valid_input = bool(input_text) and self.findText(input_text) >= 0
        self._update_validity_style(self._is_valid_input)

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        super().setEnabled(enabled)
        self._update_validity_style(self._is_valid_input)

    def _update_validity_style(self, is_valid: bool) -> None:
        if is_valid or not self.isEnabled():
            self.setStyleSheet("")
            return
        self.setStyleSheet("QComboBox { border: 1px solid red; }")


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    combo = ScanIndexComboBox()
    combo.show()
    sys.exit(app.exec_())
