"""HTML renderer — produces a standalone styled document or a body fragment."""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING, Optional

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
    TableOfContents,
)
from ..inline import Inline, InlineContent
from ..toc import TocEntry, build_tree, collect_entries, find_tocs, heading_anchors

if TYPE_CHECKING:
    from ..report import Report

DEFAULT_CSS = """\
:root {
  --text: #1f2933;
  --muted: #6b7280;
  --border: #d7dbe0;
  --accent: #1d4ed8;
  --code-bg: #f3f4f6;
  --bg: #ffffff;
}
@media (prefers-color-scheme: dark) {
  :root {
    --text: #e5e7eb;
    --muted: #9ca3af;
    --border: #374151;
    --accent: #60a5fa;
    --code-bg: #1f2937;
    --bg: #111827;
  }
}
body {
  margin: 0 auto;
  max-width: 52rem;
  padding: 2rem 1.5rem 4rem;
  font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  line-height: 1.6;
  color: var(--text);
  background: var(--bg);
}
h1, h2, h3, h4, h5, h6 { line-height: 1.25; margin: 1.6em 0 0.5em; }
h1 { font-size: 1.9rem; margin-top: 0; }
h2 { font-size: 1.4rem; border-bottom: 1px solid var(--border); padding-bottom: 0.25em; }
h3 { font-size: 1.15rem; }
a { color: var(--accent); }
.report-meta { color: var(--muted); font-size: 0.9rem; margin-bottom: 2rem; }
.report-meta .subtitle { font-size: 1.05rem; font-style: italic; }
table { border-collapse: collapse; margin: 1em 0; width: 100%; }
th, td { border: 1px solid var(--border); padding: 0.45em 0.7em; text-align: left; }
th { background: var(--code-bg); }
caption { caption-side: bottom; color: var(--muted); font-size: 0.85rem; padding-top: 0.4em; }
code { background: var(--code-bg); border-radius: 4px; padding: 0.15em 0.35em; font-size: 0.9em; }
pre { background: var(--code-bg); border-radius: 8px; padding: 1em; overflow-x: auto; }
pre code { background: none; padding: 0; }
blockquote { border-left: 4px solid var(--border); color: var(--muted); margin: 1em 0; padding: 0.1em 1em; }
img { max-width: 100%; }
hr { border: none; border-top: 1px solid var(--border); margin: 2em 0; }
nav.toc { border: 1px solid var(--border); border-radius: 8px; padding: 0.8em 1.2em; margin: 1.5em 0; }
nav.toc .toc-title { font-weight: 600; margin-bottom: 0.3em; }
nav.toc ul { list-style: none; margin: 0; padding-left: 1.2em; }
nav.toc > ul { padding-left: 0; }
nav.toc a { text-decoration: none; }
nav.toc a:hover { text-decoration: underline; }
"""


