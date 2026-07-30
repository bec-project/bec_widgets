"""Rendering helpers for scan documentation."""

from __future__ import annotations

import html
import inspect
import re
import textwrap

_SECTION_TITLES = {
    "args": "Arguments",
    "arguments": "Arguments",
    "parameters": "Arguments",
    "keyword args": "Keyword arguments",
    "keyword arguments": "Keyword arguments",
    "kwargs": "Keyword arguments",
    "attributes": "Attributes",
    "returns": "Returns",
    "yields": "Yields",
    "raises": "Raises",
    "examples": "Examples",
    "example": "Examples",
    "notes": "Notes",
    "note": "Notes",
    "warnings": "Warnings",
    "warning": "Warnings",
    "see also": "See also",
}
_FIELD_SECTIONS = {"Arguments", "Keyword arguments", "Attributes", "Returns", "Yields", "Raises"}
_TYPED_FIELD_PATTERN = re.compile(r"^(.+?)\s+\((.+?)\)\s*:\s*(.*)$")
_FIELD_PATTERN = re.compile(r"^([^:]+)\s*:\s*(.*)$")
_TOOLTIP_SUMMARY_LIMIT = 320
_TOOLTIP_ARGUMENT_LIMIT = 8


def _split_blocks(docstring: str) -> list[tuple[str | None, list[str]]]:
    """Split a docstring into titled sections and untitled prose blocks, in order."""
    blocks: list[tuple[str | None, list[str]]] = [(None, [])]

    for line in inspect.cleandoc(docstring).splitlines():
        stripped = line.strip()
        unindented = line == line.lstrip()
        title = _SECTION_TITLES.get(stripped.removesuffix(":").lower())
        if title is not None and unindented:
            blocks.append((title, []))
            continue
        if blocks[-1][0] is not None and stripped and unindented:
            # Unindented prose ends the indented section body and belongs to the surrounding text.
            blocks.append((None, []))
        blocks[-1][1].append(line)

    return blocks


def _paragraph_text(lines: list[str]) -> str:
    text = textwrap.dedent("\n".join(lines)).strip()
    if not text:
        return ""
    first_paragraph = re.split(r"\n\s*\n", text, maxsplit=1)[0]
    return " ".join(line.strip() for line in first_paragraph.splitlines())


def _paragraphs_to_html(lines: list[str]) -> str:
    text = textwrap.dedent("\n".join(lines)).strip()
    if not text:
        return ""

    paragraphs = re.split(r"\n\s*\n", text)
    return "".join(
        f"<p>{html.escape(' '.join(line.strip() for line in paragraph.splitlines()))}</p>"
        for paragraph in paragraphs
        if paragraph.strip()
    )


def _parse_fields(lines: list[str]) -> list[tuple[str, str | None, str]]:
    text = textwrap.dedent("\n".join(lines)).strip()
    if not text:
        return []

    fields: list[tuple[str, str | None, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if raw_line == raw_line.lstrip():
            match = _TYPED_FIELD_PATTERN.match(line)
            if match:
                fields.append(
                    (match.group(1).strip(), match.group(2).strip(), match.group(3).strip())
                )
                continue

            match = _FIELD_PATTERN.match(line)
            if match:
                fields.append((match.group(1).strip(), None, match.group(2).strip()))
                continue

        if not fields:
            return []
        name, field_type, description = fields[-1]
        fields[-1] = (name, field_type, " ".join(filter(None, (description, line))))

    return fields


def _fields_to_html(fields: list[tuple[str, str | None, str]]) -> str:
    rows = []
    for name, field_type, description in fields:
        type_html = (
            f"<br><small>{html.escape(field_type)}</small>" if field_type is not None else ""
        )
        rows.append(
            "<tr>"
            f'<td valign="top"><b><code>{html.escape(name)}</code></b>{type_html}</td>'
            f'<td valign="top">{html.escape(description)}</td>'
            "</tr>"
        )
    return '<table cellspacing="6" cellpadding="2">' + "".join(rows) + "</table>"


def render_scan_docstring_html(scan_name: str, docstring: str | None) -> str:
    """Render a Google-style scan docstring as theme-neutral, safe HTML."""
    title = html.escape(scan_name)
    if not isinstance(docstring, str) or not docstring.strip():
        return f"<h1>{title}</h1><p><i>No documentation is available for this scan.</i></p>"

    body = [f"<h1>{title}</h1>"]
    for section_title, lines in _split_blocks(docstring):
        if section_title is None:
            body.append(_paragraphs_to_html(lines))
            continue
        body.append(f"<h2>{html.escape(section_title)}</h2>")
        if section_title == "Examples":
            example = textwrap.dedent("\n".join(lines)).strip()
            if example:
                body.append(f"<pre>{html.escape(example)}</pre>")
            continue

        fields = _parse_fields(lines) if section_title in _FIELD_SECTIONS else []
        body.append(_fields_to_html(fields) if fields else _paragraphs_to_html(lines))

    return "".join(body)


def render_scan_tooltip_html(scan_name: str, docstring: str | None) -> str:
    """Render a compact scan summary for combo-box hover tooltips."""
    title = html.escape(scan_name)
    if not isinstance(docstring, str) or not docstring.strip():
        return f"<b>{title}</b><br><i>No documentation is available for this scan.</i>"

    blocks = _split_blocks(docstring)
    summary = _paragraph_text(blocks[0][1])
    if len(summary) > _TOOLTIP_SUMMARY_LIMIT:
        summary = summary[: _TOOLTIP_SUMMARY_LIMIT - 1].rstrip() + "…"

    body = [f"<b>{title}</b>"]
    if summary:
        body.append(f"<p>{html.escape(summary)}</p>")

    parameters = []
    for section_title, lines in blocks:
        if section_title in {"Arguments", "Keyword arguments"}:
            parameters.extend(_parse_fields(lines))
    if parameters:
        labels = [
            f"{name}: {field_type}" if field_type else name
            for name, field_type, _description in parameters[:_TOOLTIP_ARGUMENT_LIMIT]
        ]
        if len(parameters) > _TOOLTIP_ARGUMENT_LIMIT:
            labels.append("…")
        body.append(f"<p><b>Parameters:</b> {html.escape(', '.join(labels))}</p>")

    body.append("<small>Use the info button for full documentation.</small>")
    return "".join(body)
