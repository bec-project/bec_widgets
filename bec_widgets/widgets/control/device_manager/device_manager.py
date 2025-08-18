from __future__ import annotations

from qtpy.QtCore import QSize, QSortFilterProxyModel, Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from thefuzz import fuzz

from bec_widgets.utils.bec_table import BECTable
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import ErrorPopupUtility, SafeSlot
from bec_widgets.widgets.utility.toggle.toggle import ToggleSwitch


class CheckBoxCenterWidget(QWidget):
    """Widget to center a checkbox in a table cell."""

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(4, 0, 4, 0)  # Reduced margins for more compact layout

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(checked)
        self.checkbox.setEnabled(False)  # Read-only

        # Store the value for sorting
        self.value = checked

        layout.addWidget(self.checkbox)


class TextLabelWidget(QWidget):
    """Widget to display text with word wrapping in a table cell."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        # Use a layout with minimal margins to maximize text display area
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        # Create label with word wrap enabled
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop)  # Align to top-left

        # Make sure label expands to fill available space
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Store the text value for sorting
        self.value = text

        layout.addWidget(self.label)

        # Make sure the widget itself uses an expanding size policy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)

        # Ensure we have a reasonable height to start with
        # This helps ensure text is visible before resizing calculations
        min_height = 40 if text else 20
        self.setMinimumHeight(min_height)

    def setText(self, text):
        """Set the text of the label."""
        self.label.setText(text)
        self.value = text
        # Trigger layout update
        self.updateGeometry()

    def sizeHint(self):
        """Provide a size hint based on the text content."""
        # Get the width of our container (usually the table cell)
        width = self.width() or 300

        # If text is empty, return minimal size
        if not self.value:
            return QSize(width, 20)

        # Calculate height for wrapped text
        font_metrics = self.label.fontMetrics()

        # Estimate how much space the text will need when wrapped
        text_rect = font_metrics.boundingRect(
            0,
            0,
            width - 10,
            1000,  # Width constraint, virtually unlimited height
            Qt.TextWordWrap,
            self.value,
        )

        # Add some padding
        height = text_rect.height() + 8

        return QSize(width, max(30, height))

    def resizeEvent(self, event):
        """Handle resize events to ensure text is properly displayed."""
        super().resizeEvent(event)

        # When resized (especially width change), update layout to ensure text wrapping works
        self.label.updateGeometry()
        self.updateGeometry()


class SortableTableWidgetItem(QTableWidgetItem):
    """Table widget item that enables proper sorting for different data types."""

    def __lt__(self, other):
        """Compare items for sorting."""
        if self.text() == "Yes" and other.text() == "No":
            return True
        elif self.text() == "No" and other.text() == "Yes":
            return False
        else:
            return self.text().lower() < other.text().lower()


class DeviceTagsWidget(BECWidget, QWidget):
    """Widget to display devices grouped by their tags in containers."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        # Title
        self.title_label = QLabel("Device Tags")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.layout.addWidget(self.title_label)

        # Search bar for tags
        self.search_layout = QHBoxLayout()
        self.search_label = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter tags...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.filter_tags)
        self.search_layout.addWidget(self.search_label)
        self.search_layout.addWidget(self.search_input)
        self.layout.addLayout(self.search_layout)

        # Create a scroll area for tag containers
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Create a widget to hold all tag containers
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setSpacing(10)
        self.scroll_layout.setContentsMargins(5, 5, 5, 5)
        self.scroll_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.scroll_widget)
        self.layout.addWidget(self.scroll_area)

        # Initialize with empty data
        self.all_devices = []
        self.active_devices = []
        self.device_tags = {}  # Maps tag names to lists of device names
        self.tag_containers = {}  # Maps tag names to their container widgets

        # Load initial data
        self.update_tags()

    def update_tags(self):
        """Update the tags containers with current device information."""
        try:
            # Get device config
            config = self.client.device_manager._get_redis_device_config()

            # Clear current data
            self.all_devices = []
            self.active_devices = []
            self.device_tags = {}

            # Process device config
            for device_info in config:
                device_name = device_info.get("name", "Unknown")
                self.all_devices.append(device_name)

                # Add to active devices if enabled
                if device_info.get("enabled", False):
                    self.active_devices.append(device_name)

                # Process device tags
                tags = device_info.get("deviceTags", [])
                for tag in tags:
                    if tag not in self.device_tags:
                        self.device_tags[tag] = []
                    self.device_tags[tag].append(device_name)

            # Update the tag containers
            self.populate_tag_containers()

        except Exception as e:
            ErrorPopupUtility().show_error_message(
                "Device Tags Error", f"Error updating device tags: {str(e)}", self
            )

    def populate_tag_containers(self):
        """Populate the containers with current tag and device data."""
        # Save current filter before clearing
        current_filter = self.search_input.text() if hasattr(self, "search_input") else ""

        # Clear existing containers
        for i in reversed(range(self.scroll_layout.count())):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        self.tag_containers = {}

        # Add tag containers
        for tag, devices in sorted(self.device_tags.items()):
            # Create container frame for this tag
            container = QFrame()
            container.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
            container.setStyleSheet(
                "QFrame { background-color: palette(window); border: 1px solid palette(mid); border-radius: 4px; }"
            )

            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(10, 10, 10, 10)

            # Add tag header with status indicator
            header_layout = QHBoxLayout()

            # Tag name label
            tag_label = QLabel(tag)
            tag_label.setStyleSheet("font-weight: bold;")
            header_layout.addWidget(tag_label)

            # Spacer to push status to the right
            header_layout.addStretch()

            # Status indicator
            all_devices_count = len(devices)
            active_devices_count = sum(1 for d in devices if d in self.active_devices)

            if active_devices_count == 0:
                status_text = "None"
                status_color = "red"
            elif active_devices_count == all_devices_count:
                status_text = "All"
                status_color = "green"
            else:
                status_text = f"{active_devices_count}/{all_devices_count}"
                status_color = "orange"

            status_label = QLabel(status_text)
            status_label.setStyleSheet(f"color: {status_color}; font-weight: bold;")
            header_layout.addWidget(status_label)

            container_layout.addLayout(header_layout)

            # Add divider line
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setFrameShadow(QFrame.Sunken)
            container_layout.addWidget(line)

            # Add device list
            device_list = QListWidget()
            device_list.setAlternatingRowColors(True)
            device_list.setMaximumHeight(150)  # Limit height

            # Add devices to the list
            for device_name in sorted(devices):
                item = QListWidgetItem(device_name)
                if device_name in self.active_devices:
                    item.setForeground(Qt.green)
                else:
                    item.setForeground(Qt.red)
                device_list.addItem(item)

            container_layout.addWidget(device_list)

            # Add to the scroll layout
            self.scroll_layout.addWidget(container)
            self.tag_containers[tag] = container

        # Add a stretch at the end to push all containers to the top
        self.scroll_layout.addStretch()

        # Reapply filter if there was one
        if current_filter:
            self.filter_tags(current_filter)

    @SafeSlot(str)
    def filter_tags(self, text):
        """Filter the tag containers based on search text."""
        if not hasattr(self, "tag_containers"):
            return

        text = text.lower()

        # Show/hide tag containers based on filter
        for tag, container in self.tag_containers.items():
            if not text or text in tag.lower():
                # Tag matches filter
                container.show()
            else:
                # Check if any device in this tag matches
                matches = False
                for device in self.device_tags.get(tag, []):
                    if text in device.lower():
                        matches = True
                        break

                container.setVisible(matches)

    @SafeSlot()
    def add_devices_by_tag(self):
        """Add devices with the selected tags to the active configuration."""
        # This would be implemented for drag-and-drop in the future

    @SafeSlot()
    def remove_devices_by_tag(self):
        """Remove devices with the selected tags from the active configuration."""
        # This would be implemented for drag-and-drop in the future


