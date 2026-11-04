"""Numbering and cross-reference resolution shared by the renderers.

Figures and tables with a caption are numbered separately ("Figure 1",
"Table 1", ...) in document order, wherever they sit (sections, callouts).
Sections and headings are numbered "1", "1.1", ... when the report asks for
it (``Report(section_numbers=...)``), the same way LaTeX numbers them. A
label maps to its figure, table or section so :func:`~reportsmith.ref` can
name it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, Optional, Union

from .elements import Container, Element, Figure, Heading, Section, Table
from .toc import heading_depth, iter_headings, plain_text

if TYPE_CHECKING:
    from .report import Report

#: Display names, and the prefixes used for HTML ids and LaTeX labels.
KIND_NAMES = {"figure": "Figure", "table": "Table", "section": "Section"}
HTML_PREFIXES = {"figure": "fig", "table": "tbl", "section": "sec"}
LATEX_PREFIXES = {"figure": "fig", "table": "tab", "section": "sec"}

Captioned = Union[Figure, Table]


def iter_elements(container: Container) -> Iterator[Element]:
    """Every element in document order, descending into sections and callouts."""
    for child in container.children:
        yield child
        if isinstance(child, Container):
            yield from iter_elements(child)


def kind_of(el: Captioned) -> str:
    return "figure" if isinstance(el, Figure) else "table"


class Numbering:
    """Numbers for one render of a report.

    ``section_depth`` overrides ``report.section_numbers`` (the LaTeX
    renderer's ``numbered=True`` uses it).
    """

    def __init__(self, report: "Report", section_depth: Optional[int] = None):
        self._numbers: dict[int, int] = {}  # id(figure/table) -> number
        self._sections: dict[int, str] = {}  # id(section/heading) -> "2.1"
        # label -> (kind, number); a section's "number" may be "" (unnumbered)
        self._labels: dict[str, tuple[str, Union[int, str]]] = {}
        self._titles: dict[str, str] = {}  # section label -> plain title

        depth = report.section_numbers if section_depth is None else section_depth
        if depth:
            counters = [0] * 6
            for heading in iter_headings(report):
                d = heading_depth(heading)
                counters[d - 1] += 1
                counters[d:] = [0] * (6 - d)
                if d <= depth:
                    self._sections[id(heading)] = ".".join(map(str, counters[:d]))

        figures_tables = {"figure": 0, "table": 0}
        for el in iter_elements(report):
            if isinstance(el, Section) and el.label:
                self._add_label(el.label, "section", self._sections.get(id(el), ""))
                self._titles[el.label] = plain_text(el.title_parts)
            elif isinstance(el, (Figure, Table)) and el.caption:
                kind = kind_of(el)
                figures_tables[kind] += 1
                self._numbers[id(el)] = figures_tables[kind]
                if el.label:
                    self._add_label(el.label, kind, figures_tables[kind])

    def _add_label(self, label: str, kind: str, number: Union[int, str]) -> None:
        if label in self._labels:
            raise ValueError(
                f"Duplicate label {label!r} (when merging reports, "
                "extend(..., label_prefix=...) keeps labels unique)"
            )
        self._labels[label] = (kind, number)

    def number(self, el: Captioned) -> int:
        """The figure/table number, or 0 if it is not numbered (no caption)."""
        return self._numbers.get(id(el), 0)

    def caption_label(self, el: Captioned) -> str:
        """``"Figure 2"`` / ``"Table 1"``, or ``""`` for unnumbered items."""
        n = self.number(el)
        return f"{KIND_NAMES[kind_of(el)]} {n}" if n else ""

    def section_number(self, el: Union[Section, Heading]) -> str:
        """``"2.1"`` for a numbered section/heading, else ``""``."""
        return self._sections.get(id(el), "")

    @property
    def sections_numbered(self) -> bool:
        return bool(self._sections)

    def resolve(self, label: str) -> tuple[str, Union[int, str]]:
        """``(kind, number)`` for a label; ``ValueError`` if it doesn't exist."""
        try:
            return self._labels[label]
        except KeyError:
            raise ValueError(
                f"ref({label!r}) points to no section, or captioned figure or table, "
                "with that label"
            ) from None

    def ref_text(self, label: str, text: str = "") -> str:
        """"Figure 2", "Table 1", "Section 2.1" — or, for an unnumbered
        section, its title — unless ``text`` is given."""
        kind, number = self.resolve(label)
        if text:
            return text
        if kind == "section" and not number:
            return self._titles[label]
        return f"{KIND_NAMES[kind]} {number}"
