"""Inline (span-level) content: bold, italic, code, links.

Block elements accept either a plain string or a list mixing strings and
:class:`Inline` objects, so the same content renders correctly in both
Markdown and HTML.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence, Union

InlineContent = Union[str, "Inline"]
# What users may pass wherever inline text is expected.
TextLike = Union[str, "Inline", Sequence[InlineContent]]


@dataclass(frozen=True)
class Inline:
    """A span of text with a style: 'bold', 'italic', 'code', or 'link'."""

    style: str
    text: str
    href: str = ""


def bold(text: str) -> Inline:
    """Bold text span."""
    return Inline("bold", text)


def italic(text: str) -> Inline:
    """Italic text span."""
    return Inline("italic", text)


def code(text: str) -> Inline:
    """Inline code span."""
    return Inline("code", text)


def link(text: str, href: str) -> Inline:
    """Hyperlink span."""
    return Inline("link", text, href)


def normalize(content: TextLike) -> list[InlineContent]:
    """Coerce any accepted text input into a flat list of str/Inline parts."""
    if isinstance(content, (str, Inline)):
        return [content]
    if isinstance(content, Iterable):
        parts: list[InlineContent] = []
        for item in content:
            if isinstance(item, (str, Inline)):
                parts.append(item)
            else:
                parts.append(str(item))
        return parts
    return [str(content)]
