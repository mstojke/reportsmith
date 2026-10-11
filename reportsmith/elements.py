"""Block-level report elements.

Every element knows nothing about output formats; rendering lives in
``reportsmith.renderers``. ``Section`` is a container element that also mixes in
the builder API, so content can be added to a report or any nested section
with the same methods.
"""

from __future__ import annotations

from typing import Optional, Sequence

from .inline import InlineContent, TextLike, normalize


class Element:
    """Base class for all block elements."""


class Heading(Element):
    def __init__(self, content: TextLike, level: int = 1):
        if not 1 <= level <= 6:
            raise ValueError(f"Heading level must be 1-6, got {level}")
        self.parts: list[InlineContent] = normalize(content)
        self.level = level


class Paragraph(Element):
    def __init__(self, content: TextLike):
        self.parts: list[InlineContent] = normalize(content)


class Quote(Element):
    def __init__(self, content: TextLike):
        self.parts: list[InlineContent] = normalize(content)


class CodeBlock(Element):
    def __init__(self, source: str, language: str = ""):
        self.source = source
        self.language = language


class ListElement(Element):
    """Bullet or numbered list. Items may be plain/inline text or nested lists."""

    def __init__(self, items: Sequence, ordered: bool = False):
        self.ordered = ordered
        self.items: list = []
        for item in items:
            if isinstance(item, ListElement):
                self.items.append(item)
            else:
                self.items.append(normalize(item))


class Table(Element):
    def __init__(
        self,
        headers: Sequence[TextLike],
        rows: Sequence[Sequence[TextLike]],
        caption: str = "",
        align: Optional[Sequence[str]] = None,
    ):
        self.headers = [normalize(h) for h in headers]
        self.rows = [[normalize(cell) for cell in row] for row in rows]
        width = len(self.headers)
        for i, row in enumerate(self.rows):
            if len(row) != width:
                raise ValueError(
                    f"Row {i} has {len(row)} cells, expected {width}"
                )
        self.caption = caption
        if align is not None:
            if len(align) != width:
                raise ValueError("align must have one entry per column")
            for a in align:
                if a not in ("left", "center", "right"):
                    raise ValueError(f"Invalid alignment: {a!r}")
        self.align = list(align) if align is not None else ["left"] * width


class Image(Element):
    def __init__(self, src: str, alt: str = "", title: str = ""):
        self.src = src
        self.alt = alt
        self.title = title


class HorizontalRule(Element):
    pass


class Raw(Element):
    """Format-specific passthrough content.

    Rendered verbatim when the output format matches (``"markdown"`` or
    ``"html"``); skipped otherwise. Use ``format="both"`` to always emit.
    """

    def __init__(self, content: str, format: str = "both"):
        if format not in ("markdown", "html", "both"):
            raise ValueError(f"format must be 'markdown', 'html' or 'both', got {format!r}")
        self.content = content
        self.format = format


class Container(Element):
    """Mixin providing the fluent builder API shared by Report and Section."""

    def __init__(self) -> None:
        self.children: list[Element] = []
        self._level = 0  # heading depth of this container

    def add(self, element: Element) -> "Container":
        """Append a pre-built element. Returns self for chaining."""
        self.children.append(element)
        return self

    def section(self, title: TextLike) -> "Section":
        """Add a nested section (usable as a context manager)."""
        section = Section(title, level=self._level + 1)
        self.children.append(section)
        return section

    def heading(self, content: TextLike, level: Optional[int] = None) -> "Container":
        """Add a heading. Level defaults to one below this container's title."""
        self.children.append(Heading(content, level or min(self._level + 1, 6)))
        return self

    def paragraph(self, content: TextLike) -> "Container":
        self.children.append(Paragraph(content))
        return self

    def quote(self, content: TextLike) -> "Container":
        self.children.append(Quote(content))
        return self

    def code(self, source: str, language: str = "") -> "Container":
        self.children.append(CodeBlock(source, language))
        return self

    def bullet_list(self, items: Sequence) -> "Container":
        self.children.append(ListElement(items, ordered=False))
        return self

    def numbered_list(self, items: Sequence) -> "Container":
        self.children.append(ListElement(items, ordered=True))
        return self

    def table(
        self,
        headers: Sequence[TextLike],
        rows: Sequence[Sequence[TextLike]],
        caption: str = "",
        align: Optional[Sequence[str]] = None,
    ) -> "Container":
        self.children.append(Table(headers, rows, caption, align))
        return self

    def image(self, src: str, alt: str = "", title: str = "") -> "Container":
        self.children.append(Image(src, alt, title))
        return self

    def horizontal_rule(self) -> "Container":
        self.children.append(HorizontalRule())
        return self

    def raw(self, content: str, format: str = "both") -> "Container":
        self.children.append(Raw(content, format))
        return self


class Section(Container):
    """A titled group of elements; nests to any depth.

    Supports ``with`` syntax purely for readable indentation — entering and
    exiting the context has no side effects.
    """

    def __init__(self, title: TextLike, level: int = 1):
        super().__init__()
        self.title_parts: list[InlineContent] = normalize(title)
        self._level = min(level, 6)

    def __enter__(self) -> "Section":
        return self

    def __exit__(self, *exc_info) -> None:
        return None
