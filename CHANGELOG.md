# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Table of contents (`toc(title="Contents", depth=3)`, `TableOfContents`)
  in all four formats. It lists every section and explicit heading up to
  `depth` levels. Markdown gets a nested list of links to GitHub-style
  heading anchors; HTML gets a styled `<nav class="toc">` with matching
  heading `id`s; LaTeX gets `\tableofcontents` with `tocdepth`; PDF gets
  clickable entries with page numbers, spanning as many pages as needed.

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
