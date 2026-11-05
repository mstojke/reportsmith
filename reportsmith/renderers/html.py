"""HTML renderer — produces a standalone styled document or a body fragment."""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING, Optional

from ..elements import (
    Callout,
    CellStyle,
    CodeBlock,
    Element,
    Figure,
    Heading,
    HorizontalRule,
    Image,
    ListElement,
    DefinitionList,
    TaskList,
    PageBreak,
    Paragraph,
    Quote,
    Raw,
    Section,
    Table,
    TableOfContents,
)
from ..assets import data_uri, path_reference
from ..colors import BACKGROUND_COLORS, DARK_BACKGROUND_COLORS, DARK_TEXT_COLORS, TEXT_COLORS
from ..highlight import html_css as highlight_css, html_spans, require_pygments
from ..inline import Inline, InlineContent
from ..numbering import HTML_PREFIXES, Numbering, iter_elements
from ..page import segments
from ..toc import TocEntry, build_tree, collect_entries, find_tocs, heading_anchors

if TYPE_CHECKING:
    from ..report import Report

_LIGHT_VARS = """\
  --text: #1f2933;
  --muted: #6b7280;
  --border: #d7dbe0;
  --accent: #1d4ed8;
  --code-bg: #f3f4f6;
  --bg: #ffffff;
  --note: #1d4ed8;
  --tip: #15803d;
  --important: #7c3aed;
  --warning: #b45309;
  --caution: #b91c1c;
  --stripe: #f8f9fb;
""" + "".join(f"  --cell-{n}: {TEXT_COLORS[n]};\n  --cell-bg-{n}: {BACKGROUND_COLORS[n]};\n" for n in TEXT_COLORS)
_DARK_VARS = """\
  --text: #e5e7eb;
  --muted: #9ca3af;
  --border: #374151;
  --accent: #60a5fa;
  --code-bg: #1f2937;
  --bg: #111827;
  --note: #60a5fa;
  --tip: #4ade80;
  --important: #a78bfa;
  --warning: #fbbf24;
  --caution: #f87171;
  --stripe: #182231;
""" + "".join(f"  --cell-{n}: {DARK_TEXT_COLORS[n]};\n  --cell-bg-{n}: {DARK_BACKGROUND_COLORS[n]};\n" for n in TEXT_COLORS)
_BASE_CSS = """\
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
dt { font-weight: 600; }
dd { margin: 0 0 0.6em 1.5em; }
ul.task-list { list-style: none; padding-left: 0.2em; }
ul.task-list input { margin: 0 0.5em 0 0; }
.callout { --callout: var(--accent); border-left: 4px solid var(--callout); border-radius: 6px; background: var(--code-bg); padding: 0.6em 1em; margin: 1em 0; }
.callout > :last-child { margin-bottom: 0; }
.callout-title { color: var(--callout); font-weight: 600; margin: 0 0 0.3em; }
.callout-note { --callout: var(--note); }
.callout-tip { --callout: var(--tip); }
.callout-important { --callout: var(--important); }
.callout-warning { --callout: var(--warning); }
.callout-caution { --callout: var(--caution); }
sup.footnote-ref a { text-decoration: none; }
.footnotes { color: var(--muted); font-size: 0.9rem; margin-top: 3em; }
.footnote-back { text-decoration: none; }
figure { margin: 1.5em 0; text-align: center; }
figure img { max-width: 100%; }
figcaption, caption { color: var(--muted); font-size: 0.85rem; }
figcaption { margin-top: 0.4em; }
.caption-label { font-weight: 600; }
table.striped tbody tr:nth-child(even) { background: var(--stripe); }
tfoot td { font-weight: 600; border-top: 2px solid var(--muted); }
td.cell-bold { font-weight: 600; }
.cover { display: flex; flex-direction: column; align-items: center; text-align: center; min-height: 70vh; margin-bottom: 3rem; padding-bottom: 2rem; border-bottom: 1px solid var(--border); }
.cover-top { display: flex; flex-direction: column; align-items: center; gap: 1rem; width: 100%; }
.cover-logo { max-height: 30vh; object-fit: contain; }
.cover-org { color: var(--muted); font-size: 1.1rem; font-weight: 600; letter-spacing: 0.04em; }
.cover-main { flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 3rem 0; }
.cover h1 { font-size: 2.6rem; margin: 0; }
.cover-subtitle { color: var(--muted); font-size: 1.3rem; margin-top: 0.6rem; }
.cover-rule { width: 4rem; border-top: 3px solid var(--accent); margin: 1.6rem auto; }
.cover-meta { font-size: 1.05rem; }
.cover-note { color: var(--muted); font-size: 0.85rem; }
""" + "".join(
    f".cell-{n} {{ color: var(--cell-{n}); }}\n.cell-bg-{n} {{ background: var(--cell-bg-{n}); }}\n"
    for n in TEXT_COLORS
)
# Printing always uses the light colours, keeps blocks whole where it can,
# and shows the target of external links.
_PRINT_CSS = (
    "@media print {\n"
    "  :root {\n" + _LIGHT_VARS.replace("\n  ", "\n    ").replace("  --text", "    --text", 1) + "  }\n"
    """\
  body { max-width: none; padding: 0; }
  h1, h2, h3, h4, h5, h6 { break-after: avoid; }
  figure, pre, blockquote, .callout, tr, img { break-inside: avoid; }
  pre { white-space: pre-wrap; overflow: visible; }
  a[href^="http"]::after { content: " (" attr(href) ")"; color: var(--muted); font-size: 0.85em; word-break: break-all; }
  .page-break { break-after: page; }
  /* The cover fills the first page (vh is the page area when printing). */
  .cover { height: 100vh; min-height: 0; box-sizing: border-box; margin: 0; padding: 0; border: none; break-after: page; overflow: hidden; }
}
"""
)