class HtmlRenderer:
    """Renders a Report to HTML.

    With ``full_document=True`` output is a complete standalone page with the
    stylesheet embedded; otherwise only the body markup is produced.
    """

    def __init__(self, full_document: bool = True, css: Optional[str] = None):
        self.full_document = full_document
        self.css = DEFAULT_CSS if css is None else css

    def render(self, report: "Report") -> str:
        body = self._body(report)
        if not self.full_document:
            return body
        return (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n<head>\n'
            '<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{escape(report.title)}</title>\n"
            f"<style>\n{self.css}</style>\n"
            "</head>\n<body>\n"
            f"{body}"
            "</body>\n</html>\n"
        )

    def _body(self, report: "Report") -> str:
        self._report = report
        # Headings only get ids when there is a TOC to link to them, so
        # output for reports without one is unchanged.
        self._anchors = heading_anchors(report) if any(find_tocs(report)) else {}
        parts = [f"<h1>{escape(report.title)}</h1>\n"]
        meta = []
        if report.subtitle:
            meta.append(f'<div class="subtitle">{escape(report.subtitle)}</div>')
        if report.author:
            meta.append(f"<div><strong>Author:</strong> {escape(report.author)}</div>")
        if report.date:
            meta.append(f"<div><strong>Date:</strong> {escape(report.date)}</div>")
        if meta:
            parts.append('<div class="report-meta">\n' + "\n".join(meta) + "\n</div>\n")
        for child in report.children:
            parts.append(self._render_element(child))
        return "".join(parts)

    # -- elements --------------------------------------------------------

    def _render_element(self, el: Element) -> str:
        if isinstance(el, Section):
            level = el._level
            out = [f"<h{level}{self._id(el)}>{self._inline(el.title_parts)}</h{level}>\n"]
            out.extend(self._render_element(child) for child in el.children)
            return "".join(out)
        if isinstance(el, Heading):
            return f"<h{el.level}{self._id(el)}>{self._inline(el.parts)}</h{el.level}>\n"
        if isinstance(el, Paragraph):
            return f"<p>{self._inline(el.parts)}</p>\n"
        if isinstance(el, Quote):
            return f"<blockquote><p>{self._inline(el.parts)}</p></blockquote>\n"
        if isinstance(el, CodeBlock):
            cls = f' class="language-{escape(el.language, quote=True)}"' if el.language else ""
            return f"<pre><code{cls}>{escape(el.source)}</code></pre>\n"
        if isinstance(el, ListElement):
            return self._list(el)
        if isinstance(el, Table):
            return self._table(el)
        if isinstance(el, Image):
            title = f' title="{escape(el.title, quote=True)}"' if el.title else ""
            return (
                f'<img src="{escape(el.src, quote=True)}" '
                f'alt="{escape(el.alt, quote=True)}"{title}>\n'
            )
        if isinstance(el, HorizontalRule):
            return "<hr>\n"
        if isinstance(el, Raw):
            return el.content + "\n" if el.format in ("html", "both") else ""
        if isinstance(el, TableOfContents):
            return self._toc(el)
        raise TypeError(f"Cannot render element of type {type(el).__name__}")

    def _id(self, el: Element) -> str:
        anchor = self._anchors.get(id(el))
        return f' id="{escape(anchor, quote=True)}"' if anchor else ""

    def _toc(self, el: TableOfContents) -> str:
        label = escape(el.title or "Contents", quote=True)
        out = [f'<nav class="toc" aria-label="{label}">\n']
        if el.title:
            out.append(f'<div class="toc-title">{escape(el.title)}</div>\n')

        def walk(entries: list[TocEntry]) -> None:
            out.append("<ul>\n")
            for entry in entries:
                anchor = escape(self._anchors[id(entry.element)], quote=True)
                # Links can't nest inside the entry's own <a>; keep their text.
                parts = [
                    p.text if isinstance(p, Inline) and p.style == "link" else p
                    for p in entry.parts
                ]
                out.append(f'<li><a href="#{anchor}">{self._inline(parts)}</a>')
                if entry.children:
                    out.append("\n")
                    walk(entry.children)
                out.append("</li>\n")
            out.append("</ul>\n")

        entries = build_tree(collect_entries(self._report, el.depth))
        if entries:
            walk(entries)
        out.append("</nav>\n")
        return "".join(out)

    def _list(self, el: ListElement) -> str:
        tag = "ol" if el.ordered else "ul"
        out = [f"<{tag}>\n"]
        for item in el.items:
            if isinstance(item, ListElement):
                # Nested list lives inside the preceding <li> per HTML spec;
                # emit as its own item if there is no preceding one.
                nested = self._list(item)
                if out[-1].endswith("</li>\n"):
                    out[-1] = out[-1][: -len("</li>\n")] + "\n" + nested + "</li>\n"
                else:
                    out.append(f"<li>{nested}</li>\n")
            else:
                out.append(f"<li>{self._inline(item)}</li>\n")
        out.append(f"</{tag}>\n")
        return "".join(out)

    def _table(self, el: Table) -> str:
        out = ["<table>\n"]
        if el.caption:
            out.append(f"<caption>{escape(el.caption)}</caption>\n")
        out.append("<thead>\n<tr>")
        for header, align in zip(el.headers, el.align):
            out.append(f'<th style="text-align:{align}">{self._inline(header)}</th>')
        out.append("</tr>\n</thead>\n<tbody>\n")
        for row in el.rows:
            out.append("<tr>")
            for cell, align in zip(row, el.align):
                out.append(f'<td style="text-align:{align}">{self._inline(cell)}</td>')
            out.append("</tr>\n")
        out.append("</tbody>\n</table>\n")
        return "".join(out)

    # -- inline ----------------------------------------------------------

    def _inline(self, parts: list[InlineContent]) -> str:
        out = []
        for part in parts:
            if isinstance(part, Inline):
                out.append(self._span(part))
            else:
                out.append(escape(str(part)))
        return "".join(out)

    def _span(self, span: Inline) -> str:
        text = escape(span.text)
        if span.style == "bold":
            return f"<strong>{text}</strong>"
        if span.style == "italic":
            return f"<em>{text}</em>"
        if span.style == "code":
            return f"<code>{text}</code>"
        if span.style == "link":
            return f'<a href="{escape(span.href, quote=True)}">{text}</a>'
        return text
