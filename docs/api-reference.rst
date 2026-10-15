===========================
reportsmith — API Reference
===========================

Terse signature-level reference. For a walkthrough with examples, see the
:doc:`user-guide`.

Everything documented here is importable from the top-level package:

.. code-block:: python

   from reportsmith import (
       Report, Section,
       Heading, Paragraph, Quote, CodeBlock, ListElement, Table, Image,
       HorizontalRule, Raw, TableOfContents,
       Inline, bold, italic, code, link,
       MarkdownRenderer, HtmlRenderer, LatexRenderer, PdfRenderer,
   )

Type aliases
============

.. py:data:: TextLike

   Accepted anywhere inline text is expected: a :class:`str`, an
   :class:`Inline` span, or a sequence mixing both. Non-string sequence
   items are coerced with ``str()``.

Report
======

.. py:class:: Report(title, author="", date=None, subtitle="")

   Top-level container.

   :param str title: Report title; renders as the single ``h1``.
   :param str author: Optional author line.
   :param date: Defaults to today in ISO format. :class:`datetime.date` and
      :class:`datetime.datetime` objects are converted via ``.isoformat()``;
      pass ``""`` to suppress the date line.
   :type date: str | datetime.date | datetime.datetime | None
   :param str subtitle: Optional subtitle line.

   Inherits the full builder API from :class:`Container` and adds the
   export methods below.

   .. py:method:: to_markdown() -> str

      Render the report as GitHub-flavored Markdown.

   .. py:method:: to_html(full_document=True, css=None) -> str

      Render the report as HTML: a full standalone page with embedded CSS,
      or just the body markup when ``full_document=False``. ``css`` replaces
      the default stylesheet.

   .. py:method:: save_markdown(path) -> pathlib.Path

      Write UTF-8 Markdown to *path* and return it.

   .. py:method:: save_html(path, full_document=True, css=None) -> pathlib.Path

      Write UTF-8 HTML to *path* and return it.

   .. py:method:: to_latex(full_document=True, document_class="article", class_options="11pt,a4paper", preamble="", numbered=False) -> str

      Render the report as LaTeX source. See :class:`LatexRenderer` for the
      parameters.

   .. py:method:: save_latex(path, full_document=True, document_class="article", class_options="11pt,a4paper", preamble="", numbered=False) -> pathlib.Path

      Write UTF-8 LaTeX to *path* and return it.

   .. py:method:: to_pdf(fonts=None, mono_fonts=None) -> bytes

      Render the report as PDF bytes. Requires the optional ``fpdf2``
      dependency (``pip install reportsmith[pdf]``); raises
      :class:`ImportError` with an install hint otherwise. See
      :class:`PdfRenderer` for the font parameters.

   .. py:method:: save_pdf(path, fonts=None, mono_fonts=None) -> pathlib.Path

      Write the PDF export to *path* and return it (requires ``fpdf2``).

Container (builder API)
=======================

.. py:class:: Container

   Mixin shared by :class:`Report` and :class:`Section`. Every method
   appends an element and returns the container, so calls chain.
   :class:`Report` sits at heading level 1; each nested :class:`Section` is
   one level deeper (capped at 6).

   .. py:attribute:: children
      :type: list[Element]

      The elements added so far, in order.

   .. py:method:: section(title) -> Section

      Add a nested :class:`Section`. Returns the *new* section (not the
      container), usable as a context manager.

   .. py:method:: heading(content, level=None) -> Container

      Add a :class:`Heading`; ``level`` defaults to container depth + 1
      (capped at 6).

   .. py:method:: paragraph(content) -> Container

      Add a :class:`Paragraph`.

   .. py:method:: quote(content) -> Container

      Add a :class:`Quote`.

   .. py:method:: code(source, language="") -> Container

      Add a :class:`CodeBlock`.

   .. py:method:: bullet_list(items) -> Container

      Add a :class:`ListElement` with ``ordered=False``.

   .. py:method:: numbered_list(items) -> Container

      Add a :class:`ListElement` with ``ordered=True``.

   .. py:method:: table(headers, rows, caption="", align=None) -> Container

      Add a :class:`Table`.

   .. py:method:: table_from_records(records, columns=None, **options) -> Container
   .. py:method:: table_from_csv(source, columns=None, **options) -> Container
   .. py:method:: table_from_dataframe(df, columns=None, **options) -> Container

      Add a :class:`Table` built with :meth:`Table.from_records`,
      :meth:`Table.from_csv` or :meth:`Table.from_dataframe`; ``options``
      are passed through.

   .. py:method:: image(src, alt="", title="") -> Container

      Add an :class:`Image`.

   .. py:method:: horizontal_rule() -> Container

      Add a :class:`HorizontalRule`.

   .. py:method:: raw(content, format="both") -> Container

      Add a :class:`Raw` passthrough block.

   .. py:method:: toc(title="Contents", depth=3) -> Container

      Add a :class:`TableOfContents` for the whole report.

   .. py:method:: add(element) -> Container

      Append any pre-built :class:`Element`.

