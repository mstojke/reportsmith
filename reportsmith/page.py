"""Running headers and footers: template parsing shared by the renderers.

A header or footer is a string (centred) or a ``(left, centre, right)``
tuple of strings. Templates may contain ``{page}``, ``{pages}``,
``{title}``, ``{subtitle}``, ``{author}`` and ``{date}``; write ``{{`` and
``}}`` for literal braces.
"""

from __future__ import annotations

import string
from typing import TYPE_CHECKING, Optional, Sequence, Union

if TYPE_CHECKING:
    from .report import Report

#: Placeholders filled per page by each renderer.
PAGE_FIELDS = ("page", "pages")
#: Placeholders filled from the report's metadata.
REPORT_FIELDS = ("title", "subtitle", "author", "date")

Band = tuple[str, str, str]  # left, centre, right
#: A segment of a filled template: ("text", literal) / ("page", "") / ("pages", "").
Segment = tuple[str, str]


def parse_band(value: Union[None, str, Sequence[str]], what: str) -> Optional[Band]:
    """Normalize a header/footer argument to ``(left, centre, right)``."""
    if value is None:
        return None
    if isinstance(value, str):
        band: Band = ("", value, "")
    else:
        parts = list(value)
        if len(parts) != 3 or not all(isinstance(p, str) for p in parts):
            raise ValueError(f"{what} must be a string or a (left, centre, right) tuple of strings")
        band = (parts[0], parts[1], parts[2])
    for text in band:
        _fields(text, what)  # validate early
    return band if any(band) else None


def _fields(text: str, what: str) -> list[tuple[str, Optional[str]]]:
    try:
        parsed = list(string.Formatter().parse(text))
    except ValueError as exc:
        raise ValueError(f"Invalid {what} template {text!r}: {exc}") from None
    for _, field, spec, conversion in parsed:
        if field is None:
            continue
        if field not in PAGE_FIELDS + REPORT_FIELDS:
            known = ", ".join("{" + f + "}" for f in PAGE_FIELDS + REPORT_FIELDS)
            raise ValueError(f"Unknown placeholder {{{field}}} in {what}; use {known}")
        if spec or conversion:
            raise ValueError(f"Placeholders in {what} can't have a format or conversion: {text!r}")
    return [(literal, field) for literal, field, _, _ in parsed]


def segments(text: str, report: "Report") -> list[Segment]:
    """Split a template into literal text (report fields filled in) and
    ``page`` / ``pages`` markers for the renderer to fill."""
    out: list[Segment] = []

    def add_text(value: str) -> None:
        if not value:
            return
        if out and out[-1][0] == "text":
            out[-1] = ("text", out[-1][1] + value)
        else:
            out.append(("text", value))

    for literal, field in _fields(text, "template"):
        add_text(literal)
        if field in PAGE_FIELDS:
            out.append((field, ""))
        elif field is not None:
            add_text(str(getattr(report, field)))
    return out
