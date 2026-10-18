# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- CI now also tests on Python 3.14.

### Changed

- GitHub Actions updated to their Node.js 24 releases, ending the Node.js
  20 deprecation warnings: `actions/checkout` v7, `actions/setup-python`
  v7, `actions/upload-artifact` v7 and `actions/download-artifact` v8
  (which now fails a release build on an artifact checksum mismatch
  instead of warning).
- The Python version test matrix runs on `ubuntu-24.04` instead of
  `ubuntu-latest`, because there is no Python 3.9 build for Ubuntu 26.04.

## [0.4.0] - 2026-10-18

### Added

- Callouts (`callout(kind, content=None, title="")`, `Callout`) in five
  kinds: note, tip, important, warning, caution. Usable as a context
  manager to hold paragraphs, lists, code, tables and nested callouts.
  Markdown renders GitHub alerts (`> [!NOTE]`); HTML a coloured box styled
  for light and dark mode; LaTeX a breakable `tcolorbox`; PDF a coloured
  bar and title that continue across page breaks.
- Inline styles `strike()`, `sub()` and `sup()`, rendered natively in all
  four formats.
- Footnotes (`footnote(text)`), numbered in document order: GitHub `[^n]`
  footnotes in Markdown, a linked notes list in HTML, `\footnote` in LaTeX
  (with a footnote-free short title for headings), and linked endnotes in
  PDF. Footnotes are kept out of TOC entries and heading anchors.
- `py.typed` marker: the package's type hints are now used by type
  checkers.
- CI workflow: tests on Python 3.9–3.13, a run with no optional
  dependencies, ruff and mypy, and compiling every example's LaTeX output
  with pdfLaTeX, XeLaTeX and LuaLaTeX.

### Changed

- The LaTeX preamble now also loads `ulem` (with `normalem`, so `\emph`
  is unchanged) and `tcolorbox`, and defines the `rscallout` environment.
- The `dev` extra now includes pandas, pypdf, ruff and mypy.

### Fixed

- Tests for optional integrations no longer skip their whole test module
  when fpdf2 or pandas is missing; only the tests that need them skip.
- The user guide's broken "Exporting to PDF" link now has a section to
  point to.

## [0.3.0] - 2026-10-15

### Added

- Table of contents (`toc(title="Contents", depth=3)`, `TableOfContents`)
  in all four formats. It lists every section and explicit heading up to
  `depth` levels. Markdown gets a nested list of links to GitHub-style
  heading anchors; HTML gets a styled `<nav class="toc">` with matching
  heading `id`s; LaTeX gets `\tableofcontents` with `tocdepth`; PDF gets
  clickable entries with page numbers, spanning as many pages as needed.
- Tables from data: `table_from_records()`, `table_from_csv()` and
  `table_from_dataframe()` (also `Table.from_records()` etc.). Options to
  select and relabel columns, format numbers per column or globally, set a
  placeholder for None/NaN/NA, and right-align numeric columns
  automatically. CSV numbers are parsed per column, keeping IDs with
  leading zeros as text. pandas is supported without being a dependency.

## [0.2.0] - 2026-08-26

### Added

- LaTeX export (`to_latex()` / `save_latex()`, `LatexRenderer`): a
  standalone document that compiles with pdfLaTeX, XeLaTeX, or LuaLaTeX, or
  a body fragment with `full_document=False`. Options for the document
  class, class options, extra preamble, and section numbering. Uses
  `booktabs`/`longtable` tables, framed `fancyvrb` code blocks, `hyperref`
  links and bookmarks, and figures for images; all text is LaTeX-escaped.
- `raw(content, format="latex")` for LaTeX-only passthrough content.

## [0.1.0] - 2026-08-26

### Added

- `Report` class with a fluent, chainable builder API and report metadata
  (title, subtitle, author, date).
- Nestable sections (`section()`, usable as context managers) with heading
  levels derived automatically from nesting depth (capped at 6).
- Block elements: headings, paragraphs, block quotes, fenced code blocks,
  bullet and numbered lists (nestable), tables with per-column alignment and
  captions, images, horizontal rules, and format-specific raw passthrough
  (`raw(content, format="markdown" | "html" | "both")`).
- Inline formatting helpers `bold()`, `italic()`, `code()`, and
  `link(text, href)`, accepted anywhere text is expected.
- Markdown export (`to_markdown()` / `save_markdown()`): GitHub-flavored
  output with escaped table pipes, `<br>` for newlines in cells, and code
  fences that widen when the source itself contains a fence.
- HTML export (`to_html()` / `save_html()`): standalone page with an
  embedded light/dark-aware stylesheet (replaceable via `css=`), or a body
  fragment with `full_document=False`; all content HTML-escaped.
- Optional PDF export (`to_pdf()` / `save_pdf()`, `pip install
  reportsmith[pdf]`, built on fpdf2): A4 output styled to match the HTML
  export, PDF outline bookmarks from sections, clickable links, embedded
  images with graceful placeholders for missing files, and auto-detected
  Unicode system fonts with a Latin-1 core-font fallback.
- Fail-fast validation (`ValueError` at construction) for heading levels,
  table row widths, column alignment values, and raw formats.
- Test suite (105 tests, ~99% line coverage) runnable with `python -m pytest`.
- Documentation: README, Markdown user guide, reStructuredText API
  reference, and a buildable Sphinx site using the Read the Docs theme
  (`pip install -e .[docs]`, then
  `python -m sphinx -b html docs docs/_build/html`).
- Packaging via `pyproject.toml` with optional extras: `pdf`, `dev`, `docs`.
