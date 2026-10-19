"""Caption numbering and cross-reference resolution shared by the renderers.

Figures and tables with a caption are numbered separately ("Figure 1",
"Table 1", ...) in document order, wherever they sit (sections, callouts).
A label maps to its item so :func:`~reportsmith.ref` can name it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, Union

from .elements import Container, Element, Figure, Table

if TYPE_CHECKING:
    from .report import Report

#: Display names, and the prefixes used for HTML ids and LaTeX labels.
KIND_NAMES = {"figure": "Figure", "table": "Table"}
LATEX_PREFIXES = {"figure": "fig", "table": "tab"}

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
    def __init__(self, report: "Report"):
        self._numbers: dict[int, int] = {}  # id(element) -> number
        self._labels: dict[str, tuple[str, int]] = {}  # label -> (kind, number)
        counters = {"figure": 0, "table": 0}
        for el in iter_elements(report):
            if not isinstance(el, (Figure, Table)) or not el.caption:
                continue
            kind = kind_of(el)
            counters[kind] += 1
            self._numbers[id(el)] = counters[kind]
            if el.label:
                if el.label in self._labels:
                    raise ValueError(f"Duplicate label {el.label!r}")
                self._labels[el.label] = (kind, counters[kind])

    def number(self, el: Captioned) -> int:
        """The item's number, or 0 if it is not numbered (no caption)."""
        return self._numbers.get(id(el), 0)

    def caption_label(self, el: Captioned) -> str:
        """``"Figure 2"`` / ``"Table 1"``, or ``""`` for unnumbered items."""
        n = self.number(el)
        return f"{KIND_NAMES[kind_of(el)]} {n}" if n else ""

    def resolve(self, label: str) -> tuple[str, int]:
        """``(kind, number)`` for a label; ``ValueError`` if it doesn't exist."""
        try:
            return self._labels[label]
        except KeyError:
            raise ValueError(
                f"ref({label!r}) points to no captioned figure or table with that label"
            ) from None

    def ref_text(self, label: str, text: str = "") -> str:
        kind, n = self.resolve(label)
        return text or f"{KIND_NAMES[kind]} {n}"
