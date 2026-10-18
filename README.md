# reportsmith

[![Tests](https://github.com/mstojke/reportsmith/actions/workflows/tests.yml/badge.svg)](https://github.com/mstojke/reportsmith/actions/workflows/tests.yml)
[![Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/mstojke/reportsmith/badges/coverage.json)](https://github.com/mstojke/reportsmith/actions/workflows/tests.yml)

A small, dependency-free Python library for building reports programmatically and exporting them to **Markdown**, a **standalone styled HTML** document, **LaTeX**, or (optionally) **PDF**.

## Features

- Fluent builder API with chainable methods and nested sections (`with report.section(...)`)
- Table of contents in every format: linked lists in Markdown/HTML, `\tableofcontents` in LaTeX, clickable entries with page numbers in PDF
- Tables straight from data: lists of dicts, CSV files, or pandas DataFrames, with number formatting, missing-value placeholders, and automatic right-alignment of numeric columns
- Elements: headings, paragraphs, tables (with alignment and captions), bullet/numbered lists (nestable), code blocks, block quotes, images, horizontal rules, and format-specific raw passthrough
- Inline formatting helpers: `bold()`, `italic()`, `code()`, `link()`, `strike()`, `sub()`, `sup()`, and numbered `footnote()`s — rendered natively in every format
- Callouts (note, tip, important, warning, caution): GitHub alerts in Markdown, coloured boxes in HTML, LaTeX and PDF
- Correct escaping everywhere: HTML entities, Markdown table pipes, code fences that widen when the source contains ` ``` `
- HTML export ships with a clean embedded stylesheet (light/dark aware) that you can replace with your own CSS
- LaTeX export: a compilable document (pdfLaTeX/XeLaTeX/LuaLaTeX) with booktabs tables, framed code blocks, hyperlinks, and PDF bookmarks — or a body fragment to `\input` into your own document
- Optional PDF export (`pip install reportsmith[pdf]`, via fpdf2): matching styling, PDF bookmarks from sections, clickable links, auto-detected Unicode system fonts
- No required dependencies; Python 3.9+

## Installation

```bash
pip install -e .
```

Or just copy the `reportsmith/` package into your project — it has no dependencies.

## Quick start

```python
from reportsmith import Report, bold, link

report = Report("Q3 Sales Report", author="Jane Doe", subtitle="Quarterly summary")
report.toc()                         # table of contents

with report.section("Overview") as s:
    s.paragraph(["Revenue was ", bold("up 12%"), " quarter over quarter."])
    s.table(
        ["Region", "Revenue"],
        [["EMEA", "$1.2M"], ["APAC", "$0.9M"]],
        caption="Revenue by region",
        align=["left", "right"],
    )

with report.section("Next steps") as s:
    s.numbered_list([
        "Expand APAC sales team",
        ["Review ", link("pricing proposal", "https://example.com/pricing")],
    ])

print(report.to_markdown())          # Markdown string
print(report.to_html())              # standalone HTML page
report.save_markdown("report.md")
report.save_html("report.html")
report.save_latex("report.tex")    # compile with pdflatex/xelatex/lualatex
```

Run `python example.py` for a fuller demo that writes `example_report.md`, `example_report.html`, and `example_report.tex`.

## Documentation

- **[User Guide](https://github.com/mstojke/reportsmith/blob/main/docs/user-guide.md)** — a walkthrough of every feature with examples: sections, inline formatting, tables, lists, raw passthrough, HTML customization, and escaping behavior.
- **[API Reference](https://github.com/mstojke/reportsmith/blob/main/docs/api-reference.rst)** — signatures, parameters, and exceptions for every public class and function (reStructuredText, Sphinx-ready).

The docs are also a buildable Sphinx site:

```bash
pip install -e .[docs]
```

```bash
python -m sphinx -b html docs docs/_build/html
```

Then open `docs/_build/html/index.html`.

## API overview

### `Report(title, author="", date=None, subtitle="")`

`date` accepts a string, `datetime.date`, or `datetime.datetime`; it defaults to today.

Builder methods (all chainable, also available on sections):

| Method | Adds |
| --- | --- |
| `section(title)` | Nested section; heading level tracks nesting depth. Usable as a context manager. |
| `heading(text, level=None)` | Explicit heading (level defaults to the container's depth + 1) |
| `paragraph(content)` | Paragraph |
| `quote(content)` | Block quote |
| `code(source, language="")` | Fenced/`<pre>` code block |
| `bullet_list(items)` / `numbered_list(items)` | List; items may be text or a nested `ListElement` |
| `table(headers, rows, caption="", align=None)` | Table; `align` entries are `"left"`, `"center"`, `"right"` |
| `table_from_records(records)` / `table_from_csv(source)` / `table_from_dataframe(df)` | Table built from data; options `columns`, `headers`, `formats`, `missing`, `align`, `caption` |
| `image(src, alt="", title="")` | Image |
| `horizontal_rule()` | Rule |
| `raw(content, format="both")` | Verbatim content for `"markdown"`, `"html"`, `"latex"`, or `"both"` (Markdown + HTML) |
| `toc(title="Contents", depth=3)` | Table of contents for the whole report; `depth` 1–5 sets how many heading levels are listed |
| `callout(kind="note", content=None, title="")` | Callout box (`"note"`, `"tip"`, `"important"`, `"warning"`, `"caution"`); returns the callout, usable as a context manager |
| `add(element)` | Any pre-built element |

Anywhere text is accepted you may pass a plain string or a list mixing strings with `bold()`, `italic()`, `code()`, and `link(text, href)` spans.

### Export

- `report.to_markdown()` → GitHub-flavored Markdown string
- `report.to_html(full_document=True, css=None)` → HTML string; `full_document=False` returns just the body fragment, `css=` replaces the default stylesheet
- `report.to_latex(full_document=True, document_class="article", class_options="11pt,a4paper", preamble="", numbered=False)` → LaTeX source; `full_document=False` returns just the body, `preamble=` is appended to the built-in preamble
- `report.to_pdf(fonts=None, mono_fonts=None)` → PDF bytes (requires the `pdf` extra); pass TTF path quadruples to control typefaces
- `report.save_markdown(path)` / `report.save_html(path, ...)` / `report.save_latex(path, ...)` / `report.save_pdf(path, ...)` → write to a file, return the `Path`

## Running tests

Install the development dependencies (pytest, coverage, the optional fpdf2 and pandas integrations, pypdf for checking PDF output, ruff and mypy):

```bash
pip install -e .[dev]
```

The test suite lives in `tests/`. Tests for optional integrations are skipped when their package isn't installed.

```bash
python -m pytest
```

With a coverage report:

```bash
python -m pytest --cov=reportsmith --cov-report=term-missing
```

Lint and type-check:

```bash
ruff check .
```

```bash
mypy
```

CI runs all of these on Python 3.9–3.14, runs the suite once more with no optional dependencies installed, and compiles the LaTeX output of every example with pdfLaTeX, XeLaTeX, and LuaLaTeX.

## Changelog

See [CHANGELOG.md](https://github.com/mstojke/reportsmith/blob/main/CHANGELOG.md) — the format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## License

MIT