THEMES = ("auto", "light", "dark")


def theme_css(theme: str = "auto") -> str:
    """The default stylesheet for a colour theme.

    ``"auto"`` follows the reader's light/dark preference
    (``prefers-color-scheme``); ``"light"`` and ``"dark"`` are fixed.
    """
    if theme not in THEMES:
        raise ValueError(f"theme must be one of {', '.join(map(repr, THEMES))}, got {theme!r}")
    if theme == "auto":
        dark = _DARK_VARS.replace("  --", "    --")
        root = (
            ":root {\n" + _LIGHT_VARS + "}\n"
            "@media (prefers-color-scheme: dark) {\n  :root {\n" + dark + "  }\n}\n"
        )
    else:
        root = ":root {\n" + (_LIGHT_VARS if theme == "light" else _DARK_VARS) + "}\n"
    return root + _BASE_CSS + _PRINT_CSS


_BOX_STYLE = (
    'font: 9pt -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; '
    "color: #6b7280;"
)


def _css_string(text: str) -> str:
    # "<" is escaped too, so a header can't close the <style> element.
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\A ").replace("<", "\\3C ")
    return f'"{escaped}"'


def page_css(report: "Report") -> str:
    """``@page`` rules for the report's running header and footer.

    Margin boxes print in Chromium-based browsers and paged-media tools
    (WeasyPrint, Paged.js, Prince); other browsers ignore them.
    """
    boxes = []
    for band, edge in ((report.header, "top"), (report.footer, "bottom")):
        if band is None:
            continue
        for text, position in zip(band, ("left", "center", "right")):
            if not text:
                continue
            content = " ".join(
                {"page": "counter(page)", "pages": "counter(pages)"}.get(kind) or _css_string(value)
                for kind, value in segments(text, report)
            )
            boxes.append(f"  @{edge}-{position} {{ content: {content}; {_BOX_STYLE} }}\n")
    if not boxes:
        return ""
    css = "@page {\n  margin: 20mm 18mm;\n" + "".join(boxes) + "}\n"
    # The first page has the title block instead of a header; a cover
    # page has neither header nor footer.
    edges = ("top", "bottom") if report.cover is not None else ("top",) if report.header is not None else ()
    if edges:
        css += "@page :first {\n" + "".join(
            f"  @{edge}-{position} {{ content: none; }}\n"
            for edge in edges
            for position in ("left", "center", "right")
        ) + "}\n"
    return css


