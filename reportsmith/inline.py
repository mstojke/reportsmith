"""Inline (span-level) content: bold, italic, code, links, strikethrough,
subscript, superscript and footnotes.

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
    """A span of text with a style: 'bold', 'italic', 'code', 'link',
    'strike', 'sub', 'sup', 'footnote' (whose text is the note itself) or
    'ref' (whose href is the label it refers to)."""

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


def strike(text: str) -> Inline:
    """Strikethrough text span."""
    return Inline("strike", text)


def sub(text: str) -> Inline:
    """Subscript text span, e.g. the 2 in H2O."""
    return Inline("sub", text)


def sup(text: str) -> Inline:
    """Superscript text span, e.g. the 2 in m2."""
    return Inline("sup", text)


def footnote(text: str) -> Inline:
    """A footnote: renders as a numbered marker where it is placed, with
    ``text`` shown as the note (numbered in document order)."""
    return Inline("footnote", text)


def ref(label: str, text: str = "") -> Inline:
    """A cross-reference to the figure or table with this ``label``.

    Renders as "Figure 2" / "Table 1" (linked where the format allows), or
    as ``text`` if given.
    """
    return Inline("ref", text, label)


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