class DeviceManager(BECWidget, QWidget):
    """Widget to display the current device configuration in a table."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        # Main layout for the entire widget
        self.main_layout = QHBoxLayout(self)
        self.setLayout(self.main_layout)

        # Create a splitter to hold the device tags widget and device table
        self.splitter = QSplitter(Qt.Horizontal)

        # Create device tags widget
        self.device_tags_widget = DeviceTagsWidget(self)
        self.splitter.addWidget(self.device_tags_widget)

        # Create container for device table and its controls
        self.table_container = QWidget()
        self.layout = QVBoxLayout(self.table_container)

        # Create search bar
        self.search_layout = QHBoxLayout()
        self.search_label = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Filter devices (approximate matching)..."
        )  # Default to fuzzy search
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.filter_devices)
        self.search_layout.addWidget(self.search_label)
        self.search_layout.addWidget(self.search_input)

        # Add exact match toggle
        self.fuzzy_toggle_layout = QHBoxLayout()
        self.fuzzy_toggle_label = QLabel("Exact Match:")
        self.fuzzy_toggle = ToggleSwitch()
        self.fuzzy_toggle.setChecked(False)  # Default to fuzzy search (toggle OFF)
        self.fuzzy_toggle.stateChanged.connect(self.on_fuzzy_toggle_changed)
        self.fuzzy_toggle.setToolTip(
            "Toggle between approximate matching (OFF) and exact matching (ON)"
        )
        self.fuzzy_toggle_label.setToolTip(
            "Toggle between approximate matching (OFF) and exact matching (ON)"
        )
        self.fuzzy_toggle_layout.addWidget(self.fuzzy_toggle_label)
        self.fuzzy_toggle_layout.addWidget(self.fuzzy_toggle)
        self.fuzzy_toggle_layout.addStretch()

        # Add both search components to the layout
        self.search_controls = QHBoxLayout()
        self.search_controls.addLayout(self.search_layout)
        self.search_controls.addSpacing(20)  # Add some space between the search box and toggle
        self.search_controls.addLayout(self.fuzzy_toggle_layout)

        self.layout.addLayout(self.search_controls)

        # Create table widget
        self.device_table = BECTable()
        self.device_table.setEditTriggers(QTableWidget.NoEditTriggers)  # Make table read-only
        self.device_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.device_table.setAlternatingRowColors(True)
        self.layout.addWidget(self.device_table)

        # Connect custom sorting handler
        self.device_table.horizontalHeader().sectionClicked.connect(self.handle_header_click)
        self.current_sort_section = 0
        self.current_sort_order = Qt.AscendingOrder

        # Make table resizable
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.device_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Don't stretch the last section to prevent it from changing width
        self.device_table.horizontalHeader().setStretchLastSection(False)
        self.device_table.verticalHeader().setVisible(False)

        # Set up initial headers
        self.headers = [
            "Name",
            "Device Class",
            "Readout Priority",
            "Enabled",
            "Read Only",
            "Documentation",
        ]
        self.device_table.setColumnCount(len(self.headers))
        self.device_table.setHorizontalHeaderLabels(self.headers)

        # Set initial column resize modes
        header = self.device_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Name
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Device Class
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Readout Priority
        header.setSectionResizeMode(3, QHeaderView.Fixed)  # Enabled
        header.setSectionResizeMode(4, QHeaderView.Fixed)  # Read Only
        header.setSectionResizeMode(5, QHeaderView.Stretch)  # Documentation

        # Connect resize signal to adjust row heights when table is resized
        self.device_table.horizontalHeader().sectionResized.connect(self.on_table_resized)

        # Set fixed width for checkbox columns
        self.device_table.setColumnWidth(3, 70)  # Enabled column
        self.device_table.setColumnWidth(4, 70)  # Read Only column

        # Ensure column widths stay fixed
        header.setMinimumSectionSize(70)
        header.setDefaultSectionSize(100)

        # Enable sorting by clicking column headers
        self.device_table.setSortingEnabled(False)  # We'll handle sorting manually
        self.device_table.horizontalHeader().setSortIndicatorShown(True)
        self.device_table.horizontalHeader().setSectionsClickable(True)

        # Add buttons for adding/removing devices
        self.button_layout = QHBoxLayout()

        # Add device button
        self.add_device_button = QPushButton("Add Device")
        self.add_device_button.clicked.connect(self.add_device)
        self.button_layout.addWidget(self.add_device_button)

        # Remove device button
        self.remove_device_button = QPushButton("Remove Device")
        self.remove_device_button.clicked.connect(self.remove_device)
        self.button_layout.addWidget(self.remove_device_button)

        # Add buttons to main layout
        self.layout.addLayout(self.button_layout)

        # Add the table container to the splitter
        self.splitter.addWidget(self.table_container)

        # Set initial sizes (30% for tags, 70% for table)
        self.splitter.setSizes([300, 700])

        # Add the splitter to the main layout
        self.main_layout.addWidget(self.splitter)

        # Connect signals between widgets
        self.connect_signals()

        # Load initial data
        self.update_device_table()

    def connect_signals(self):
        """Connect signals between the device table and tags widget."""
        # Connect add devices by tag button to update the table
        if hasattr(self.device_tags_widget, "add_tag_button"):
            self.device_tags_widget.add_tag_button.clicked.connect(self.update_device_table)

        # Connect remove devices by tag button to update the table
        if hasattr(self.device_tags_widget, "remove_tag_button"):
            self.device_tags_widget.remove_tag_button.clicked.connect(self.update_device_table)

    @SafeSlot(int, int, int)
    def on_table_resized(self, column, old_width, new_width):
        """Handle table column resize events to readjust row heights for text wrapping."""
        # Only handle resizes of the documentation column
        if column == 5:
            # Update all rows with TextLabelWidgets in the documentation column
            for row in range(self.device_table.rowCount()):
                doc_widget = self.device_table.cellWidget(row, 5)
                if doc_widget and isinstance(doc_widget, TextLabelWidget):
                    # Trigger recalculation of text wrapping
                    doc_widget.updateGeometry()

                    # Force the table to recalculate row heights
                    if doc_widget.value:
                        # Get text metrics
                        font_metrics = doc_widget.label.fontMetrics()

                        # Calculate new text height with word wrap
                        text_rect = font_metrics.boundingRect(
                            0,
                            0,
                            new_width - 10,
                            2000,  # New width constraint
                            Qt.TextWordWrap,
                            doc_widget.value,
                        )

                        # Update row height
                        row_height = text_rect.height() + 16
                        self.device_table.setRowHeight(row, max(40, row_height))

    @SafeSlot()
    def update_device_table(self):
        """Update the device table with the current device configuration."""
        try:
            # Get device config (always a list of dictionaries)
            config = self.client.device_manager._get_redis_device_config()

            # Clear existing rows
            self.device_table.setRowCount(0)

            # Add devices to the table
            for device_info in config:
                row_position = self.device_table.rowCount()
                self.device_table.insertRow(row_position)

                # Set device name
                self.device_table.setItem(
                    row_position, 0, SortableTableWidgetItem(device_info.get("name", "Unknown"))
                )

                # Set device class
                device_class = device_info.get("deviceClass", "Unknown")
                self.device_table.setItem(row_position, 1, SortableTableWidgetItem(device_class))

                # Set readout priority
                readout_priority = device_info.get("readoutPriority", "Unknown")
                self.device_table.setItem(
                    row_position, 2, SortableTableWidgetItem(readout_priority)
                )

                # Set enabled status as checkbox
                enabled_checkbox = CheckBoxCenterWidget(device_info.get("enabled", False))
                self.device_table.setCellWidget(row_position, 3, enabled_checkbox)

                # Set read-only status as checkbox
                readonly_checkbox = CheckBoxCenterWidget(device_info.get("readOnly", False))
                self.device_table.setCellWidget(row_position, 4, readonly_checkbox)

                # Set documentation using text label widget with word wrap
                documentation = device_info.get("documentation", "")
                doc_widget = TextLabelWidget(documentation)
                self.device_table.setCellWidget(row_position, 5, doc_widget)

            # First, ensure the table is updated to show the new widgets
            self.device_table.viewport().update()

            # Force a layout update to get proper sizes
            self.device_table.resizeRowsToContents()

            # Then adjust row heights with better calculation for wrapped text
            for row in range(self.device_table.rowCount()):
                doc_widget = self.device_table.cellWidget(row, 5)
                if doc_widget and isinstance(doc_widget, TextLabelWidget):
                    text = doc_widget.value
                    if text:
                        # Get the column width
                        col_width = self.device_table.columnWidth(5)

                        # Calculate appropriate height for the text
                        font_metrics = doc_widget.label.fontMetrics()

                        # Calculate text rectangle with word wrap
                        text_rect = font_metrics.boundingRect(
                            0,
                            0,
                            col_width - 10,
                            2000,  # Width constraint with large height
                            Qt.TextWordWrap,
                            text,
                        )

                        # Set row height with additional padding
                        row_height = text_rect.height() + 16
                        self.device_table.setRowHeight(row, max(40, row_height))

                        # Update the widget to reflect the new size
                        doc_widget.updateGeometry()

            # Apply current sort if any
            if hasattr(self, "current_sort_section") and self.current_sort_section >= 0:
                self.sort_table(self.current_sort_section, self.current_sort_order)
                self.device_table.horizontalHeader().setSortIndicator(
                    self.current_sort_section, self.current_sort_order
                )

            # Reset the filter to make sure search works with new data
            if hasattr(self, "search_input"):
                current_filter = self.search_input.text()
                if current_filter:
                    self.filter_devices(current_filter)

            # Update the device tags widget
            self.device_tags_widget.update_tags()

        except Exception as e:
            ErrorPopupUtility().show_error_message(
                "Device Manager Error", f"Error updating device table: {str(e)}", self
            )

    @SafeSlot(bool)
    def on_fuzzy_toggle_changed(self, enabled):
        """
        Handle exact match toggle state change.

        When toggle is ON (enabled=True): Use exact matching
        When toggle is OFF (enabled=False): Use fuzzy/approximate matching
        """
        # Update search mode label
        if hasattr(self, "search_input"):
            # Store original stylesheet to restore it later
            original_style = self.search_input.styleSheet()

            # Set placeholder text based on mode
            if enabled:  # Toggle ON = Exact match
                self.search_input.setPlaceholderText("Filter devices (exact match)...")
                print("Toggle switched ON: Using EXACT match mode")
            else:  # Toggle OFF = Approximate/fuzzy match
                self.search_input.setPlaceholderText("Filter devices (approximate matching)...")
                print("Toggle switched OFF: Using FUZZY match mode")

            # Visual feedback - briefly highlight the search box with appropriate color
            highlight_color = "#3498db"  # Blue for feedback
            self.search_input.setStyleSheet(f"border: 2px solid {highlight_color};")

            # Create a one-time timer to restore the original style after a short delay
            from qtpy.QtCore import QTimer

            QTimer.singleShot(500, lambda: self.search_input.setStyleSheet(original_style))

            # Log the toggle state for debugging
            print(
                f"Search mode changed: Exact match = {enabled}, Toggle isChecked = {self.fuzzy_toggle.isChecked()}"
            )

        # When toggle changes, reapply current search with new mode
        current_text = self.search_input.text()

        # Always reapply the filter, even if text is empty
        # This ensures all rows are properly shown/hidden based on the new mode
        self.filter_devices(current_text)

    @SafeSlot(str)
    def filter_devices(self, text):
        """Filter devices in the table based on exact or approximate matching."""
        # Always show all rows when search is empty, regardless of match mode
        if not text:
            for row in range(self.device_table.rowCount()):
                self.device_table.setRowHidden(row, False)
            return

        # Get current search mode
        # When toggle is ON, we use exact match
        # When toggle is OFF, we use fuzzy/approximate match
        use_exact_match = hasattr(self, "fuzzy_toggle") and self.fuzzy_toggle.isChecked()

        # Debug print to verify which mode is being used
        print(f"Filtering with exact match: {use_exact_match}, search text: '{text}'")

        # Threshold for fuzzy matching (0-100, higher is more strict)
        threshold = 80

        # Prepare search text (lowercase for case-insensitive search)
        search_text = text.lower()

        # Count of matched rows for feedback (but avoid double-counting)
        visible_rows = 0
        total_rows = self.device_table.rowCount()

        # Filter rows using either exact or approximate matching
        for row in range(total_rows):
            row_visible = False

            # Check name and device class columns (0 and 1)
            for col in [0, 1]:  # Name and Device Class columns
                item = self.device_table.item(row, col)
                if not item:
                    continue

                cell_text = item.text().lower()

                if use_exact_match:
                    # EXACT MATCH: Simple substring check
                    if search_text in cell_text:
                        row_visible = True
                        break
                else:
                    # FUZZY MATCH: Use approximate matching
                    match_ratio = fuzz.partial_ratio(search_text, cell_text)
                    if match_ratio >= threshold:
                        row_visible = True
                        break

            # Hide or show this row
            self.device_table.setRowHidden(row, not row_visible)

            # Count visible rows for potential feedback
            if row_visible:
                visible_rows += 1

    @SafeSlot(int)
    def handle_header_click(self, section):
        """Handle column header click to sort the table."""
        # Toggle sort order if clicking the same section
        if section == self.current_sort_section:
            self.current_sort_order = (
                Qt.DescendingOrder
                if self.current_sort_order == Qt.AscendingOrder
                else Qt.AscendingOrder
            )
        else:
            self.current_sort_section = section
            self.current_sort_order = Qt.AscendingOrder

        # Update sort indicator
        self.device_table.horizontalHeader().setSortIndicator(
            self.current_sort_section, self.current_sort_order
        )

        # Perform the sort
        self.sort_table(section, self.current_sort_order)

    def sort_table(self, column, order):
        """Sort the table by the specified column and order."""
        row_count = self.device_table.rowCount()
        if row_count <= 1:
            return  # Nothing to sort

        # Collect all rows for sorting
        rows_data = []
        for row in range(row_count):
            # Create a safe copy of the row data
            row_data = {}
            row_data["items"] = []
            row_data["widgets"] = []
            row_data["hidden"] = self.device_table.isRowHidden(row)
            row_data["sort_key"] = None

            # Extract sort key for this row
            if column in [3, 4]:  # Checkbox columns
                widget = self.device_table.cellWidget(row, column)
                if widget and hasattr(widget, "value"):
                    row_data["sort_key"] = widget.value
                else:
                    row_data["sort_key"] = False
            else:  # Text columns
                item = self.device_table.item(row, column)
                if item:
                    row_data["sort_key"] = item.text().lower()
                else:
                    row_data["sort_key"] = ""

            # Collect all items and widgets in the row
            for col in range(self.device_table.columnCount()):
                if col in [3, 4]:  # Checkbox columns
                    widget = self.device_table.cellWidget(row, col)
                    if widget:
                        # Store the widget value to recreate it
                        is_checked = False
                        if hasattr(widget, "value"):
                            is_checked = widget.value
                        elif hasattr(widget, "checkbox"):
                            is_checked = widget.checkbox.isChecked()
                        row_data["widgets"].append((col, "checkbox", is_checked))
                elif col == 5:  # Documentation column with TextLabelWidget
                    widget = self.device_table.cellWidget(row, col)
                    if widget and isinstance(widget, TextLabelWidget):
                        text = widget.value
                        row_data["widgets"].append((col, "textlabel", text))
                    else:
                        row_data["widgets"].append((col, "textlabel", ""))
                else:
                    item = self.device_table.item(row, col)
                    if item:
                        row_data["items"].append((col, item.text()))
                    else:
                        row_data["items"].append((col, ""))

            rows_data.append(row_data)

        # Sort the rows
        reverse = order == Qt.DescendingOrder
        sorted_rows = sorted(rows_data, key=lambda x: x["sort_key"], reverse=reverse)

        # Rebuild the table with sorted data
        self.device_table.setUpdatesEnabled(False)  # Disable updates while rebuilding

        # Clear and rebuild the table
        self.device_table.clearContents()
        self.device_table.setRowCount(row_count)

        for row, row_data in enumerate(sorted_rows):
            # Add text items
            for col, text in row_data["items"]:
                self.device_table.setItem(row, col, SortableTableWidgetItem(text))

            # Add widgets
            for col, widget_type, value in row_data["widgets"]:
                if widget_type == "checkbox":
                    checkbox = CheckBoxCenterWidget(value)
                    self.device_table.setCellWidget(row, col, checkbox)
                elif widget_type == "textlabel":
                    text_label = TextLabelWidget(value)
                    self.device_table.setCellWidget(row, col, text_label)

            # Restore hidden state
            self.device_table.setRowHidden(row, row_data["hidden"])

        self.device_table.setUpdatesEnabled(True)  # Re-enable updates

    @SafeSlot()
    def show_add_device_dialog(self):
        """Show the dialog for adding a new device."""
        # Call the add_device method to handle the dialog and logic
        self.add_device()

    @SafeSlot()
    def add_device(self):
        """Simulate adding a new device to the configuration."""
        try:
            # Create and show the add device dialog
            dialog = AddDeviceDialog(self)
            if dialog.exec():
                # Get device config from dialog
                device_config = dialog.get_device_config()
                device_name = device_config.get("name")

                # Print the action that would be taken (simulation only)
                print(f"Would add device: {device_name} with config: {device_config}")

                # Show simulation message
                QMessageBox.information(
                    self,
                    "Device Addition Simulated",
                    f"Would add device: {device_name} (simulation only)",
                )

                # Update the device tags widget
                self.device_tags_widget.update_tags()

        except Exception as e:
            ErrorPopupUtility().show_error_message(
                "Device Manager Error", f"Error in add device simulation: {str(e)}", self
            )

    @SafeSlot()
    def remove_device(self):
        """Simulate removing selected device(s) from the configuration."""
        selected_rows = self.device_table.selectionModel().selectedRows()

        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select a device to remove.")
            return

        # Confirm deletion
        device_count = len(selected_rows)
        message = f"Are you sure you want to remove {device_count} device{'s' if device_count > 1 else ''}?"
        confirmation = QMessageBox.question(
            self, "Confirm Removal", message, QMessageBox.Yes | QMessageBox.No
        )

        if confirmation == QMessageBox.Yes:
            try:
                # Get device names from selected rows
                device_names = []
                for index in selected_rows:
                    row = index.row()
                    device_name = self.device_table.item(row, 0).text()
                    device_names.append(device_name)

                # Print removal action instead of actual removal
                print(f"Would remove devices: {device_names}")

                # Show simulation message
                QMessageBox.information(
                    self,
                    "Device Removal Simulated",
                    f"Would remove {device_count} device{'s' if device_count > 1 else ''} (simulation only)",
                )

                # Update the device tags widget
                self.device_tags_widget.update_tags()

            except Exception as e:
                ErrorPopupUtility().show_error_message(
                    "Device Manager Error", f"Error in remove device simulation: {str(e)}", self
                )


class AddDeviceDialog(QDialog):
    """Dialog for adding a new device to the configuration."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Device")
        self.setMinimumWidth(400)

        # Create layout
        self.layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()

        # Device name
        self.name_input = QLineEdit()
        self.form_layout.addRow("Device Name:", self.name_input)

        # Device class
        self.device_class_input = QLineEdit()
        self.device_class_input.setText("ophyd_devices.SimPositioner")
        self.form_layout.addRow("Device Class:", self.device_class_input)

        # Readout priority
        self.readout_priority_combo = QComboBox()
        self.readout_priority_combo.addItems(["baseline", "monitored", "async", "on_request"])
        self.form_layout.addRow("Readout Priority:", self.readout_priority_combo)

        # Enabled checkbox
        self.enabled_checkbox = QCheckBox()
        self.enabled_checkbox.setChecked(True)
        self.form_layout.addRow("Enabled:", self.enabled_checkbox)

        # Read-only checkbox
        self.readonly_checkbox = QCheckBox()
        self.form_layout.addRow("Read Only:", self.readonly_checkbox)

        # Documentation text
        self.documentation_input = QLineEdit()
        self.form_layout.addRow("Documentation:", self.documentation_input)

        # Add form to layout
        self.layout.addLayout(self.form_layout)

        # Add buttons
        self.button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.add_button = QPushButton("Add Device")
        self.add_button.clicked.connect(self.accept)
        self.button_layout.addWidget(self.cancel_button)
        self.button_layout.addWidget(self.add_button)

        self.layout.addLayout(self.button_layout)

    def get_device_config(self):
        """Get the device configuration from the dialog."""
        return {
            "name": self.name_input.text(),
            "deviceClass": self.device_class_input.text(),
            "readoutPriority": self.readout_priority_combo.currentText(),
            "enabled": self.enabled_checkbox.isChecked(),
            "readOnly": self.readonly_checkbox.isChecked(),
            "documentation": self.documentation_input.text(),
            "deviceConfig": {},  # Empty config for now
        }


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    window = DeviceManager()
    window.show()
    app.exec_()
