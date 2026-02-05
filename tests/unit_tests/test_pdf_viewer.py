import pytest
from qtpy.QtPdf import QPdfDocument
from qtpy.QtPdfWidgets import QPdfView

from bec_widgets.widgets.utility.pdf_viewer.pdf_viewer import PdfViewerWidget


@pytest.fixture
def pdf_viewer_widget(qtbot, mocked_client):
    """Create a PDF viewer widget for testing."""
    widget = PdfViewerWidget(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.cleanup()


@pytest.fixture
def temp_pdf_file(tmpdir):
    """Create a minimal 3-page PDF file for testing."""
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R 5 0 R 7 0 R] /Count 3 >>
endobj

3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Page 1) Tj ET
endstream
endobj

5 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 6 0 R >>
endobj
6 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Page 2) Tj ET
endstream
endobj

7 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 8 0 R >>
endobj
8 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Page 3) Tj ET
endstream
endobj

9 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj

xref
0 10
0000000000 65535 f 
0000000010 00000 n 
0000000060 00000 n 
0000000125 00000 n 
0000000205 00000 n 
0000000282 00000 n 
0000000362 00000 n 
0000000439 00000 n 
0000000519 00000 n 
0000000596 00000 n 
trailer
<< /Size 10 /Root 1 0 R >>
startxref
675
%%EOF
"""

    pdf_path = tmpdir.join("test_3page.pdf")
    pdf_path.write_binary(pdf_content)
    return str(pdf_path)


@pytest.fixture
def temp_pdf_file_2(tmpdir):
    """Create a second minimal temporary PDF file for testing."""
    # Create a minimal PDF content for testing
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>stream
BT
/F1 12 Tf
100 700 Td
(Second Test PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000307 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
398
%%EOF"""
    # Create temporary PDF file using tmpdir
    pdf_file = tmpdir.join("test2.pdf")
    pdf_file.write_binary(pdf_content)
    return str(pdf_file)


def test_initialization(pdf_viewer_widget: PdfViewerWidget):
    """Test that the widget initializes correctly."""
    widget = pdf_viewer_widget

    # Check basic widget setup
    assert widget is not None
    assert hasattr(widget, "pdf_view")
    assert hasattr(widget, "toolbar")
    assert hasattr(widget, "_pdf_document")

    # Check initial state
    assert widget._current_file_path is None
    assert widget._page_spacing == 5
    assert widget._side_margins == 10

    # Check PDF view setup
    assert isinstance(widget.pdf_view, QPdfView)
    assert widget.pdf_view.zoomMode() == QPdfView.ZoomMode.FitToWidth

    # Check PDF document setup
    assert isinstance(widget._pdf_document, QPdfDocument)


def test_toolbar_setup(pdf_viewer_widget: PdfViewerWidget):
    """Test that toolbar is set up with all expected actions."""
    widget = pdf_viewer_widget
    toolbar = widget.toolbar

    # Check that all expected actions exist
    expected_actions = [
        "open_file",
        "zoom_in",
        "zoom_out",
        "fit_width",
        "fit_page",
        "reset_zoom",
        "continuous_scroll",
        "prev_page",
        "next_page",
        "page_jump",
    ]

    for action_name in expected_actions:
        assert toolbar.components.exists(action_name), f"Action {action_name} not found"


def test_load_pdf_file(qtbot, pdf_viewer_widget: PdfViewerWidget, temp_pdf_file, temp_pdf_file_2):
    """Test loading a PDF file into the viewer."""
    widget = pdf_viewer_widget

    # Load the temporary PDF file
    widget.load_pdf(temp_pdf_file)
    qtbot.wait(100)  # Wait for loading

    # Check that the document is loaded
    assert widget._pdf_document.status() == QPdfDocument.Status.Ready
    assert widget._pdf_document.pageCount() > 0
    assert widget._current_file_path == temp_pdf_file

    # Load a second PDF file to test reloading
    widget.load_pdf(temp_pdf_file_2)
    qtbot.wait(100)  # Wait for loading

    # Check that the new document is loaded
    assert widget._pdf_document.status() == QPdfDocument.Status.Ready
    assert widget._pdf_document.pageCount() > 0
    assert widget._current_file_path == temp_pdf_file_2

    assert widget.current_file_path == temp_pdf_file_2

    widget.current_file_path = temp_pdf_file
    qtbot.wait(100)  # Wait for loading
    assert widget.current_file_path == temp_pdf_file


