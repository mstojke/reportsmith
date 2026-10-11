"""Markdown renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..elements import (
    CodeBlock,
    Element,
    Heading,
    HorizontalRule,
    Image,
    ListElement,
    Paragraph,
    Quote,
    Raw,
    Section,
    Table,
)
from ..inline import Inline, InlineContent

if TYPE_CHECKING:
    from ..report import Report

_ALIGN_MARKERS = {"left": ":---", "center": ":---:", "right": "---:"}


class MarkdownRenderer:
    """Renders a Report to GitHub-flavored Markdown."""

    def render(self, report: "Report") -> str:
        blocks: list[str] = [f"# {report.title}"]
        meta = self._metadata_lines(report)
        if meta:
            blocks.append("\n".join(meta))
        for child in report.children:
            blocks.extend(self._render_element(child))
        return "\n\n".join(blocks) + "\n"

    def _metadata_lines(self, report: "Report") -> list[str]:
        lines = []
        if report.subtitle:
            lines.append(f"*{report.subtitle}*  ")
        if report.author:
            lines.append(f"**Author:** {report.author}  ")
        if report.date:
            lines.append(f"**Date:** {report.date}  ")
        return lines

    # -- elements --------------------------------------------------------

    def _render_element(self, el: Element) -> list[str]:
        if isinstance(el, Section):
            blocks = [f"{'#' * el._level} {self._inline(el.title_parts)}"]
            for child in el.children:
                blocks.extend(self._render_element(child))
            return blocks
        if isinstance(el, Heading):
            return [f"{'#' * el.level} {self._inline(el.parts)}"]
        if isinstance(el, Paragraph):
            return [self._inline(el.parts)]
        if isinstance(el, Quote):
            text = self._inline(el.parts)
            return ["\n".join(f"> {line}" for line in text.splitlines() or [""])]
        if isinstance(el, CodeBlock):
            fence = "```"
            # Widen the fence if the source itself contains backtick fences.
            while fence in el.source:
                fence += "`"
            return [f"{fence}{el.language}\n{el.source}\n{fence}"]
        if isinstance(el, ListElement):
            return ["\n".join(self._list_lines(el, indent=0))]
        if isinstance(el, Table):
            return [self._table(el)]
        if isinstance(el, Image):
            title = f' "{el.title}"' if el.title else ""
            return [f"![{el.alt}]({el.src}{title})"]
        if isinstance(el, HorizontalRule):
            return ["---"]
        if isinstance(el, Raw):
            return [el.content] if el.format in ("markdown", "both") else []
        raise TypeError(f"Cannot render element of type {type(el).__name__}")

    def _list_lines(self, el: ListElement, indent: int) -> list[str]:
        lines: list[str] = []
        pad = "  " * indent
        counter = 0
        for item in el.items:
            if isinstance(item, ListElement):
                lines.extend(self._list_lines(item, indent + 1))
            else:
                counter += 1
                marker = f"{counter}." if el.ordered else "-"
                lines.append(f"{pad}{marker} {self._inline(item)}")
        return lines

    def _table(self, el: Table) -> str:
        def cell(parts: list[InlineContent]) -> str:
            # Pipes break table syntax; newlines become <br> inside cells.
            return self._inline(parts).replace("|", "\\|").replace("\n", "<br>")

        lines = ["| " + " | ".join(cell(h) for h in el.headers) + " |"]
        lines.append("| " + " | ".join(_ALIGN_MARKERS[a] for a in el.align) + " |")
        for row in el.rows:
            lines.append("| " + " | ".join(cell(c) for c in row) + " |")
        table = "\n".join(lines)
        if el.caption:
            table += f"\n\n*{el.caption}*"
        return table

    # -- inline ----------------------------------------------------------

    def _inline(self, parts: list[InlineContent]) -> str:
        out = []
        for part in parts:
            if isinstance(part, Inline):
                out.append(self._span(part))
            else:
                out.append(str(part))
        return "".join(out)

    def _span(self, span: Inline) -> str:
        if span.style == "bold":
            return f"**{span.text}**"
        if span.style == "italic":
            return f"*{span.text}*"
        if span.style == "code":
            return f"`{span.text}`"
        if span.style == "link":
            return f"[{span.text}]({span.href})"
        return span.text
