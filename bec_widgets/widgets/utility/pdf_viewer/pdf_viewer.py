import os
from typing import Optional

from qtpy.QtCore import QMargins, Qt, Signal
from qtpy.QtGui import QIntValidator
from qtpy.QtPdf import QPdfDocument
from qtpy.QtPdfWidgets import QPdfView
from qtpy.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.toolbars.actions import MaterialIconAction, WidgetAction
from bec_widgets.utils.toolbars.toolbar import ModularToolBar


class PdfViewerWidget(BECWidget, QWidget):
    """A widget to display PDF documents with toolbar controls."""

    # Emitted when a PDF document is successfully loaded, providing the file path.
    document_ready = Signal(str)

    PLUGIN = True
    RPC = True
    ICON_NAME = "picture_as_pdf"
    USER_ACCESS = [
        "load_pdf",
        "zoom_in",
        "zoom_out",
        "fit_to_width",
        "fit_to_page",
        "reset_zoom",
        "previous_page",
        "next_page",
        "toggle_continuous_scroll",
        "page_spacing",
        "page_spacing.setter",
        "side_margins",
        "side_margins.setter",
        "go_to_first_page",
        "go_to_last_page",
        "jump_to_page",
        "current_page",
        "current_file_path",
        "current_file_path.setter",
    ]

    def __init__(
        self, parent: Optional[QWidget] = None, config=None, client=None, gui_id=None, **kwargs
    ):
        super().__init__(parent=parent, config=config, client=client, gui_id=gui_id, **kwargs)

        # Set up the layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create the PDF document and view first
        self._pdf_document = QPdfDocument(self)
        self.pdf_view = QPdfView()
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

        # Create toolbar after PDF components are initialized
        self.toolbar = ModularToolBar(parent=self, orientation="horizontal")
        self._setup_toolbar()

        # Add widgets to layout
        layout.addWidget(self.toolbar)
        layout.addWidget(self.pdf_view)

        # Current file path and spacing settings
        self._current_file_path = None
        self._page_spacing = 5  # Default spacing between pages in continuous mode
        self._side_margins = 10  # Default side margins (horizontal spacing)

    def _setup_toolbar(self):
        """Set up the toolbar with PDF control buttons."""
        # Create separate bundles for different control groups
        file_bundle = self.toolbar.new_bundle("file_controls")
        zoom_bundle = self.toolbar.new_bundle("zoom_controls")
        view_bundle = self.toolbar.new_bundle("view_controls")
        nav_bundle = self.toolbar.new_bundle("navigation_controls")

        # File operations
        open_action = MaterialIconAction(
            icon_name="folder_open", tooltip="Open PDF File", parent=self
        )
        open_action.action.triggered.connect(self.open_file_dialog)
        self.toolbar.components.add("open_file", open_action)
        file_bundle.add_action("open_file")

        # Zoom controls
        zoom_in_action = MaterialIconAction(icon_name="zoom_in", tooltip="Zoom In", parent=self)
        zoom_in_action.action.triggered.connect(self.zoom_in)
        self.toolbar.components.add("zoom_in", zoom_in_action)
        zoom_bundle.add_action("zoom_in")

        zoom_out_action = MaterialIconAction(icon_name="zoom_out", tooltip="Zoom Out", parent=self)
        zoom_out_action.action.triggered.connect(self.zoom_out)
        self.toolbar.components.add("zoom_out", zoom_out_action)
        zoom_bundle.add_action("zoom_out")

        fit_width_action = MaterialIconAction(
            icon_name="fit_screen", tooltip="Fit to Width", parent=self
        )
        fit_width_action.action.triggered.connect(self.fit_to_width)
        self.toolbar.components.add("fit_width", fit_width_action)
        zoom_bundle.add_action("fit_width")

        fit_page_action = MaterialIconAction(
            icon_name="fullscreen", tooltip="Fit to Page", parent=self
        )
        fit_page_action.action.triggered.connect(self.fit_to_page)
        self.toolbar.components.add("fit_page", fit_page_action)
        zoom_bundle.add_action("fit_page")

        reset_zoom_action = MaterialIconAction(
            icon_name="center_focus_strong", tooltip="Reset Zoom to 100%", parent=self
        )
        reset_zoom_action.action.triggered.connect(self.reset_zoom)
        self.toolbar.components.add("reset_zoom", reset_zoom_action)
        zoom_bundle.add_action("reset_zoom")

        # View controls
        continuous_scroll_action = MaterialIconAction(
            icon_name="view_agenda", tooltip="Toggle Continuous Scroll", checkable=True, parent=self
        )
        continuous_scroll_action.action.toggled.connect(self.toggle_continuous_scroll)
        self.toolbar.components.add("continuous_scroll", continuous_scroll_action)
        view_bundle.add_action("continuous_scroll")

        # Navigation controls
        prev_page_action = MaterialIconAction(
            icon_name="navigate_before", tooltip="Previous Page", parent=self
        )
        prev_page_action.action.triggered.connect(self.previous_page)
        self.toolbar.components.add("prev_page", prev_page_action)
        nav_bundle.add_action("prev_page")

        next_page_action = MaterialIconAction(
            icon_name="navigate_next", tooltip="Next Page", parent=self
        )
        next_page_action.action.triggered.connect(self.next_page)
        self.toolbar.components.add("next_page", next_page_action)
        nav_bundle.add_action("next_page")

        # Page jump widget (in navigation bundle)
        self._setup_page_jump_widget(nav_bundle)

        # Show all bundles
        self.toolbar.show_bundles(
            ["file_controls", "zoom_controls", "view_controls", "navigation_controls"]
        )

        # Initialize navigation button tooltips for single page mode (default)
        self._update_navigation_buttons_for_mode(continuous=False)

        # Initialize navigation button states
        self._update_navigation_button_states()

    def _setup_page_jump_widget(self, nav_bundle):
        """Set up the page jump widget (label + line edit)."""
        # Create a container widget for the page jump controls
        page_jump_container = QWidget()
        page_jump_layout = QHBoxLayout(page_jump_container)
        page_jump_layout.setContentsMargins(5, 0, 5, 0)
        page_jump_layout.setSpacing(3)

        # Page input field
        self.page_input = QLineEdit()
        self.page_input.setValidator(QIntValidator(1, 100000))  # restrict to 1–100000
        self.page_input.setFixedWidth(50)
        self.page_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_input.setPlaceholderText("1")
        self.page_input.setToolTip("Enter page number and press Enter")
        self.page_input.returnPressed.connect(self._line_edit_jump_to_page)

        # Total pages label
        self.total_pages_label = QLabel("/ 1")
        self.total_pages_label.setStyleSheet("color: #666; font-size: 12px;")

        # Add widgets to layout
        page_jump_layout.addWidget(self.page_input)
        page_jump_layout.addWidget(self.total_pages_label)

        # Create a WidgetAction for the page jump controls
        # No manual separator needed - bundles are automatically separated
        page_jump_action = WidgetAction(
            label="Page:", widget=page_jump_container, adjust_size=False, parent=self
        )
        self.toolbar.components.add("page_jump", page_jump_action)
        nav_bundle.add_action("page_jump")

    def _line_edit_jump_to_page(self):
        """Jump to the page entered in the line edit."""
        page_text = self.page_input.text().strip()
        if not page_text:
            return
        # We validated input to be integer, so safe to convert directly
        self.jump_to_page(int(page_text))

    def _update_navigation_button_states(self):
        """Update the enabled/disabled state of navigation buttons."""
        if not self._pdf_document or self._pdf_document.status() != QPdfDocument.Status.Ready:
            # No document loaded - disable all navigation
            self._set_navigation_enabled(False, False)
            self._update_page_display(1, 1)
            return

        navigator = self.pdf_view.pageNavigator()
        current_page = navigator.currentPage()
        total_pages = self._pdf_document.pageCount()

        # Update button states
        prev_enabled = current_page > 0
        next_enabled = current_page < (total_pages - 1)
        self._set_navigation_enabled(prev_enabled, next_enabled)

        # Update page display
        self._update_page_display(current_page + 1, total_pages)

    def _set_navigation_enabled(self, prev_enabled: bool, next_enabled: bool):
        """Set the enabled state of navigation buttons."""
        prev_action = self.toolbar.components.get_action("prev_page")
        if prev_action and hasattr(prev_action, "action") and prev_action.action:
            prev_action.action.setEnabled(prev_enabled)

        next_action = self.toolbar.components.get_action("next_page")
        if next_action and hasattr(next_action, "action") and next_action.action:
            next_action.action.setEnabled(next_enabled)

    def _update_page_display(self, current_page: int, total_pages: int):
        """Update the page display in the toolbar."""
        if hasattr(self, "page_input"):
            self.page_input.setText(str(current_page))
            self.page_input.setPlaceholderText(str(current_page))

        if hasattr(self, "total_pages_label"):
            self.total_pages_label.setText(f"/ {total_pages}")

    @SafeProperty(str)
    def current_file_path(self):
        """Get the current PDF file path."""
        return self._current_file_path

    @current_file_path.setter
    def current_file_path(self, value: str):
        """
        Set the current PDF file path and load the document.

        Args:
            value (str): Path to the PDF file to load.
        """
        if not isinstance(value, str):
            raise ValueError("current_file_path must be a string")
        self.load_pdf(value)

    @SafeProperty(int)
    def page_spacing(self):
        """Get the spacing between pages in continuous scroll mode."""
        return self._page_spacing

    @property
    def current_page(self):
        """Get the current page number (1-based index)."""
        if not self._pdf_document or self._pdf_document.status() != QPdfDocument.Status.Ready:
            return 0
        navigator = self.pdf_view.pageNavigator()
        return navigator.currentPage() + 1

    @page_spacing.setter
    def page_spacing(self, value: int):
        """
        Set the spacing between pages in continuous scroll mode.

        Args:
            value (int): Spacing in pixels (non-negative integer).
        """
        if not isinstance(value, int):
            raise ValueError("page_spacing must be an integer")
        if value < 0:
            raise ValueError("page_spacing must be non-negative")

        self._page_spacing = value

        # If currently in continuous scroll mode, update the spacing immediately
        if self.pdf_view.pageMode() == QPdfView.PageMode.MultiPage:
            self.pdf_view.setPageSpacing(self._page_spacing)

    @SafeProperty(int)
    def side_margins(self):
        """Get the horizontal margins (side spacing) around the PDF content."""
        return self._side_margins

    @side_margins.setter
    def side_margins(self, value: int):
        """Set the horizontal margins (side spacing) around the PDF content."""
        if not isinstance(value, int):
            raise ValueError("side_margins must be an integer")
        if value < 0:
            raise ValueError("side_margins must be non-negative")

        self._side_margins = value

        # Update the document margins immediately
        # setDocumentMargins takes a QMargins(left, top, right, bottom)
        margins = QMargins(self._side_margins, 0, self._side_margins, 0)
        self.pdf_view.setDocumentMargins(margins)

    def open_file_dialog(self):
        """Open a file dialog to select a PDF file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF File", "", "PDF Files (*.pdf);;All Files (*)"
        )
        if file_path:
            self.load_pdf(file_path)

    @SafeSlot(str, popup_error=True)
    def load_pdf(self, file_path: str):
        """
        Load a PDF file into the viewer.

        Args:
            file_path (str): Path to the PDF file to load.
        """
        # Validate file exists
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        self._current_file_path = file_path

        # Disconnect any existing signal connections
        try:
            self._pdf_document.statusChanged.disconnect(self._on_document_status_changed)
        except (TypeError, RuntimeError):
            pass

        # Connect to statusChanged signal to handle when document is ready
        self._pdf_document.statusChanged.connect(self._on_document_status_changed)

        # Load the document
        self._pdf_document.load(file_path)

        # If already ready (synchronous loading), set document immediately
        if self._pdf_document.status() == QPdfDocument.Status.Ready:
            self._on_document_ready()

    @SafeSlot(QPdfDocument.Status)
    def _on_document_status_changed(self, status: QPdfDocument.Status):
        """Handle document status changes."""
        status = self._pdf_document.status()

        if status == QPdfDocument.Status.Ready:
            self._on_document_ready()
        elif status == QPdfDocument.Status.Error:
            raise RuntimeError(f"Failed to load PDF document: {self._current_file_path}")

    def _on_document_ready(self):
        """Handle when document is ready to be displayed."""
        self.pdf_view.setDocument(self._pdf_document)

        # Set initial margins
        margins = QMargins(self._side_margins, 0, self._side_margins, 0)
        self.pdf_view.setDocumentMargins(margins)

        # Connect to page changes to update navigation button states
        navigator = self.pdf_view.pageNavigator()
        navigator.currentPageChanged.connect(self._on_page_changed)

        # Make sure we start at the first page
        navigator.update(0, navigator.currentLocation(), navigator.currentZoom())

        # Update initial navigation state
        self._update_navigation_button_states()
        self.document_ready.emit(self._current_file_path)

    def _on_page_changed(self, _page):
        """Handle page change events to update navigation states."""
        self._update_navigation_button_states()

    # Toolbar action methods
    @SafeSlot()
    def zoom_in(self):
        """Zoom in the PDF view."""
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        current_factor = self.pdf_view.zoomFactor()
        new_factor = current_factor * 1.25
        self.pdf_view.setZoomFactor(new_factor)

    @SafeSlot()
    def zoom_out(self):
        """Zoom out the PDF view."""
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        current_factor = self.pdf_view.zoomFactor()
        new_factor = max(current_factor / 1.25, 0.1)
        self.pdf_view.setZoomFactor(new_factor)

    @SafeSlot()
    def fit_to_width(self):
        """Fit PDF to width."""
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

    @SafeSlot()
    def fit_to_page(self):
        """Fit PDF to page."""
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)

    @SafeSlot()
    def reset_zoom(self):
        """Reset zoom to 100% (1.0 factor)."""
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.pdf_view.setZoomFactor(1.0)

    @SafeSlot()
    def previous_page(self):
        """Go to previous page."""
        if not self._pdf_document or self._pdf_document.status() != QPdfDocument.Status.Ready:
            return

        navigator = self.pdf_view.pageNavigator()
        current_page = navigator.currentPage()
        if current_page == 0:
            self._update_navigation_button_states()
            return

        try:
            target_page = current_page - 1
            navigator.update(target_page, navigator.currentLocation(), navigator.currentZoom())
        except Exception:
            try:
                # Fallback: Use scroll to approximate position
                page_height = self.pdf_view.viewport().height()
                self.pdf_view.verticalScrollBar().setValue(
                    self.pdf_view.verticalScrollBar().value() - page_height
                )
            except Exception:
                pass

        # Update navigation button states (in case signal doesn't fire)
        self._update_navigation_button_states()

    @SafeSlot()
    def next_page(self):
        """Go to next page."""
        if not self._pdf_document or self._pdf_document.status() != QPdfDocument.Status.Ready:
            return

        navigator = self.pdf_view.pageNavigator()
        current_page = navigator.currentPage()
        max_page = self._pdf_document.pageCount() - 1
        if current_page < max_page:
            try:
                target_page = current_page + 1
                navigator.update(target_page, navigator.currentLocation(), navigator.currentZoom())
            except Exception:
                try:
                    # Fallback: Use scroll to approximate position
                    page_height = self.pdf_view.viewport().height()
                    self.pdf_view.verticalScrollBar().setValue(
                        self.pdf_view.verticalScrollBar().value() + page_height
                    )
                except Exception:
                    pass

        # Update navigation button states (in case signal doesn't fire)
        self._update_navigation_button_states()

    @SafeSlot(bool)
    def toggle_continuous_scroll(self, checked: bool):
        """
        Toggle between single page and continuous scroll mode.

        Args:
            checked (bool): True to enable continuous scroll, False for single page mode.
        """
        if checked:
            self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
            self.pdf_view.setPageSpacing(self._page_spacing)
            self._update_navigation_buttons_for_mode(continuous=True)
            tooltip = "Switch to Single Page Mode"
        else:
            self.pdf_view.setPageMode(QPdfView.PageMode.SinglePage)
            self._update_navigation_buttons_for_mode(continuous=False)
            tooltip = "Switch to Continuous Scroll Mode"

        # Update navigation button states after mode change
        self._update_navigation_button_states()

        # Update toggle button tooltip to reflect current state
        action = self.toolbar.components.get_action("continuous_scroll")
        if action and hasattr(action, "action") and action.action:
            action.action.setToolTip(tooltip)

    def _update_navigation_buttons_for_mode(self, continuous: bool):
        """Update navigation button tooltips based on current mode."""
        prev_action = self.toolbar.components.get_action("prev_page")
        next_action = self.toolbar.components.get_action("next_page")

        if continuous:
            prev_actions_tooltip = "Previous Page (use scroll in continuous mode)"
            next_actions_tooltip = "Next Page (use scroll in continuous mode)"
        else:
            prev_actions_tooltip = "Previous Page"
            next_actions_tooltip = "Next Page"

        if prev_action and hasattr(prev_action, "action") and prev_action.action:
            prev_action.action.setToolTip(prev_actions_tooltip)
        if next_action and hasattr(next_action, "action") and next_action.action:
            next_action.action.setToolTip(next_actions_tooltip)

    @SafeSlot()
    def go_to_first_page(self):
        """Go to the first page."""
        if not self._pdf_document or self._pdf_document.status() != QPdfDocument.Status.Ready:
            return

        navigator = self.pdf_view.pageNavigator()
        navigator.update(0, navigator.currentLocation(), navigator.currentZoom())

    @SafeSlot()
    def go_to_last_page(self):
        """Go to the last page."""
        if not self._pdf_document or self._pdf_document.status() != QPdfDocument.Status.Ready:
            return

        navigator = self.pdf_view.pageNavigator()
        last_page = self._pdf_document.pageCount() - 1
        navigator.update(last_page, navigator.currentLocation(), navigator.currentZoom())

    @SafeSlot(int)
    def jump_to_page(self, page_number: int):
        """Jump to a specific page number (1-based index)."""
        if not isinstance(page_number, int):
            raise ValueError("page_number must be an integer")

        if not self._pdf_document or self._pdf_document.status() != QPdfDocument.Status.Ready:
            raise RuntimeError("No PDF document loaded")

        max_page = self._pdf_document.pageCount()
        page_number = max(min(page_number, max_page), 1)

        target_page = page_number - 1  # Convert to 0-based index
        navigator = self.pdf_view.pageNavigator()
        navigator.update(target_page, navigator.currentLocation(), navigator.currentZoom())

    def cleanup(self):
        """Handle widget close event to prevent segfaults."""
        if hasattr(self, "_pdf_document") and self._pdf_document:
            self._pdf_document.statusChanged.disconnect()
            empty_doc = QPdfDocument(self)
            self.pdf_view.setDocument(empty_doc)

        if hasattr(self, "toolbar"):
            self.toolbar.cleanup()

        super().cleanup()


if __name__ == "__main__":
    import sys

    # from bec_qthemes import apply_theme
    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    # apply_theme("dark")
    viewer = PdfViewerWidget()
    # viewer.load_pdf("/Path/To/Your/TestDocument.pdf")
    viewer.next_page()
    # viewer.page_spacing = 0
    # viewer.side_margins = 0
    viewer.resize(1000, 700)
    viewer.show()

    sys.exit(app.exec())