#: The default stylesheet (automatic light/dark theme).
DEFAULT_CSS = theme_css("auto")


class HtmlRenderer:
    """Renders a Report to HTML.

    With ``full_document=True`` output is a complete standalone page with the
    stylesheet embedded; otherwise only the body markup is produced.
    """

    def __init__(
        self,
        full_document: bool = True,
        css: Optional[str] = None,
        theme: str = "auto",
        highlight: bool = False,
    ):
        self.full_document = full_document
        self.css = theme_css(theme) if css is None else css
        self.highlight = highlight
        if highlight:
            require_pygments()
            # Token colours are added even to a custom stylesheet.
            self.css += highlight_css("auto" if css is not None else theme)

    def render(self, report: "Report") -> str:
        body = self._body(report)
        if not self.full_document:
            return body
        from .. import __version__

        meta = [
            ("author", report.author),
            ("description", report.description),
            ("keywords", ", ".join(report.keywords)),
            ("generator", f"reportsmith {__version__}"),
        ]
        meta_tags = "".join(
            f'<meta name="{name}" content="{escape(value, quote=True)}">\n'
            for name, value in meta
            if value
        )
        return (
            "<!DOCTYPE html>\n"
            f'<html lang="{escape(report.language, quote=True)}">\n<head>\n'
            '<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"{meta_tags}"
            f"<title>{escape(report.title)}</title>\n"
            f"<style>\n{self.css}{page_css(report)}</style>\n"
            "</head>\n<body>\n"
            f"{body}"
            "</body>\n</html>\n"
        )

    def _body(self, report: "Report") -> str:
        self._report = report
        self._numbering = Numbering(report)
        # Headings only get ids when there is a TOC or a ref() to link to
        # them, so output for other reports is unchanged.
        has_toc = any(find_tocs(report))
        self._anchors = heading_anchors(report, self._numbering) if has_toc else {}
        for el in iter_elements(report):
            if isinstance(el, Section) and el.label:
                self._anchors[id(el)] = f"sec-{el.label}"
        parts = [self._cover(report) if report.cover is not None else self._title_block(report)]
        self._footnotes: list[str] = []
        for child in report.children:
            parts.append(self._render_element(child))
        if self._footnotes:
            parts.append('<section class="footnotes">\n<hr>\n<ol>\n')
            for n, text in enumerate(self._footnotes, start=1):
                parts.append(
                    f'<li id="fn-{n}">{escape(text)} <a href="#fnref-{n}" '
                    f'class="footnote-back" aria-label="Back to reference {n}">&#8617;&#xFE0E;</a></li>\n'
                )
            parts.append("</ol>\n</section>\n")
        return "".join(parts)

    @staticmethod
    def _title_block(report: "Report") -> str:
        out = f"<h1>{escape(report.title)}</h1>\n"
        meta = []
        if report.subtitle:
            meta.append(f'<div class="subtitle">{escape(report.subtitle)}</div>')
        if report.author:
            meta.append(f"<div><strong>Author:</strong> {escape(report.author)}</div>")
        if report.date:
            meta.append(f"<div><strong>Date:</strong> {escape(report.date)}</div>")
        if meta:
            out += '<div class="report-meta">\n' + "\n".join(meta) + "\n</div>\n"
        return out

    @staticmethod
    def _cover(report: "Report") -> str:
        cover = report.cover
        assert cover is not None
        out = ['<header class="cover">\n<div class="cover-top">\n']
        logo = cover.logo
        if logo is not None:
            if logo.kind == "path":
                src = path_reference(logo.source)
            else:
                src = data_uri(*logo.image_data("png"))
            out.append(
                f'<img class="cover-logo" src="{escape(src, quote=True)}" '
                f'alt="{escape(logo.alt, quote=True)}" style="width:{(logo.width or 1) * 100:g}%">\n'
            )
        if cover.organization:
            out.append(f'<div class="cover-org">{escape(cover.organization)}</div>\n')
        out.append('</div>\n<div class="cover-main">\n')
        out.append(f"<h1>{escape(report.title)}</h1>\n")
        if report.subtitle:
            out.append(f'<div class="cover-subtitle">{escape(report.subtitle)}</div>\n')
        meta = [escape(x) for x in (report.author, report.date) if x]
        if meta:
            out.append('<div class="cover-rule"></div>\n')
            out.append('<div class="cover-meta">' + "<br>\n".join(meta) + "</div>\n")
        out.append("</div>\n")
        if cover.note:
            out.append(f'<div class="cover-note">{escape(cover.note)}</div>\n')
        out.append("</header>\n")
        return "".join(out)

    # -- elements --------------------------------------------------------

    def _render_element(self, el: Element) -> str:
        if isinstance(el, Section):
            level = el._level
            out = [f"<h{level}{self._id(el)}>{self._numbered(el, el.title_parts)}</h{level}>\n"]
            out.extend(self._render_element(child) for child in el.children)
            return "".join(out)
        if isinstance(el, Heading):
            return f"<h{el.level}{self._id(el)}>{self._numbered(el, el.parts)}</h{el.level}>\n"
        if isinstance(el, Paragraph):
            return f"<p>{self._inline(el.parts)}</p>\n"
        if isinstance(el, Quote):
            return f"<blockquote><p>{self._inline(el.parts)}</p></blockquote>\n"
        if isinstance(el, CodeBlock):
            cls = f' class="language-{escape(el.language, quote=True)}"' if el.language else ""
            spans = html_spans(el.source, el.language) if self.highlight else None
            return f"<pre><code{cls}>{spans if spans is not None else escape(el.source)}</code></pre>\n"
        if isinstance(el, ListElement):
            return self._list(el)
        if isinstance(el, DefinitionList):
            if not el.items:
                return ""
            items = "".join(
                f"<dt>{self._inline(term)}</dt>\n<dd>{self._inline(definition)}</dd>\n"
                for term, definition in el.items
            )
            return f"<dl>\n{items}</dl>\n"
        if isinstance(el, TaskList):
            if not el.items:
                return ""
            items = "".join(
                f'<li><input type="checkbox" disabled{" checked" if done else ""}> '
                f"{self._inline(text)}</li>\n"
                for done, text in el.items
            )
            return f'<ul class="task-list">\n{items}</ul>\n'
        if isinstance(el, PageBreak):
            return '<div class="page-break"></div>\n'
        if isinstance(el, Table):
            return self._table(el)
        if isinstance(el, Figure):
            return self._figure(el)
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
        if isinstance(el, Callout):
            out = [
                f'<div class="callout callout-{el.kind}">\n',
                f'<p class="callout-title">{escape(el.display_title)}</p>\n',
            ]
            out.extend(self._render_element(child) for child in el.children)
            out.append("</div>\n")
            return "".join(out)
        raise TypeError(f"Cannot render element of type {type(el).__name__}")

    def _numbered(self, el: "Section | Heading", parts: list[InlineContent]) -> str:
        number = self._numbering.section_number(el)
        text = self._inline(parts)
        return f'<span class="section-number">{number}</span> {text}' if number else text

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
                # Links can't nest inside the entry's own <a>; keep their
                # text. Footnote markers belong to the heading, not the TOC.
                parts = [
                    p.text if isinstance(p, Inline) and p.style == "link" else p
                    for p in entry.parts
                    if not (isinstance(p, Inline) and p.style == "footnote")
                ]
                number = f'<span class="section-number">{entry.number}</span> ' if entry.number else ""
                out.append(f'<li><a href="#{anchor}">{number}{self._inline(parts)}</a>')
                if entry.children:
                    out.append("\n")
                    walk(entry.children)
                out.append("</li>\n")
            out.append("</ul>\n")

        entries = build_tree(collect_entries(self._report, el.depth, self._numbering))
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

    def _target_id(self, el: "Figure | Table") -> str:
        if not el.label:
            return ""
        prefix = "fig" if isinstance(el, Figure) else "tbl"
        return f' id="{prefix}-{escape(el.label, quote=True)}"'

    def _caption(self, el: "Figure | Table") -> str:
        label = self._numbering.caption_label(el)
        return f'<span class="caption-label">{label}:</span> {escape(el.caption)}'

    def _figure(self, el: Figure) -> str:
        if el.kind == "path":
            src = path_reference(el.source)
        else:
            src = data_uri(*el.image_data("png"))
        style = f' style="width:{el.width * 100:g}%"' if el.width else ""
        out = [
            f"<figure{self._target_id(el)}>\n",
            f'<img src="{escape(src, quote=True)}" alt="{escape(el.alt, quote=True)}"{style}>\n',
        ]
        if el.caption:
            out.append(f"<figcaption>{self._caption(el)}</figcaption>\n")
        out.append("</figure>\n")
        return "".join(out)

    def _table(self, el: Table) -> str:
        cls = ' class="striped"' if el.striped else ""
        out = [f"<table{self._target_id(el)}{cls}>\n"]
        if el.caption:
            out.append(f"<caption>{self._caption(el)}</caption>\n")
        if el.widths:
            out.append("<colgroup>")
            out.extend(f'<col style="width:{w * 100:.4g}%">' for w in el.widths)
            out.append("</colgroup>\n")
        out.append("<thead>\n<tr>")
        for header, align in zip(el.headers, el.align):
            out.append(f'<th style="text-align:{align}">{self._inline(header)}</th>')
        out.append("</tr>\n</thead>\n<tbody>\n")
        for i, row in enumerate(el.rows):
            out.append("<tr>")
            for j, (cell, align) in enumerate(zip(row, el.align)):
                out.append(self._td(cell, align, el.style_at(i, j)))
            out.append("</tr>\n")
        out.append("</tbody>\n")
        if el.footer is not None:
            out.append("<tfoot>\n<tr>")
            for j, (cell, align) in enumerate(zip(el.footer, el.align)):
                out.append(self._td(cell, align, el.footer_styles.get(j, CellStyle())))
            out.append("</tr>\n</tfoot>\n")
        out.append("</table>\n")
        return "".join(out)

    def _td(self, parts: list[InlineContent], align: str, style: CellStyle) -> str:
        # Named colours are classes, so they follow the theme; hex values
        # are inline styles.
        classes, css = [], [f"text-align:{align}"]
        if style.bold:
            classes.append("cell-bold")
        for value, prefix, prop in ((style.color, "cell-", "color"), (style.background, "cell-bg-", "background")):
            if value is None:
                continue
            if value.startswith("#"):
                css.append(f"{prop}:{value}")
            else:
                classes.append(prefix + value)
        cls = f' class="{" ".join(classes)}"' if classes else ""
        return f'<td{cls} style="{";".join(css)}">{self._inline(parts)}</td>'

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
        if span.style == "strike":
            return f"<del>{text}</del>"
        if span.style in ("sub", "sup"):
            return f"<{span.style}>{text}</{span.style}>"
        if span.style == "ref":
            kind, _ = self._numbering.resolve(span.href)
            prefix = HTML_PREFIXES[kind]
            text = escape(self._numbering.ref_text(span.href, span.text))
            return f'<a href="#{prefix}-{escape(span.href, quote=True)}" class="ref">{text}</a>'
        if span.style == "footnote":
            self._footnotes.append(span.text)
            n = len(self._footnotes)
            return (
                f'<sup class="footnote-ref"><a href="#fn-{n}" id="fnref-{n}">{n}</a></sup>'
            )
        return text