Elements
========

All elements subclass ``reportsmith.elements.Element`` and are
render-agnostic.

.. py:class:: Section(title, level=1)

   Titled container; includes the full builder API from
   :class:`Container`. ``__enter__``/``__exit__`` are no-ops so it can be
   used with ``with`` for indentation. Renders as a heading at its depth
   followed by its children.

.. py:class:: Heading(content, level=1)

   :raises ValueError: unless ``1 <= level <= 6``.

.. py:class:: Paragraph(content)

.. py:class:: Quote(content)

   Renders as ``>``-prefixed lines (multiline-aware) in Markdown and
   ``<blockquote>`` in HTML.

.. py:class:: CodeBlock(source, language="")

   Markdown: fenced block whose fence widens if *source* contains a
   triple-backtick fence. HTML: ``<pre><code class="language-...">`` with
   escaped source.

.. py:class:: ListElement(items, ordered=False)

   Items are ``TextLike`` or nested :class:`ListElement` instances. A
   nested list attaches to the preceding item (indents in Markdown; goes
   inside the previous ``<li>`` in HTML) and does not consume a number in
   ordered lists.

.. py:class:: Table(headers, rows, caption="", align=None)

   :param headers: ``Sequence[TextLike]`` — one entry per column.
   :param rows: ``Sequence[Sequence[TextLike]]``.
   :param str caption: Italic line after the table (Markdown) or
      ``<caption>`` (HTML).
   :param align: One of ``"left"``, ``"center"``, ``"right"`` per column;
      default all-left.
   :raises ValueError: for row-width mismatch, wrong ``align`` length, or
      an invalid ``align`` value.

   Markdown cells escape ``|`` and turn embedded newlines into ``<br>``.

   The constructors below share these keyword options:

   :param columns: Column keys to include, in order (second positional
      argument); default all.
   :param headers: Display labels — a sequence with one ``TextLike`` per
      selected column, or a mapping from column key to label.
   :param formats: A format string (``"{:,.2f}"``) or callable applied to
      every numeric cell, or a mapping from column key to format applied to
      every non-missing value in that column. Callables may return any
      ``TextLike``.
   :param align: As above; ``None`` right-aligns columns whose non-missing
      values are all numbers (``bool`` excluded) and left-aligns the rest.
   :param str missing: Cell text for ``None``, NaN, and pandas ``NA`` /
      ``NaT``; default ``""``.
   :param str caption: As above.
   :raises ValueError: for column names in ``columns``, ``headers`` or
      ``formats`` that don't exist, or a ``headers`` sequence of the wrong
      length.

   .. py:classmethod:: from_records(records, columns=None, *, headers=None, formats=None, align=None, missing="", caption="") -> Table

      Rows from an iterable of mappings. Columns default to the union of
      keys in first-seen order; keys absent from a record are missing.

      :raises TypeError: if a record is not a mapping.

   .. py:classmethod:: from_csv(source, columns=None, *, delimiter=",", encoding="utf-8", parse_numbers=True, headers=None, formats=None, align=None, missing="", caption="") -> Table

      Rows from a CSV file path or open text file; the first row is the
      header. With ``parse_numbers``, a column whose values all parse as
      numbers becomes ``int``/``float`` (integers with leading zeros and
      thousands separators stay text). Empty fields are missing, short rows
      are padded, blank lines are skipped and a leading BOM is dropped.

      :raises ValueError: for empty input or a row with too many fields.

   .. py:classmethod:: from_dataframe(df, columns=None, *, index=False, headers=None, formats=None, align=None, missing="", caption="") -> Table

      Rows from a pandas DataFrame (or any object with ``columns`` and
      ``itertuples()``); pandas is not imported. ``index=True`` prepends the
      index as a column headed by the index name.

      :raises TypeError: if *df* is not DataFrame-like.

.. py:class:: Image(src, alt="", title="")

.. py:class:: HorizontalRule()

.. py:class:: Raw(content, format="both")

   Verbatim passthrough. ``format`` is ``"markdown"``, ``"html"``,
   ``"latex"``, or ``"both"`` (Markdown and HTML); the content is emitted
   only when the output format matches, otherwise skipped.

   :raises ValueError: for any other ``format`` value.

   .. warning:: Content is **not escaped** — pass trusted content only.

.. py:class:: TableOfContents(title="Contents", depth=3)

   Lists every :class:`Section` and :class:`Heading` in the report, in
   document order, wherever the element is placed. ``depth`` limits the
   levels listed (1 = top-level sections only); an empty ``title`` omits
   the title line.

   Markdown: bold title plus a nested list of links to GitHub-style heading
   anchors. HTML: ``<nav class="toc">`` with nested links; headings gain
   matching ``id`` attributes. LaTeX: ``\tableofcontents`` with
   ``tocdepth`` set to ``depth`` (needs two compilation passes). PDF:
   linked entries with page numbers; only the first TOC in a report is
   rendered, and content after it starts on a new page.

   :raises ValueError: unless ``1 <= depth <= 5``.

