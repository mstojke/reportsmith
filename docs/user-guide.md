# reportsmith — User Guide

`reportsmith` lets you build a report programmatically from typed elements and export it to **Markdown** or a **standalone styled HTML page**. It has no dependencies and works on Python 3.9+.

This guide walks through every feature. For a terse signature-level listing, see the [API reference](api-reference.rst).

## Contents

1. [Creating a report](#creating-a-report)
2. [Sections](#sections)
3. [Text and inline formatting](#text-and-inline-formatting)
4. [Tables](#tables)
5. [Lists](#lists)
6. [Code blocks, quotes, images, rules](#code-blocks-quotes-images-rules)
7. [Raw passthrough content](#raw-passthrough-content)
8. [Exporting](#exporting)
9. [Exporting to PDF](#exporting-to-pdf)
10. [Customizing the HTML output](#customizing-the-html-output)
11. [Escaping and safety](#escaping-and-safety)

---

## Creating a report

```python
from reportsmith import Report

report = Report(
    "Q3 Sales Report",              # required title (rendered as the H1)
    author="Jane Doe",              # optional
    subtitle="Quarterly summary",   # optional
    date="2026-08-26",              # optional; defaults to today
)
```

`date` accepts a string, a `datetime.date`, or a `datetime.datetime` — date objects are converted to ISO format. Pass `date=""` to omit the date line entirely.

The title, subtitle, author, and date render as a metadata header at the top of both exports.

All content methods return the container they were called on, so calls chain:

```python
report.paragraph("First.").paragraph("Second.").horizontal_rule()
```

## Sections

`section(title)` adds a titled group of content. Sections nest to any depth, and the heading level is derived automatically from nesting depth: top-level sections render as `##` / `<h2>`, their children as `###` / `<h3>`, and so on (capped at level 6).

Sections support `with` syntax — this is purely for readable indentation and has no other effect:

```python
with report.section("Results") as s:
    s.paragraph("Overall results were positive.")
    with s.section("Details") as d:      # renders as h3
        d.paragraph("The fine print.")
```

The same works without `with`:

```python
s = report.section("Results")
s.paragraph("Overall results were positive.")
```

If you need an out-of-band heading (not tied to a section), use `heading(text, level=None)`; when `level` is omitted it defaults to one deeper than the container it's added to.

## Text and inline formatting

Everywhere text is accepted — paragraphs, headings, quotes, list items, table cells, section titles — you can pass:

- a plain string: `s.paragraph("Just text.")`
- a list mixing strings and inline spans:

```python
from reportsmith import bold, italic, code, link

s.paragraph([
    "Revenue was ", bold("up 12%"), " — see the ",
    link("dashboard", "https://example.com"), " or run ",
    code("make report"), " ", italic("locally"), ".",
])
```

Each span renders correctly per format (`**bold**` vs `<strong>`, etc.). Non-string items in the list (numbers, `None`) are coerced with `str()`.

## Tables

```python
s.table(
    headers=["Region", "Revenue", "Change"],
    rows=[
        ["EMEA", "$1.2M", "+8%"],
        ["APAC", "$0.9M", "-2%"],
    ],
    caption="Revenue by region",              # optional
    align=["left", "right", "right"],         # optional; per-column
)
```

- `align` entries are `"left"`, `"center"`, or `"right"`; the default is left for all columns.
- Every row must have the same number of cells as `headers` — a mismatch raises `ValueError` at construction time, not at render time.
- Cells accept inline formatting like any other text: `[["EMEA", bold("$1.2M")]]`.
- In Markdown, pipes in cell text are escaped and newlines inside a cell become `<br>` so the table stays valid.

## Lists

```python
s.bullet_list(["First point", "Second point"])
s.numbered_list(["Step one", "Step two"])
```

Items accept inline formatting, and lists nest by placing a `ListElement` in the items:

```python
from reportsmith import ListElement

s.bullet_list([
    "Parent item",
    ListElement(["Child A", "Child B"], ordered=True),
    "Next parent item",
])
```

A nested list attaches to the item before it (indented in Markdown, placed inside the preceding `<li>` in HTML). In a numbered list, nested lists don't consume a number.

## Code blocks, quotes, images, rules

```python
s.code("SELECT * FROM sales;", language="sql")   # fenced / <pre><code>
s.quote("Any sufficiently advanced report is indistinguishable from magic.")
s.image("chart.png", alt="Revenue chart", title="Q3 revenue")
s.horizontal_rule()
```

- `language` becomes the fence info string in Markdown and a `language-*` class in HTML (ready for highlight.js/Prism if you add one via custom CSS/raw HTML).
- If the code itself contains ` ``` `, the Markdown fence automatically widens so the block stays intact.

## Raw passthrough content

`raw(content, format=...)` injects verbatim content into one or both outputs — the escape hatch for anything the element set doesn't cover:

```python
report.raw("<details><summary>More</summary>…</details>", format="html")
report.raw("[TOC]", format="markdown")   # e.g. a marker your MD pipeline expands
report.raw("---", format="both")         # default: emitted in both formats
```

Content with a non-matching format is silently skipped, so a single report definition can carry format-specific extras for both exports.

## Exporting

```python
markdown_text = report.to_markdown()
html_text     = report.to_html()

report.save_markdown("report.md")     # writes UTF-8, returns the Path
report.save_html("report.html")
```

`to_html()` / `save_html()` options:

- `full_document=False` returns only the body markup (`<h1>…` onward, no `<html>`, `<head>`, or CSS) — useful for embedding the report into an existing page or template.
- `css="..."` replaces the built-in stylesheet in the full document.

The renderers can also be used directly (e.g. to render a bare `Section`-free element tree or to subclass):

```python
from reportsmith import MarkdownRenderer, HtmlRenderer

MarkdownRenderer().render(report)
HtmlRenderer(full_document=False).render(report)
```

## Exporting to PDF

PDF export is an optional extra built on [fpdf2](https://py-pdf.github.io/fpdf2/):

```bash
pip install reportsmith[pdf]
```

```python
pdf_bytes = report.to_pdf()          # bytes
report.save_pdf("report.pdf")        # write to file
```

The PDF is an A4 document styled to match the HTML export: a title/metadata block, section headings sized by nesting depth, shaded code blocks, bordered tables with per-column alignment and captions, clickable links, and embedded images. Sections also become PDF **bookmarks** (the outline sidebar in PDF viewers).

Details and limitations:

- **Fonts and Unicode.** PDF core fonts only cover Latin-1, so the renderer auto-detects a Unicode-capable system family (Arial/Segoe UI on Windows, DejaVu on Linux, Arial on macOS — plus Consolas/DejaVu Mono for code) and embeds it. If none is found, it falls back to Helvetica/Courier and replaces unsupported characters with `?` instead of crashing. To control the typeface, pass explicit `(regular, bold, italic, bold-italic)` TTF paths:

  ```python
  report.save_pdf("report.pdf", fonts=(
      "fonts/MyFont-Regular.ttf", "fonts/MyFont-Bold.ttf",
      "fonts/MyFont-Italic.ttf", "fonts/MyFont-BoldItalic.ttf",
  ))
  ```

- **Table cells** render inline spans as plain text (no bold/links inside PDF table cells).
- **Missing images** render as a `[Image: alt]` placeholder instead of failing the export.
- **`raw(...)` content is skipped** — Markdown/HTML passthrough has no meaning in PDF.
- Without fpdf2 installed, `to_pdf()` raises `ImportError` with the install hint; the rest of the library is unaffected.

## Customizing the HTML output

The default stylesheet is a single CSS string, `reportsmith.renderers.html.DEFAULT_CSS`. It uses CSS variables and respects `prefers-color-scheme` for dark mode. To tweak rather than replace it, extend it:

```python
from reportsmith.renderers.html import DEFAULT_CSS

report.save_html("report.html", css=DEFAULT_CSS + """
:root { --accent: #b91c1c; }
h1 { text-transform: uppercase; }
""")
```

## Escaping and safety

All user text is escaped for the target format automatically:

- **HTML**: `<`, `>`, `&` in text and quotes in attributes are entity-escaped, including inside code blocks, table cells, link hrefs, image attributes, and the document `<title>`. Untrusted strings placed in normal elements cannot inject markup.
- **Markdown**: pipes in table cells are escaped; code fences widen when the source contains a fence.

The one deliberate exception is `raw(...)`, which is emitted verbatim — only pass trusted content to it.

## Error handling

Invalid input fails fast with `ValueError` at construction time:

- heading level outside 1–6
- table row width not matching the header count
- unknown `align` value or wrong `align` length
- unknown `raw` format

Rendering an element type the renderer doesn't know raises `TypeError` (relevant only if you define custom `Element` subclasses).
