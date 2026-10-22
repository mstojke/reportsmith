# reportsmith — User Guide

`reportsmith` lets you build a report programmatically from typed elements and export it to **Markdown**, a **standalone styled HTML page**, **LaTeX**, or **PDF**. It has no dependencies and works on Python 3.9+.

This guide walks through every feature. For a terse signature-level listing, see the [API reference](api-reference.rst).

## Contents

1. [Creating a report](#creating-a-report)
2. [Sections](#sections)
3. [Text and inline formatting](#text-and-inline-formatting) — including [footnotes](#footnotes)
4. [Tables](#tables) — including [tables from data](#tables-from-data)
5. [Lists](#lists) — including [definition and task lists](#definition-lists-and-task-lists)
6. [Code blocks, quotes, images, rules](#code-blocks-quotes-images-rules)
7. [Figures](#figures) — including [numbering and cross-references](#numbering-and-cross-references)
8. [Callouts](#callouts)
9. [Table of contents](#table-of-contents)
10. [Raw passthrough content](#raw-passthrough-content)
11. [Exporting](#exporting)
12. [Exporting to LaTeX](#exporting-to-latex)
13. [Exporting to PDF](#exporting-to-pdf)
14. [Customizing the HTML output](#customizing-the-html-output)
15. [Escaping and safety](#escaping-and-safety)

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

### Strikethrough, subscript, superscript

```python
from reportsmith import strike, sub, sup

s.paragraph(["Price: ", strike("$49"), " $39"])
s.paragraph(["H", sub("2"), "O boils at 100 °C; area is 12 m", sup("2"), "."])
```

| Helper | Markdown | HTML | LaTeX |
| --- | --- | --- | --- |
| `strike()` | `~~text~~` | `<del>` | `\sout{}` (ulem) |
| `sub()` | `<sub>` | `<sub>` | `\textsubscript{}` |
| `sup()` | `<sup>` | `<sup>` | `\textsuperscript{}` |

Markdown has no syntax for sub/superscript, so the HTML tags are used; GitHub and most Markdown renderers display them. PDF renders all three natively.

### Footnotes

`footnote(text)` places a numbered marker where it appears, with `text` as the note. Footnotes are numbered in document order and work anywhere inline text does — paragraphs, list items, table cells, callouts, even section titles:

```python
from reportsmith import footnote

s.paragraph(["Revenue grew 21%", footnote("Excluding the APAC acquisition."), " year over year."])
```

- **Markdown:** GitHub-style `[^1]` markers, with the definitions collected at the end of the document.
- **HTML:** linked superscript markers and a numbered notes list at the end, each with a link back to its marker.
- **LaTeX:** `\footnote{...}` — real page-bottom footnotes. A footnote in a heading is kept out of the table of contents and PDF bookmarks.
- **PDF:** linked superscript markers and a "Notes" section after the content (endnotes). In table cells, where styles can't mix, the marker is a superscript digit (or `[1]` with the Latin-1 fallback font).

Footnotes never appear in table of contents entries or heading anchors.

## Tables

```python
s.table(
    headers=["Region", "Revenue", "Change"],
    rows=[
        ["EMEA", "$1.2M", "+8%"],
        ["APAC", "$0.9M", "-2%"],
    ],
    caption="Revenue by region",              # optional; numbered "Table 1: ..."
    align=["left", "right", "right"],         # optional; per-column
    label="revenue",                          # optional; for ref("revenue")
)
```

- `align` entries are `"left"`, `"center"`, or `"right"`; the default is left for all columns.
- Every row must have the same number of cells as `headers` — a mismatch raises `ValueError` at construction time, not at render time.
- Cells accept inline formatting like any other text: `[["EMEA", bold("$1.2M")]]`.
- In Markdown, pipes in cell text are escaped and newlines inside a cell become `<br>` so the table stays valid.
- A captioned table is numbered — "Table 1: Revenue by region" — in every format; see [numbering and cross-references](#numbering-and-cross-references).

### Tables from data

Three helpers build a table straight from data, so you don't have to turn values into strings yourself:

```python
# A list of dicts: keys become headers (union of keys, first-seen order)
s.table_from_records([
    {"region": "EMEA", "revenue": 1_234_567.9, "growth": 0.08},
    {"region": "APAC", "revenue": 987_654.3, "growth": None},
])

# A CSV file path or open text file; the first row is the header
s.table_from_csv("sales.csv", delimiter=",", encoding="utf-8")

# A pandas DataFrame (pandas is optional — reportsmith never imports it)
s.table_from_dataframe(df, index=False)
```

All three accept the same options:

| Option | Effect |
| --- | --- |
| `columns=["growth", "region"]` | Select and order columns (second positional argument). Unknown names raise `ValueError`. |
| `headers={"revenue": "Revenue ($)"}` | Relabel columns: a mapping for some columns, or a list with one label per column. Labels may use inline formatting. |
| `formats="{:,.2f}"` | One format string or callable, applied to every **numeric** cell. |
| `formats={"revenue": "${:,.0f}", "growth": "{:+.1%}"}` | Per-column formats, applied to every value in that column; callables may return inline content, e.g. `{"region": bold}`. |
| `missing="—"` | Text for `None`, NaN, and pandas `NA`/`NaT` (default: empty cell). |
| `align=None` | Default: numeric columns are right-aligned, others left. Pass a list to override. |
| `caption="..."`, `label="..."` | Caption and cross-reference label, as for `table()`. |

Values without a format are rendered with `str()`. Booleans count as text, not numbers.

**CSV specifics:** with `parse_numbers=True` (the default), a column whose values all look like numbers is converted to `int`/`float`, so formats and right-alignment apply. Conversion is per column, all or nothing: integers with leading zeros (IDs, ZIP codes like `00501`) and values with thousands separators stay text, and so does the rest of their column. Blank lines are skipped, short rows are padded with missing cells, a leading byte-order mark is dropped, and a row with too many fields raises `ValueError`. Pass `parse_numbers=False` to keep every value as text.

**DataFrame specifics:** `index=True` adds the index as the first column, headed by the index name. Any object with `columns` and `itertuples()` works.

The same constructors are available as `Table.from_records(...)`, `Table.from_csv(...)` and `Table.from_dataframe(...)` when you want a `Table` to pass to `add()`.

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

### Definition lists and task lists

```python
s.definition_list([
    ("API", "Application programming interface"),
    ("SLA", ["Service level agreement — see ", link("the policy", "https://example.com/sla")]),
])
s.definition_list({"MRR": "Monthly recurring revenue"})   # a mapping works too

s.task_list([
    (True, "Write the docs"),
    (False, ["Ship ", code("v1.0")]),
])
```

Terms, definitions and task text accept inline formatting. Each entry must be a pair — `(term, definition)` or `(done, text)` with a `bool` first — or `ValueError` is raised. Empty lists render nothing.

| Format | Definition list | Task list |
| --- | --- | --- |
| Markdown | `- **Term**: definition` (Markdown has no standard definition-list syntax; this reads well everywhere) | `- [x] Done` / `- [ ] To do` (GitHub task lists) |
| HTML | `<dl>` with `<dt>` / `<dd>` | A list of disabled checkboxes |
| LaTeX | `description` environment | `itemize` with ☒ / ☐ markers (`amssymb`) |
| PDF | Bold term, indented definition | Drawn checkboxes (independent of the font) |

## Code blocks, quotes, images, rules

```python
s.code("SELECT * FROM sales;", language="sql")   # fenced / <pre><code>
s.quote("Any sufficiently advanced report is indistinguishable from magic.")
s.image("chart.png", alt="Revenue chart", title="Q3 revenue")
s.horizontal_rule()
```

- `language` becomes the fence info string in Markdown and a `language-*` class in HTML (ready for highlight.js/Prism if you add one via custom CSS/raw HTML).
- If the code itself contains ` ``` `, the Markdown fence automatically widens so the block stays intact.

### Page breaks

`page_break()` starts a new page: a new page in PDF (skipped when already at the top of a page, so it never leaves a blank one), `\clearpage` in LaTeX (which also places pending figures first), and a break when the HTML is printed. Markdown has no pages; it gets an invisible `<div style="break-after: page">` that takes effect when the Markdown is converted to HTML and printed.

## Figures

`figure(source, caption="", alt="", label="", width=None)` adds an image with an optional numbered caption. `source` can be:

- **an image file path** — referenced as-is in Markdown, HTML and LaTeX, embedded in PDF;
- **image bytes** — PNG, JPEG, GIF or SVG, detected from the content;
- **a plot** — a matplotlib figure, or any object with a matplotlib-style `savefig()` method (reportsmith never imports matplotlib itself).

```python
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(6, 3))
ax.plot(months, revenue)

s.figure(fig, caption="Monthly revenue", label="revenue-chart", width=0.8)
s.figure("diagram.png", caption="System overview")
s.figure(png_bytes, alt="Logo", width=0.2)          # no caption: not numbered
```

`width` is a fraction of the text width (`0.5` = half); by default figures fill the width in PDF and are scaled down to fit elsewhere. `alt` defaults to the caption. `dpi=200` sets the resolution plots are rendered at.

Where generated images (plots and bytes) go depends on the format:

| Format | Generated images |
| --- | --- |
| HTML | Embedded as data URIs, so the page stays a single self-contained file. Plots are PNG. |
| Markdown | `save_markdown("report.md")` writes them to a `report_files/` folder next to the file and links them relatively. `to_markdown()` embeds them as data URIs, or writes them to `assets_dir=` if you pass one. |
| LaTeX | `save_latex("report.tex")` writes them to `report_files/`; plots are saved as vector PDF. `to_latex()` needs `assets_dir=` for them, and raises `ValueError` without it. SVG bytes can't be used (LaTeX can't include SVG). |
| PDF | Embedded directly. A missing file renders a `[Figure: ...]` placeholder. |

`image(src, alt, title)` still exists for simple unnumbered images, including remote `http(s)://` images, which figures don't accept.

### Numbering and cross-references

Figures and tables **with a caption** are numbered separately, in document order — "Figure 1", "Figure 2", "Table 1" — in every format; items without a caption aren't numbered. Give an item a `label` and refer to it from any text with `ref()`:

```python
from reportsmith import ref

s.paragraph(["Revenue grew 21% (", ref("revenue"), "); ", ref("revenue-chart", "the chart"), " shows the trend."])
s.table(headers, rows, caption="Revenue by region", label="revenue")
```

`ref("revenue")` renders as "Table 1" — a link in HTML, LaTeX and PDF, plain text in Markdown — and `ref(label, "custom text")` uses your wording instead. References may come before or after their target. Labels use letters, digits, `_`, `.`, `:` and `-`; a label needs a caption (only numbered items can be referred to), a duplicate label raises `ValueError`, and so does `ref()` to a label that doesn't exist.

In LaTeX, numbers come from LaTeX itself (`\caption`, `\label`, `\ref`), and plain `image()` captions are unnumbered (`\caption*`), so they match the other formats.

## Callouts

`callout(kind, content=None, title="")` adds a highlighted box for notes, tips and warnings. There are five kinds, matching GitHub's alerts: `"note"`, `"tip"`, `"important"`, `"warning"` and `"caution"`.

```python
report.callout("note", "Figures are unaudited.")
report.callout("tip", ["Run ", code("make report"), " to regenerate."], title="Pro tip")

# Several blocks: use it like a section
with report.callout("warning", title="Breaking change") as c:
    c.paragraph("The v1 API is removed on 1 March:")
    c.bullet_list(["/v1/orders", "/v1/invoices"])
    c.code("curl https://api.example.com/v2/orders", language="bash")
```

`content`, if given, becomes the callout's first paragraph. `callout()` returns the new callout (not the container), so more content can be added — paragraphs, lists, code, tables, images, headings, even nested callouts. Sections and tables of contents aren't allowed inside a callout (they raise `TypeError`), so callouts never change the document outline; headings inside one stay out of the table of contents.

The title defaults to the capitalized kind ("Warning"). Rendering:

| Format | Output |
| --- | --- |
| Markdown | A GitHub alert: `> [!WARNING]` followed by the content. Alerts have no custom titles, so a `title` becomes a bold first line. Other Markdown viewers show a block quote. |
| HTML | `<div class="callout callout-warning">` with a coloured left border and title, styled for light and dark mode by the default stylesheet. |
| LaTeX | A coloured `tcolorbox` that can break across pages. |
| PDF | A coloured bar and title; the bar continues across page breaks. |

## Table of contents

`toc(title="Contents", depth=3)` adds a table of contents listing every section and explicit heading in the report, in document order. It always covers the whole report, so it can go anywhere — usually right after creating the report:

```python
report = Report("Q3 Sales Report")
report.toc()                       # or report.toc(title="In this report", depth=1)

with report.section("Overview") as s:        # depth 1
    with s.section("By region") as r:        # depth 2
        r.section("EMEA")                    # depth 3
```

`depth` (1–5) controls how many levels are listed: `1` lists only top-level sections, `2` adds their subsections, and so on. Pass `title=""` to omit the title line.

How each format renders it:

| Format | Output |
| --- | --- |
| Markdown | A bold title and a nested bullet list of links to GitHub-style heading anchors (`#overview`, repeated titles get `-1`, `-2`, …) |
| HTML | A `<nav class="toc">` with nested links; headings get matching `id` attributes (only when the report has a TOC). Styled by the default stylesheet. |
| LaTeX | `\tableofcontents` with `tocdepth` set to `depth`. Compile twice so LaTeX can fill it in. |
| PDF | Clickable entries with right-aligned page numbers; long titles are truncated with an ellipsis. |

Entries use the plain text of each title in Markdown and PDF; HTML keeps inline formatting such as bold. In PDF only the first TOC in a report is rendered (an fpdf2 limitation), and content after it starts on a new page.

## Raw passthrough content

`raw(content, format=...)` injects verbatim content into one or both outputs — the escape hatch for anything the element set doesn't cover:

```python
report.raw("<details><summary>More</summary>…</details>", format="html")
report.raw("[TOC]", format="markdown")   # e.g. a marker your MD pipeline expands
report.raw("\\newpage", format="latex")  # LaTeX export only
report.raw("---", format="both")         # default: emitted in Markdown and HTML
```

Content with a non-matching format is silently skipped, so a single report definition can carry format-specific extras for every export. `"both"` means Markdown and HTML only — LaTeX only receives `format="latex"` content, and PDF skips raw content entirely.

## Exporting

```python
markdown_text = report.to_markdown()
html_text     = report.to_html()

report.save_markdown("report.md")     # writes UTF-8, returns the Path
report.save_html("report.html")

report.save("report.pdf")             # format from the extension
report.save("report.html", full_document=False)   # options go to save_html()
```

`save(path, **options)` picks the format from the file extension — `.md` / `.markdown`, `.html` / `.htm`, `.tex`, `.pdf` (case-insensitive) — and passes any options to the matching `save_*` method. Other extensions raise `ValueError`.

Generated figure images are embedded in HTML; `save_markdown()` writes them into a `report_files/` folder next to the file (see [Figures](#figures)).

`to_html()` / `save_html()` options:

- `full_document=False` returns only the body markup (`<h1>…` onward, no `<html>`, `<head>`, or CSS) — useful for embedding the report into an existing page or template.
- `css="..."` replaces the built-in stylesheet in the full document.

The renderers can also be used directly (e.g. to render a bare `Section`-free element tree or to subclass):

```python
from reportsmith import MarkdownRenderer, HtmlRenderer

MarkdownRenderer().render(report)
HtmlRenderer(full_document=False).render(report)
```

## Exporting to LaTeX

LaTeX export needs no extra dependencies — it produces `.tex` source that you compile with your own TeX distribution:

```python
latex_text = report.to_latex()
report.save_latex("report.tex")
```

```bash
pdflatex report.tex
```

The document compiles with pdfLaTeX, XeLaTeX, or LuaLaTeX. It uses the `article` class with a `\maketitle` title block (subtitle under the title, author, date), `booktabs` tables via `longtable` (they break across pages and repeat the header), framed `fancyvrb` code blocks, `hyperref` links, and PDF bookmarks from sections. Run the compiler twice if a long table's column widths look off — `longtable` settles widths on the second pass.

Options (on `to_latex()`, `save_latex()`, and `LatexRenderer`):

- `full_document=False` returns only the body (sections onward — no preamble, title block, or `\begin{document}`), ready to `\input` into your own document. Your document then needs the packages listed in `reportsmith.renderers.latex.DEFAULT_PREAMBLE`, and the `rscallout` environment and `rs*` colours defined there if the report contains callouts.
- `document_class="report"` / `class_options="12pt,letterpaper"` change the `\documentclass` line.
- `preamble="..."` is appended after the built-in preamble, e.g. `preamble="\\usepackage{amsmath}"` or `\\renewcommand` tweaks.
- `numbered=True` numbers sections; by default they are unnumbered (but still bookmarked).
- `assets_dir=...` (on `to_latex()` and `LatexRenderer`): where to write figures made from plots or image bytes. `save_latex()` uses a `<name>_files/` folder automatically.

Details and limitations:

- **Section depth** maps to `\section`, `\subsection`, `\subsubsection`, `\paragraph`, `\subparagraph`.
- **Images** are embedded with `\includegraphics` in a figure (the title, or else the alt text, becomes an unnumbered caption) and scaled down to the text width if needed. Paths are resolved relative to where you compile, and a missing file is a compile error. `http(s)://` images can't be embedded, so they render as a link instead.
- **Lists** nest at most four levels deep (a LaTeX limit). Empty lists are omitted.
- **Multi-line table cells** are rendered as stacked lines within the cell.

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

- **Table cells** keep bold, italic, strikethrough and clickable links. Code spans and cross-references show as plain text there (cells can't switch fonts or hold internal links), and digit sub/superscripts use Unicode characters such as m² when the font has them.
- **Missing images** render as an `[Image: alt]` (or `[Figure: ...]`) placeholder instead of failing the export.
- **`raw(...)` content is skipped** — Markdown/HTML/LaTeX passthrough has no meaning in PDF.
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
- **LaTeX**: `\ & % $ # _ { } ~ ^` and square brackets are escaped in all text, metadata, and captions; link targets are escaped for `\href`; code blocks escape only `\ { }`, so source containing `\end{Verbatim}` can't break out.

The one deliberate exception is `raw(...)`, which is emitted verbatim — only pass trusted content to it.

## Error handling

Invalid input fails fast with `ValueError` at construction time:

- heading level outside 1–6
- table row width not matching the header count
- unknown `align` value or wrong `align` length
- unknown `raw` format
- a definition-list entry that isn't a `(term, definition)` pair, or a task that isn't a `(done, text)` pair with a `bool` first
- figure source that isn't a path, image bytes or plot; invalid `width`; invalid label, or a label without a caption

Duplicate labels and `ref()` to an unknown label raise `ValueError` when the report is rendered.

Rendering an element type the renderer doesn't know raises `TypeError` (relevant only if you define custom `Element` subclasses).