def test_load_invalid_pdf_file(qtbot, pdf_viewer_widget: PdfViewerWidget, tmpdir):
    """Test loading an invalid PDF file into the viewer."""
    widget = pdf_viewer_widget

    # Try to open a non-existent file
    invalid_pdf_file = tmpdir.join("non_existent.pdf")

    # Attempt to load the invalid PDF file
    with pytest.raises(FileNotFoundError):
        widget.load_pdf(str(invalid_pdf_file), _override_slot_params={"raise_error": True})


def test_page_navigation(qtbot, pdf_viewer_widget: PdfViewerWidget, temp_pdf_file):
    """Test page navigation functionality."""
    widget = pdf_viewer_widget

    # Load the temporary PDF file
    with qtbot.waitSignal(widget.document_ready, timeout=2000):
        widget.load_pdf(temp_pdf_file)

    # Check initial page
    assert widget.current_page == 1
    total_pages = widget._pdf_document.pageCount()
    assert total_pages >= 1

    # Navigate to next page
    widget.next_page()
    qtbot.wait(300)
    assert widget.current_page == 2

    # Navigate to previous page
    widget.previous_page()
    qtbot.wait(300)
    assert widget.current_page == 1

    # Jump to last page
    widget.jump_to_page(total_pages)
    qtbot.wait(300)
    assert widget.current_page == total_pages

    widget.jump_to_page(1)
    qtbot.wait(300)
    assert widget.current_page == 1

    widget.jump_to_page(2)
    qtbot.wait(300)
    assert widget.current_page == 2

    widget.go_to_last_page()
    qtbot.wait(300)
    assert widget.current_page == total_pages

    widget.go_to_first_page()
    qtbot.wait(300)
    assert widget.current_page == 1

    widget.page_input.setText(str(total_pages + 10))
    widget.page_input.returnPressed.emit()
    qtbot.wait(100)
    assert widget.current_page == total_pages


def test_zoom_controls(qtbot, pdf_viewer_widget: PdfViewerWidget, temp_pdf_file):
    """Test zoom in, zoom out, fit width, fit page, and reset zoom functionality."""
    widget = pdf_viewer_widget

    # Load the temporary PDF file
    with qtbot.waitSignal(widget.document_ready, timeout=2000):
        widget.load_pdf(temp_pdf_file)

    # Initial zoom mode should be FitToWidth
    assert widget.pdf_view.zoomMode() == QPdfView.ZoomMode.FitToWidth

    # Zoom in
    initial_zoom = widget.pdf_view.zoomFactor()
    widget.zoom_in()
    qtbot.wait(100)
    assert widget.pdf_view.zoomFactor() > initial_zoom

    # Zoom out
    zoom_after_in = widget.pdf_view.zoomFactor()
    widget.zoom_out()
    qtbot.wait(100)
    assert widget.pdf_view.zoomFactor() < zoom_after_in

    # Fit to page
    widget.fit_to_page()
    qtbot.wait(100)
    assert widget.pdf_view.zoomMode() == QPdfView.ZoomMode.FitInView

    # Fit to width
    widget.fit_to_width()
    qtbot.wait(100)
    assert widget.pdf_view.zoomMode() == QPdfView.ZoomMode.FitToWidth

    # Reset zoom
    widget.reset_zoom()
    qtbot.wait(100)
    assert widget.pdf_view.zoomMode() == QPdfView.ZoomMode.Custom


def test_page_spacing_and_margins(qtbot, pdf_viewer_widget: PdfViewerWidget, temp_pdf_file):
    """Test setting page spacing and side margins."""
    widget = pdf_viewer_widget

    # Load the temporary PDF file
    with qtbot.waitSignal(widget.document_ready, timeout=2000):
        widget.load_pdf(temp_pdf_file)

    # Set and verify page spacing
    widget.page_spacing = 20
    assert widget.page_spacing == 20

    # Set and verify side margins
    widget.side_margins = 30
    assert widget.side_margins == 30


def test_toggle_continuous_scroll(qtbot, pdf_viewer_widget: PdfViewerWidget, temp_pdf_file):
    """Test toggling continuous scroll mode."""
    widget = pdf_viewer_widget

    # Load the temporary PDF file
    with qtbot.waitSignal(widget.document_ready, timeout=2000):
        widget.load_pdf(temp_pdf_file)

    # Initial mode should be single page
    assert widget.pdf_view.pageMode() == QPdfView.PageMode.SinglePage

    # Toggle to continuous scroll
    widget.toggle_continuous_scroll(True)
    qtbot.wait(100)
    assert widget.pdf_view.pageMode() == QPdfView.PageMode.MultiPage

    # Toggle back to single page
    widget.toggle_continuous_scroll(False)
    qtbot.wait(100)
    assert widget.pdf_view.pageMode() == QPdfView.PageMode.SinglePage

    widget.jump_to_page(2)
    qtbot.wait(100)
    assert widget.current_page == 2
