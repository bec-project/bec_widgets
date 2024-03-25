from qtpy.QtCore import Qt
from qtpy.QtWidgets import QTableWidget


class BECTable(QTableWidget):
    """Table widget with custom keyPressEvent to delete rows with backspace or delete key"""

    def keyPressEvent(self, event) -> None:
        """
        Delete selected rows with backspace or delete key
        Args:
            event: keyPressEvent
        """
        if event.key() in (Qt.Key_Backspace, Qt.Key_Delete):
            selected_ranges = self.selectedRanges()
            for selected_range in selected_ranges:
                for row in range(selected_range.topRow(), selected_range.bottomRow() + 1):
                    self.removeRow(row)
        else:
            super().keyPressEvent(event)
