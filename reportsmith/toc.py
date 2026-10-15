"""Shared table-of-contents helpers used by the renderers.

Every renderer lists the same entries: each :class:`Section` title and each
explicit :class:`Heading` in document order, filtered by the TOC's depth.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterator, Union

from .elements import Container, Element, Heading, Section, TableOfContents
from .inline import Inline, InlineContent

if TYPE_CHECKING:
    from .report import Report


@dataclass
class TocEntry:
    element: Union[Section, Heading]
    depth: int  # 1 = top-level section
    parts: list[InlineContent]
    children: list["TocEntry"] = field(default_factory=list)


def plain_text(parts: list[InlineContent]) -> str:
    """Text of inline content; footnotes are dropped, since a footnote's
    text is the note rather than part of the sentence."""
    return "".join(
        p.text if isinstance(p, Inline) else str(p)
        for p in parts
        if not (isinstance(p, Inline) and p.style == "footnote")
    )


def iter_headings(container: Container) -> Iterator[Union[Section, Heading]]:
    """Yield every Section and Heading in document order."""
    for child in container.children:
        if isinstance(child, Section):
            yield child
            yield from iter_headings(child)
        elif isinstance(child, Heading):
            yield child


def find_tocs(container: Container) -> Iterator[TableOfContents]:
    for child in container.children:
        if isinstance(child, TableOfContents):
            yield child
        elif isinstance(child, Section):
            yield from find_tocs(child)


def heading_depth(el: Element) -> int:
    # The report title is level 1, so top-level sections (level 2) are
    # depth 1; an explicit level-1 heading is treated as top-level too.
    level = el._level if isinstance(el, Section) else el.level
    return max(level - 1, 1)


def collect_entries(report: "Report", depth: int) -> list[TocEntry]:
    """Flat list of TOC entries up to ``depth``, in document order."""
    entries = []
    for el in iter_headings(report):
        d = heading_depth(el)
        if d <= depth:
            parts = el.title_parts if isinstance(el, Section) else el.parts
            entries.append(TocEntry(el, d, parts))
    return entries


def build_tree(entries: list[TocEntry]) -> list[TocEntry]:
    """Nest flat entries by depth; a skipped level nests under the nearest
    shallower entry rather than creating empty intermediate levels."""
    roots: list[TocEntry] = []
    stack: list[TocEntry] = []
    for entry in entries:
        entry.children = []
        while stack and stack[-1].depth >= entry.depth:
            stack.pop()
        (stack[-1].children if stack else roots).append(entry)
        stack.append(entry)
    return roots


class Slugger:
    """GitHub-compatible heading anchors (mirrors github-slugger), with
    ``-1``, ``-2``, ... suffixes for repeated headings."""

    def __init__(self) -> None:
        self._seen: dict[str, int] = {}

    def slug(self, text: str) -> str:
        base = re.sub(r"[^\w\- ]", "", text.lower()).replace(" ", "-")
        slug = base
        while slug in self._seen:
            self._seen[base] += 1
            slug = f"{base}-{self._seen[base]}"
        self._seen[slug] = 0
        return slug


def heading_anchors(report: "Report") -> dict[int, str]:
    """Map ``id(element)`` to a unique anchor for every heading.

    The report title is slugged first so anchors match what GitHub (and
    most Markdown viewers) generate for the rendered document.
    """
    slugger = Slugger()
    slugger.slug(report.title)
    anchors = {}
    for el in iter_headings(report):
        parts = el.title_parts if isinstance(el, Section) else el.parts
        anchors[id(el)] = slugger.slug(plain_text(parts))
    return anchors
