(user.widgets.pdf_viewer_widget)=

# PDF Viewer Widget

````{tab} Overview

The PDF Viewer Widget is a versatile tool designed for displaying and navigating PDF documents within your BEC applications. Directly integrated with the `BEC` framework, it provides a full-featured PDF viewing experience with zoom controls, page navigation, and customizable display options.

## Key Features:
- **Flexible Integration**: The widget can be integrated into [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BEC Designer`.
- **Full PDF Support**: Display any PDF document with full rendering support through Qt's PDF rendering engine.
- **Navigation Controls**: Built-in toolbar with page navigation, zoom controls, and document status indicators.
- **Customizable Display**: Adjustable page spacing, margins, and zoom levels for optimal viewing experience.
- **Document Management**: Load different PDF files dynamically during runtime with proper error handling.

## User Interface Components:
- **Toolbar**: Contains all navigation and zoom controls
  - Previous/Next page buttons
  - Page number input field with total page count
  - First/Last page navigation buttons
  - Zoom in/out buttons
  - Fit to width/page buttons
  - Reset zoom button
- **PDF View Area**: Main display area for the PDF content

````

````{tab} Examples - CLI

`PdfViewerWidget` can be embedded in [`BECDockArea`](user.widgets.bec_dock_area), or used as an individual component in your application through `BEC Designer`. The command-line API is the same for all cases.

## Example 1 - Basic PDF Loading

In this example, we demonstrate how to add a `PdfViewerWidget` to a [`BECDockArea`](user.widgets.bec_dock_area) and load a PDF document.

```python
# Add a new dock with PDF viewer widget
dock_area = gui.new()
pdf_viewer = dock_area.new().new(gui.available_widgets.PdfViewerWidget)

# Load a PDF file
pdf_viewer.load_pdf("/path/to/your/document.pdf")
```

## Example 2 - Customizing Display Properties

This example shows how to customize the display properties of the PDF viewer for better presentation.

```python
# Create PDF viewer
pdf_viewer = gui.new().new().new(gui.available_widgets.PdfViewerWidget)

# Load PDF document
pdf_viewer.load_pdf("/path/to/report.pdf")
pdf_viewer.toggle_continuous_scroll(True)  # Enable continuous scroll mode

# Customize display properties
pdf_viewer.page_spacing = 20  # Increase spacing between pages
pdf_viewer.side_margins = 50  # Add horizontal margins

# Navigate to specific page
pdf_viewer.jump_to_page(5)  # Go to page 5
```

## Example 3 - Navigation and Zoom Controls

The PDF viewer provides programmatic access to all navigation and zoom functionality.

```python
# Create and load PDF
pdf_viewer = gui.new().new().new(gui.available_widgets.PdfViewerWidget)
pdf_viewer.load_pdf("/path/to/manual.pdf")

# Navigation examples
pdf_viewer.go_to_first_page()  # Go to first page
pdf_viewer.go_to_last_page()   # Go to last page
pdf_viewer.jump_to_page(10)    # Jump to specific page

# Zoom controls
pdf_viewer.zoom_in()           # Increase zoom
pdf_viewer.zoom_out()          # Decrease zoom
pdf_viewer.fit_to_width()      # Fit document to window width
pdf_viewer.fit_to_page()       # Fit entire page to window
pdf_viewer.reset_zoom()        # Reset to 100% zoom

# Check current status
current_page = pdf_viewer.current_page
print(f"Currently viewing page {current_page}")
```

## Example 4 - Dynamic Document Loading

This example demonstrates how to switch between different PDF documents dynamically.

```python
# Create PDF viewer
pdf_viewer = gui.new().new().new(gui.available_widgets.PdfViewerWidget)

# Load first document
pdf_viewer.load_pdf("/path/to/document1.pdf")

# Or simply set the current file path
pdf_viewer.current_file_path = "/path/to/document2.pdf"
# This automatically loads the new document

# Check which file is currently loaded
current_file = pdf_viewer.current_file_path
print(f"Currently viewing: {current_file}")
```

````

````{tab} API
```{eval-rst}  
.. autoclass:: bec_widgets.cli.client.PdfViewerWidget
   :members:
   :show-inheritance:
```
````