Inline spans
============

.. py:class:: Inline(style, text, href="")

   Frozen dataclass representing a styled span of text. An ``Inline`` with
   an unknown style renders as its plain text in both formats.

.. py:function:: bold(text) -> Inline

   Markdown ``**text**``; HTML ``<strong>``.

.. py:function:: italic(text) -> Inline

   Markdown ``*text*``; HTML ``<em>``.

.. py:function:: code(text) -> Inline

   Markdown ````text````; HTML ``<code>``.

.. py:function:: link(text, href) -> Inline

   Markdown ``[text](href)``; HTML ``<a href="...">``.

Renderers
=========

Each renderer exposes ``render(report)``. :meth:`Report.to_markdown`,
:meth:`Report.to_html`, :meth:`Report.to_latex`, and :meth:`Report.to_pdf`
are convenience wrappers around these.

.. py:class:: MarkdownRenderer()

   GitHub-flavored Markdown. Blocks are separated by blank lines; table
   alignment uses ``:---`` / ``:---:`` / ``---:`` markers.

   .. py:method:: render(report) -> str

.. py:class:: HtmlRenderer(full_document=True, css=None)

   :param bool full_document: ``True`` produces a complete
      ``<!DOCTYPE html>`` page with ``<title>`` from the report title and
      the stylesheet embedded in ``<style>``; ``False`` produces body
      markup only.
   :param css: ``None`` uses ``reportsmith.renderers.html.DEFAULT_CSS`` — a
      variable-based stylesheet with automatic dark mode
      (``prefers-color-scheme``). Pass any CSS string to replace it, or
      concatenate with ``DEFAULT_CSS`` to extend it.

   All text content and attribute values are HTML-escaped; table alignment
   is emitted as inline ``text-align`` styles.

   .. py:method:: render(report) -> str

.. py:class:: LatexRenderer(full_document=True, document_class="article", class_options="11pt,a4paper", preamble="", numbered=False)

   :param bool full_document: ``True`` produces a complete document
      (preamble, ``\maketitle`` block, body) that compiles with pdfLaTeX,
      XeLaTeX, or LuaLaTeX; ``False`` produces the body only, for
      ``\input`` into an existing document.
   :param str document_class: The ``\documentclass``.
   :param str class_options: Class options; ``""`` for none.
   :param str preamble: Extra preamble appended after
      ``reportsmith.renderers.latex.DEFAULT_PREAMBLE``.
   :param bool numbered: Number sections. Unnumbered sections are still
      bookmarked.

   All text is LaTeX-escaped (also available as
   ``reportsmith.renderers.latex.escape_latex``). Tables use ``longtable``
   and ``booktabs``; code blocks use ``fancyvrb``; remote (``http(s)://``)
   images render as links; empty lists and zero-column tables are omitted;
   only :class:`Raw` content with ``format="latex"`` is emitted.

   .. py:method:: render(report) -> str

.. py:class:: PdfRenderer(fonts=None, mono_fonts=None)

   Renders a Report to an A4 PDF document. Requires the optional ``fpdf2``
   dependency (``pip install reportsmith[pdf]``), imported lazily on
   :meth:`render <PdfRenderer.render>`.

   :param fonts: optional ``(regular, bold, italic, bold-italic)`` TTF path
      quadruple for body text. ``None`` auto-detects a Unicode-capable
      system family (Arial/Segoe UI on Windows, DejaVu on Linux, Arial on
      macOS); ``()`` forces the built-in Latin-1 core Helvetica, degrading
      unsupported characters to ``?``.
   :param mono_fonts: same, for code; auto-detects Consolas/DejaVu Mono and
      falls back to core Courier.

   Sections become PDF outline bookmarks; links are clickable; missing
   images render as a ``[Image: alt]`` placeholder; table cells are
   rendered as plain text; :class:`Raw` content is skipped.

   .. py:method:: render(report) -> bytes

Exceptions
==========

===================================================  ==============================
Condition                                            Raised
===================================================  ==============================
Heading level outside 1–6                            ``ValueError`` (construction)
Table row width mismatch                             ``ValueError`` (construction)
Invalid or mis-sized ``align``                       ``ValueError`` (construction)
Invalid ``Raw`` format                               ``ValueError`` (construction)
``TableOfContents`` depth outside 1–5                ``ValueError`` (construction)
Renderer meets an unknown ``Element`` subclass       ``TypeError`` (render)
PDF export without ``fpdf2`` installed               ``ImportError`` (render)
===================================================  ==============================
