"""Block-level report elements.

Every element knows nothing about output formats; rendering lives in
``reportsmith.renderers``. ``Section`` is a container element that also mixes in
the builder API, so content can be added to a report or any nested section
with the same methods.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Iterable, Optional, Sequence, Union

from .inline import InlineContent, TextLike, normalize

if TYPE_CHECKING:
    from .data import Formats, Headers


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

    # -- construction from data ------------------------------------------
    # Shared options: ``columns`` selects and orders columns; ``headers``
    # relabels them (a list, or a column -> label mapping); ``formats`` is a
    # format string / callable applied to every numeric cell, or a
    # column -> format mapping applied to every value in that column;
    # ``missing`` replaces None/NaN/NA; ``align=None`` right-aligns numeric
    # columns and left-aligns the rest.

    @classmethod
    def from_records(
        cls,
        records: Iterable[Mapping[Any, Any]],
        columns: Optional[Sequence[Any]] = None,
        *,
        headers: Headers = None,
        formats: Formats = None,
        align: Optional[Sequence[str]] = None,
        missing: str = "",
        caption: str = "",
    ) -> "Table":
        """Build a table from a sequence of dicts (keys become headers)."""
        from .data import from_records

        return from_records(
            records, columns, headers=headers, formats=formats,
            align=align, missing=missing, caption=caption,
        )

    @classmethod
    def from_csv(
        cls,
        source: Union[str, Path, IO[str]],
        columns: Optional[Sequence[str]] = None,
        *,
        delimiter: str = ",",
        encoding: str = "utf-8",
        parse_numbers: bool = True,
        headers: Headers = None,
        formats: Formats = None,
        align: Optional[Sequence[str]] = None,
        missing: str = "",
        caption: str = "",
    ) -> "Table":
        """Build a table from a CSV file path or open text file.

        The first row is the header. With ``parse_numbers=True`` numeric
        fields become numbers (so formats and auto-alignment apply);
        integers with leading zeros stay text.
        """
        from .data import from_csv

        return from_csv(
            source, columns, delimiter=delimiter, encoding=encoding,
            parse_numbers=parse_numbers, headers=headers, formats=formats,
            align=align, missing=missing, caption=caption,
        )

    @classmethod
    def from_dataframe(
        cls,
        df: Any,
        columns: Optional[Sequence[Any]] = None,
        *,
        index: bool = False,
        headers: Headers = None,
        formats: Formats = None,
        align: Optional[Sequence[str]] = None,
        missing: str = "",
        caption: str = "",
    ) -> "Table":
        """Build a table from a pandas DataFrame (pandas is not required by
        reportsmith itself). ``index=True`` adds the index as the first column."""
        from .data import from_dataframe

        return from_dataframe(
            df, columns, index=index, headers=headers, formats=formats,
            align=align, missing=missing, caption=caption,
        )


class Image(Element):
    def __init__(self, src: str, alt: str = "", title: str = ""):
        self.src = src
        self.alt = alt
        self.title = title


class HorizontalRule(Element):
    pass


class Raw(Element):
    """Format-specific passthrough content.

    Rendered verbatim when the output format matches (``"markdown"``,
    ``"html"`` or ``"latex"``); skipped otherwise. ``format="both"`` emits
    in both Markdown and HTML.
    """

    def __init__(self, content: str, format: str = "both"):
        if format not in ("markdown", "html", "latex", "both"):
            raise ValueError(
                f"format must be 'markdown', 'html', 'latex' or 'both', got {format!r}"
            )
        self.content = content
        self.format = format


class TableOfContents(Element):
    """A table of contents listing the report's sections and headings.

    Always covers the whole report, wherever it is placed. ``depth`` limits
    how many heading levels are listed: 1 lists only top-level sections, 2
    adds their subsections, and so on (up to 5).
    """

    def __init__(self, title: str = "Contents", depth: int = 3):
        if not 1 <= depth <= 5:
            raise ValueError(f"TOC depth must be 1-5, got {depth}")
        self.title = title
        self.depth = depth


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

    def table_from_records(
        self,
        records: Iterable[Mapping[Any, Any]],
        columns: Optional[Sequence[Any]] = None,
        **options: Any,
    ) -> "Container":
        """Add a table built from dicts; see :meth:`Table.from_records`."""
        self.children.append(Table.from_records(records, columns, **options))
        return self

    def table_from_csv(
        self,
        source: Union[str, Path, IO[str]],
        columns: Optional[Sequence[str]] = None,
        **options: Any,
    ) -> "Container":
        """Add a table read from CSV; see :meth:`Table.from_csv`."""
        self.children.append(Table.from_csv(source, columns, **options))
        return self

    def table_from_dataframe(
        self, df: Any, columns: Optional[Sequence[Any]] = None, **options: Any
    ) -> "Container":
        """Add a table built from a DataFrame; see :meth:`Table.from_dataframe`."""
        self.children.append(Table.from_dataframe(df, columns, **options))
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

    def toc(self, title: str = "Contents", depth: int = 3) -> "Container":
        """Add a table of contents for the whole report."""
        self.children.append(TableOfContents(title, depth))
        return self

    def callout(
        self, kind: str = "note", content: Optional[TextLike] = None, title: str = ""
    ) -> "Callout":
        """Add a callout box. ``content``, if given, becomes its first
        paragraph; returns the new callout (usable as a context manager) so
        more content can be added to it."""
        callout = Callout(kind, content, title, level=self._level)
        self.children.append(callout)
        return callout


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


CALLOUT_KINDS = ("note", "tip", "important", "warning", "caution")


class Callout(Container):
    """A highlighted box — note, tip, important, warning or caution —
    holding block content (paragraphs, lists, code, tables, ...).

    ``title`` defaults to the capitalized kind. Supports ``with`` syntax
    like :class:`Section`. Callouts can't contain sections or a table of
    contents, so they never affect the document outline.
    """

    def __init__(
        self,
        kind: str = "note",
        content: Optional[TextLike] = None,
        title: str = "",
        level: int = 1,
    ):
        if kind not in CALLOUT_KINDS:
            raise ValueError(
                f"kind must be one of {', '.join(map(repr, CALLOUT_KINDS))}, got {kind!r}"
            )
        super().__init__()
        self.kind = kind
        self.title = title
        self._level = level  # headings inside default to the parent's child level
        if content is not None:
            self.paragraph(content)

    @property
    def display_title(self) -> str:
        return self.title or self.kind.capitalize()

    def add(self, element: Element) -> "Container":
        if isinstance(element, (Section, TableOfContents)):
            raise TypeError(f"A callout cannot contain a {type(element).__name__}")
        return super().add(element)

    def section(self, title: TextLike) -> "Section":
        raise TypeError("A callout cannot contain sections; use heading() instead")

    def toc(self, title: str = "Contents", depth: int = 3) -> "Container":
        raise TypeError("A callout cannot contain a table of contents")

    def __enter__(self) -> "Callout":
        return self

    def __exit__(self, *exc_info) -> None:
        return None
