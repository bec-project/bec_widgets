from bec_widgets.widgets.control.scan_control.scan_docstring import (
    render_scan_docstring_html,
    render_scan_tooltip_html,
)


def test_render_scan_docstring_html_formats_google_sections():
    docstring = """Run a line scan over one motor.

    The motor is moved through evenly spaced positions.

    Args:
        device (DeviceBase | str): Device to move.
        start (float): Initial position.
            Expressed in the device's configured engineering units.
            Constraint: must be below the stop position.

    Returns:
        ScanReport: Handle for the submitted scan.

    Raises:
        ValueError: If the requested range is invalid.

    Examples:
        >>> scans.line_scan(samx, -1, 1, steps=11)
    """

    rendered = render_scan_docstring_html("line_scan", docstring)

    assert "<h1>line_scan</h1>" in rendered
    assert "<h2>Arguments</h2>" in rendered
    assert "<code>device</code>" in rendered
    assert "DeviceBase | str" in rendered
    assert "configured engineering units" in rendered
    assert "Constraint: must be below" in rendered
    assert "<code>Constraint</code>" not in rendered
    assert "<h2>Returns</h2>" in rendered
    assert "<h2>Raises</h2>" in rendered
    assert "<h2>Examples</h2>" in rendered
    assert "<pre>&gt;&gt;&gt; scans.line_scan" in rendered


def test_render_scan_tooltip_html_is_compact_and_informative():
    docstring = """Run a line scan.

    Args:
        device (DeviceBase | str): Device to move.
        start (float): Initial position.

    Examples:
        >>> scans.line_scan(samx, 0, 1)
    """

    rendered = render_scan_tooltip_html("line_scan", docstring)

    assert "<b>line_scan</b>" in rendered
    assert "Run a line scan." in rendered
    assert "device: DeviceBase | str" in rendered
    assert "start: float" in rendered
    assert "Examples" not in rendered
    assert "full documentation" in rendered


def test_scan_docstring_renderers_escape_untrusted_content():
    docstring = "Use <script>alert('x')</script> safely."

    full = render_scan_docstring_html("<scan>", docstring)
    tooltip = render_scan_tooltip_html("<scan>", docstring)

    for rendered in (full, tooltip):
        assert "&lt;scan&gt;" in rendered
        assert "&lt;script&gt;" in rendered
        assert "<script>" not in rendered


def test_trailing_prose_after_args_is_not_folded_into_fields():
    docstring = (
        "Run a scan.\n\n"
        "Args:\n"
        "    device (DeviceBase): Device to move.\n\n"
        "The scan aborts when limits are exceeded."
    )

    rendered = render_scan_docstring_html("scan", docstring)

    assert "<p>The scan aborts when limits are exceeded.</p>" in rendered
    assert "Device to move. The scan aborts" not in rendered


def test_unindented_colon_prose_is_not_parsed_as_field():
    docstring = (
        "Run a scan.\n\n"
        "Args:\n"
        "    device (DeviceBase): Device to move.\n\n"
        "Limit handling: the scan aborts."
    )

    rendered = render_scan_docstring_html("scan", docstring)
    tooltip = render_scan_tooltip_html("scan", docstring)

    assert "<code>Limit handling</code>" not in rendered
    assert "<p>Limit handling: the scan aborts.</p>" in rendered
    assert "Limit handling" not in tooltip


def test_typed_field_type_is_not_greedy():
    docstring = "Run a scan.\n\nArgs:\n    steps (int): Number of steps (per axis): must be > 0"

    rendered = render_scan_docstring_html("scan", docstring)
    tooltip = render_scan_tooltip_html("scan", docstring)

    assert "<small>int</small>" in rendered
    assert "Number of steps (per axis): must be &gt; 0" in rendered
    assert "steps: int" in tooltip


def test_scan_docstring_renderers_handle_plain_and_missing_docs():
    plain = render_scan_docstring_html("count", "Count detector readings.")
    missing = render_scan_tooltip_html("count", None)

    assert "<p>Count detector readings.</p>" in plain
    assert "No documentation is available for this scan." in missing
