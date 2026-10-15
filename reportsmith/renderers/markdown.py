"""Markdown renderer."""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING

from ..elements import (
    Callout,
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
    TableOfContents,
)
from ..inline import Inline, InlineContent
from ..toc import TocEntry, build_tree, collect_entries, heading_anchors, plain_text

if TYPE_CHECKING:
    from ..report import Report

_ALIGN_MARKERS = {"left": ":---", "center": ":---:", "right": "---:"}


class MarkdownRenderer:
    """Renders a Report to GitHub-flavored Markdown."""

    def render(self, report: "Report") -> str:
        self._report = report
        self._anchors = heading_anchors(report)
        self._footnotes: list[str] = []
        blocks: list[str] = [f"# {report.title}"]
        meta = self._metadata_lines(report)
        if meta:
            blocks.append("\n".join(meta))
        for child in report.children:
            blocks.extend(self._render_element(child))
        if self._footnotes:
            # GFM footnote definitions; continuation lines are indented.
            blocks.append("\n".join(
                f"[^{n}]: " + text.replace("\n", "\n    ")
                for n, text in enumerate(self._footnotes, start=1)
            ))
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
        if isinstance(el, TableOfContents):
            return self._toc(el)
        if isinstance(el, Callout):
            return [self._callout(el)]
        raise TypeError(f"Cannot render element of type {type(el).__name__}")

    def _callout(self, el: Callout) -> str:
        # GitHub alert syntax; other renderers show it as a block quote.
        # Alerts have no custom titles, so a title becomes a bold first line.
        lines = [f"[!{el.kind.upper()}]"]
        if el.title:
            lines.append(f"**{el.title}**")
        blocks = [b for child in el.children for b in self._render_element(child)]
        if blocks:
            if el.title:
                lines.append("")
            lines.extend("\n\n".join(blocks).split("\n"))
        return "\n".join(f"> {line}" if line else ">" for line in lines)

    def _toc(self, el: TableOfContents) -> list[str]:
        blocks = [f"**{el.title}**"] if el.title else []
        lines: list[str] = []

        def walk(entries: list[TocEntry], indent: int) -> None:
            for entry in entries:
                # Plain text: inline markup can't nest inside link text.
                text = plain_text(entry.parts).replace("[", r"\[").replace("]", r"\]")
                anchor = self._anchors[id(entry.element)]
                lines.append(f"{'  ' * indent}- [{text}](#{anchor})")
                walk(entry.children, indent + 1)

        walk(build_tree(collect_entries(self._report, el.depth)), 0)
        if lines:
            blocks.append("\n".join(lines))
        return blocks

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
        if span.style == "strike":
            return f"~~{span.text}~~"
        if span.style in ("sub", "sup"):
            # No Markdown syntax; GitHub and most renderers accept the tags.
            return f"<{span.style}>{escape(span.text, quote=False)}</{span.style}>"
        if span.style == "footnote":
            self._footnotes.append(span.text)
            return f"[^{len(self._footnotes)}]"
        return span.text
