===========================
reportsmith — API Reference
===========================

Terse signature-level reference. For a walkthrough with examples, see the
:doc:`user-guide`.

Everything documented here is importable from the top-level package:

.. code-block:: python

   from reportsmith import (
       Report, Section,
       Heading, Paragraph, Quote, CodeBlock, ListElement, DefinitionList,
       TaskList, PageBreak, Table, Image,
       HorizontalRule, Raw, TableOfContents, Callout, Figure,
       Inline, bold, italic, code, link, strike, sub, sup, footnote, ref,
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

.. py:class:: Report(title, author="", date=None, subtitle="", description="", keywords=(), language="en")

   Top-level container.

   :param str title: Report title; renders as the single ``h1``.
   :param str author: Optional author line.
   :param date: Defaults to today in ISO format. :class:`datetime.date` and
      :class:`datetime.datetime` objects are converted via ``.isoformat()``;
      pass ``""`` to suppress the date line.
   :type date: str | datetime.date | datetime.datetime | None
   :param str subtitle: Optional subtitle line.
   :param str description: Document description: HTML ``<meta
      name="description">``, PDF subject, LaTeX ``pdfsubject``, Markdown
      front matter.
   :param keywords: Sequence of strings: HTML ``<meta name="keywords">``,
      PDF keywords, LaTeX ``pdfkeywords``, Markdown front matter.
   :param str language: Language tag: HTML ``lang``, PDF language, LaTeX
      ``pdflang``, Markdown front matter ``lang``.
   :raises TypeError: if *keywords* is a single string.

   Inherits the full builder API from :class:`Container` and adds the
   export methods below.

   .. py:method:: to_markdown(assets_dir=None, front_matter=False) -> str

      Render the report as GitHub-flavored Markdown. Figures made from plots
      or image bytes are embedded as data URIs, or written as files into
      *assets_dir* when given. ``front_matter=True`` starts the document
      with a YAML block of the report's metadata.

   .. py:method:: to_html(full_document=True, css=None, theme="auto", highlight=False) -> str

      Render the report as HTML: a full standalone page with embedded CSS,
      or just the body markup when ``full_document=False``. ``css`` replaces
      the default stylesheet; ``theme`` (``"auto"``, ``"light"``,
      ``"dark"``) chooses its colours.
      ``highlight=True`` colours code blocks with Pygments (``pip install
      reportsmith[highlight]``); see :ref:`highlighting`.

   .. py:method:: save_markdown(path, front_matter=False) -> pathlib.Path

      Write UTF-8 Markdown to *path* and return it. Figures made from plots
      or image bytes are written to a ``<name>_files/`` folder next to it
      and linked relatively.

   .. py:method:: save_html(path, full_document=True, css=None, theme="auto", highlight=False) -> pathlib.Path

      Write UTF-8 HTML to *path* and return it.

   .. py:method:: to_latex(full_document=True, document_class="article", class_options="11pt,a4paper", preamble="", numbered=False, assets_dir=None, highlight=False) -> str

      Render the report as LaTeX source. See :class:`LatexRenderer` for the
      parameters. *assets_dir* is required when the report has figures made
      from plots or image bytes.
      ``highlight=True`` colours code blocks with Pygments (``pip install
      reportsmith[highlight]``); see :ref:`highlighting`.

   .. py:method:: save_latex(path, full_document=True, document_class="article", class_options="11pt,a4paper", preamble="", numbered=False, highlight=False) -> pathlib.Path

      Write UTF-8 LaTeX to *path* and return it. Figures made from plots or
      image bytes are written to a ``<name>_files/`` folder next to it
      (plots as vector PDF).

   .. py:method:: to_pdf(fonts=None, mono_fonts=None, highlight=False) -> bytes

      Render the report as PDF bytes. Requires the optional ``fpdf2``
      dependency (``pip install reportsmith[pdf]``); raises
      :class:`ImportError` with an install hint otherwise. See
      :class:`PdfRenderer` for the font parameters.
      ``highlight=True`` colours code blocks with Pygments (``pip install
      reportsmith[highlight]``); see :ref:`highlighting`.

   .. py:method:: save_pdf(path, fonts=None, mono_fonts=None, highlight=False) -> pathlib.Path

      Write the PDF export to *path* and return it (requires ``fpdf2``).

   .. py:method:: save(path, **options) -> pathlib.Path

      Write the report in the format given by *path*'s extension:
      ``.md`` / ``.markdown`` (:meth:`save_markdown`), ``.html`` / ``.htm``
      (:meth:`save_html`), ``.tex`` (:meth:`save_latex`) or ``.pdf``
      (:meth:`save_pdf`), case-insensitively. *options* are passed to that
      method.

      :raises ValueError: for any other extension.

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

   .. py:method:: definition_list(items) -> Container

      Add a :class:`DefinitionList`.

   .. py:method:: task_list(items) -> Container

      Add a :class:`TaskList`.

   .. py:method:: page_break() -> Container

      Add a :class:`PageBreak`.

   .. py:method:: table(headers, rows, caption="", align=None, label="") -> Container

      Add a :class:`Table`.

   .. py:method:: table_from_records(records, columns=None, **options) -> Container
   .. py:method:: table_from_csv(source, columns=None, **options) -> Container
   .. py:method:: table_from_dataframe(df, columns=None, **options) -> Container

      Add a :class:`Table` built with :meth:`Table.from_records`,
      :meth:`Table.from_csv` or :meth:`Table.from_dataframe`; ``options``
      are passed through.

   .. py:method:: figure(source, caption="", alt="", label="", width=None, dpi=200) -> Container

      Add a :class:`Figure`.

   .. py:method:: image(src, alt="", title="") -> Container

      Add an :class:`Image`.

   .. py:method:: horizontal_rule() -> Container

      Add a :class:`HorizontalRule`.

   .. py:method:: raw(content, format="both") -> Container

      Add a :class:`Raw` passthrough block.

   .. py:method:: toc(title="Contents", depth=3) -> Container

      Add a :class:`TableOfContents` for the whole report.

   .. py:method:: callout(kind="note", content=None, title="") -> Callout

      Add a :class:`Callout`. Returns the *new* callout (not the
      container), usable as a context manager, so more content can be
      added to it.

   .. py:method:: add(element) -> Container

      Append any pre-built :class:`Element`. A :class:`Section` or
      :class:`Callout` is re-levelled to fit here, together with its
      subsections and its default-levelled headings (explicit ``level=``
      values are kept), so a section built on its own gets the right level.

      :raises TypeError: for a :class:`Report` (use :meth:`extend`).

   .. py:method:: extend(source, label_prefix="") -> Container

      Append deep copies of *source*'s content — a :class:`Report`,
      :class:`Section` or :class:`Callout` (its children), or an iterable of
      elements — re-levelled to fit here. The source is not changed and can
      be merged again.

      Tables of contents are skipped when *source* is a container.
      *label_prefix* is prepended to every figure and table label in the
      copies and to the :func:`ref` cross-references that point to them,
      keeping labels unique when merging reports. Plot objects in figures
      are shared, not copied.

      :raises ValueError: for a *label_prefix* that would make an invalid
         label.

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

.. py:class:: DefinitionList(items)

   *items* is a sequence of ``(term, definition)`` pairs or a mapping from
   term to definition; both are ``TextLike``. Markdown: ``- **Term**:
   definition``. HTML: ``<dl>``. LaTeX: ``description``. PDF: bold term
   with the definition indented below.

   :raises ValueError: for an entry that isn't a pair.

.. py:class:: TaskList(items)

   *items* is a sequence of ``(done, text)`` pairs: a ``bool`` and
   ``TextLike``. Markdown: ``- [x]`` / ``- [ ]``. HTML: disabled
   checkboxes in ``<ul class="task-list">``. LaTeX: ``itemize`` with
   ``$\boxtimes$`` / ``$\square$`` (``amssymb``). PDF: drawn checkboxes.

   :raises ValueError: for an entry that isn't a ``(bool, text)`` pair.

.. py:class:: PageBreak()

   PDF: a new page, unless already at the top of one. LaTeX:
   ``\clearpage``. HTML: ``<div class="page-break">``, a break when
   printed. Markdown: an invisible ``<div style="break-after: page">``.

.. py:class:: Table(headers, rows, caption="", align=None, label="")

   :param headers: ``Sequence[TextLike]`` — one entry per column.
   :param rows: ``Sequence[Sequence[TextLike]]``.
   :param str caption: Numbered caption ("Table 1: ..."): an italic line
      after the table (Markdown), ``<caption>`` (HTML), ``\caption``
      (LaTeX). Tables without a caption aren't numbered.
   :param align: One of ``"left"``, ``"center"``, ``"right"`` per column;
      default all-left.
   :param str label: Name for :func:`ref`; requires a caption.
   :raises ValueError: for row-width mismatch, wrong ``align`` length, an
      invalid ``align`` value, or an invalid label / label without caption.

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
   :param str label: As above.
   :raises ValueError: for column names in ``columns``, ``headers`` or
      ``formats`` that don't exist, or a ``headers`` sequence of the wrong
      length.

   .. py:classmethod:: from_records(records, columns=None, *, headers=None, formats=None, align=None, missing="", caption="", label="") -> Table

      Rows from an iterable of mappings. Columns default to the union of
      keys in first-seen order; keys absent from a record are missing.

      :raises TypeError: if a record is not a mapping.

   .. py:classmethod:: from_csv(source, columns=None, *, delimiter=",", encoding="utf-8", parse_numbers=True, headers=None, formats=None, align=None, missing="", caption="", label="") -> Table

      Rows from a CSV file path or open text file; the first row is the
      header. With ``parse_numbers``, a column whose values all parse as
      numbers becomes ``int``/``float`` (integers with leading zeros and
      thousands separators stay text). Empty fields are missing, short rows
      are padded, blank lines are skipped and a leading BOM is dropped.

      :raises ValueError: for empty input or a row with too many fields.

   .. py:classmethod:: from_dataframe(df, columns=None, *, index=False, headers=None, formats=None, align=None, missing="", caption="", label="") -> Table

      Rows from a pandas DataFrame (or any object with ``columns`` and
      ``itertuples()``); pandas is not imported. ``index=True`` prepends the
      index as a column headed by the index name.

      :raises TypeError: if *df* is not DataFrame-like.

.. py:class:: Figure(source, caption="", alt="", label="", width=None, dpi=200)

   An image with an optional numbered caption ("Figure 1: ...").

   :param source: An image file path (``str`` or :class:`pathlib.Path`;
      not a URL), image bytes (PNG, JPEG, GIF or SVG, detected from the
      content), or a plot object with a matplotlib-style ``savefig()``
      method. matplotlib is never imported.
   :param str caption: Numbered caption; figures without one aren't
      numbered.
   :param str alt: Alternative text; defaults to the caption.
   :param str label: Name for :func:`ref`; requires a caption.
   :param width: Fraction (0, 1] of the text width; ``None`` fills the
      width in PDF and scales down to fit elsewhere.
   :param int dpi: Resolution for rendering plots to PNG.
   :raises TypeError: for any other source type.
   :raises ValueError: for unrecognized bytes, a URL, an invalid width, or
      an invalid label / label without caption.

   Paths are referenced as-is in Markdown, HTML and LaTeX and embedded in
   PDF. Plots and bytes are embedded as data URIs in HTML (and in Markdown
   without an assets folder), written to files for Markdown/LaTeX by
   ``save_markdown()`` / ``save_latex()`` (plots as vector PDF for LaTeX;
   SVG can't be used in LaTeX), and embedded in PDF.

   .. py:method:: image_data(plot_format="png") -> tuple[bytes, str]

      The image as ``(bytes, format)``; plots are rendered as
      *plot_format*.

.. py:class:: Image(src, alt="", title="")

   A plain, unnumbered image; *src* may be a remote URL. In LaTeX the
   title (or alt text) becomes an unnumbered ``\caption*``.

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

.. py:class:: Callout(kind="note", content=None, title="", level=1)

   A highlighted box holding block content. Includes the builder API from
   :class:`Container` and supports ``with``.

   :param str kind: ``"note"``, ``"tip"``, ``"important"``, ``"warning"``
      or ``"caution"``.
   :param content: Optional ``TextLike``; becomes the first paragraph.
   :param str title: Shown above the content; defaults to the capitalized
      kind (see ``display_title``).
   :raises ValueError: for any other ``kind``.
   :raises TypeError: from ``section()``, ``toc()``, or ``add()`` with a
      :class:`Section` or :class:`TableOfContents` — callouts never affect
      the document outline. Use ``heading()`` for a heading inside one.

   Markdown: a GitHub alert (``> [!NOTE]``); a custom title becomes a bold
   first line. HTML: ``<div class="callout callout-KIND">`` with a
   ``callout-title`` paragraph, styled per kind by the default stylesheet.
   LaTeX: a breakable ``tcolorbox`` (``rscallout`` environment defined in
   the built-in preamble). PDF: a coloured bar and title that continue
   across page breaks.

.. _highlighting:

Syntax highlighting
===================

Optional, via Pygments (``pip install reportsmith[highlight]``), and off
unless ``highlight=True`` is passed to an HTML, LaTeX or PDF export. Code
blocks whose ``language`` Pygments recognises are coloured; others stay
plain. Markdown output is unchanged.

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

.. py:function:: strike(text) -> Inline

   Markdown ``~~text~~``; HTML ``<del>``; LaTeX ``\sout`` (``ulem``).

.. py:function:: sub(text) -> Inline
.. py:function:: sup(text) -> Inline

   Subscript / superscript. Markdown and HTML ``<sub>`` / ``<sup>``;
   LaTeX ``\textsubscript`` / ``\textsuperscript``.

.. py:function:: ref(label, text="") -> Inline

   A cross-reference to the captioned figure or table with this *label*:
   "Figure 2" / "Table 1", or *text* if given. A link in HTML, LaTeX
   (``\hyperref`` + ``\ref*``) and PDF; plain text in Markdown and in PDF
   table cells. Raises ``ValueError`` at render time for an unknown label.

.. py:function:: footnote(text) -> Inline

   A footnote whose note is *text*, numbered in document order and shown
   as a marker where it is placed. Markdown: ``[^n]`` with definitions at
   the end. HTML: linked superscript markers and a ``<section
   class="footnotes">`` list. LaTeX: ``\footnote`` (headings get a short
   title without it for the TOC and bookmarks). PDF: linked superscript
   markers and a "Notes" section at the end. Footnotes are left out of TOC
   entries and heading anchors.

Renderers
=========

Each renderer exposes ``render(report)``. :meth:`Report.to_markdown`,
:meth:`Report.to_html`, :meth:`Report.to_latex`, and :meth:`Report.to_pdf`
are convenience wrappers around these.

.. py:class:: MarkdownRenderer(assets_dir=None, assets_url=None, front_matter=False)

   GitHub-flavored Markdown. Blocks are separated by blank lines; table
   alignment uses ``:---`` / ``:---:`` / ``---:`` markers. Figures made
   from plots or image bytes are written into *assets_dir* when given and
   referenced as *assets_url* + file name (default: the directory path);
   otherwise they are embedded as data URIs. ``front_matter=True``
   prepends a YAML block with the report's metadata.

   .. py:method:: render(report) -> str

.. py:class:: HtmlRenderer(full_document=True, css=None, theme="auto", highlight=False)

   :param bool full_document: ``True`` produces a complete
      ``<!DOCTYPE html>`` page with ``<title>`` from the report title and
      the stylesheet embedded in ``<style>``; ``False`` produces body
      markup only.
   :param css: ``None`` uses ``reportsmith.renderers.html.DEFAULT_CSS`` — a
      variable-based stylesheet with automatic dark mode
      (``prefers-color-scheme``). Pass any CSS string to replace it, or
      concatenate with ``DEFAULT_CSS`` to extend it.
   :param str theme: ``"auto"``, ``"light"`` or ``"dark"`` — which colours
      the default stylesheet uses (ignored when *css* is given). Every
      theme prints with light colours.
   :param bool highlight: Colour code blocks with Pygments; token colours
      are appended to the stylesheet (also to a custom *css*).
   :raises ValueError: for an unknown *theme*.
   :raises ImportError: for ``highlight=True`` without Pygments.

.. py:function:: reportsmith.renderers.html.theme_css(theme="auto") -> str

   The default stylesheet for a theme; ``DEFAULT_CSS`` is
   ``theme_css("auto")``. All colours are CSS variables: ``--text``,
   ``--muted``, ``--border``, ``--accent``, ``--code-bg``, ``--bg``,
   ``--note``, ``--tip``, ``--important``, ``--warning``, ``--caution``.
   Includes a print stylesheet.

   All text content and attribute values are HTML-escaped; table alignment
   is emitted as inline ``text-align`` styles.

   .. py:method:: render(report) -> str

.. py:class:: LatexRenderer(full_document=True, document_class="article", class_options="11pt,a4paper", preamble="", numbered=False, assets_dir=None, assets_url=None, highlight=False)

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
   :param assets_dir: Where figures made from plots or image bytes are
      written (required if the report has any); referenced as
      *assets_url* + file name, default the directory path.
   :param bool highlight: Colour code blocks with Pygments; its ``\PY``
      macros are added to the preamble of a full document.

   All text is LaTeX-escaped (also available as
   ``reportsmith.renderers.latex.escape_latex``). Tables use ``longtable``
   and ``booktabs``; code blocks use ``fancyvrb``; remote (``http(s)://``)
   images render as links; empty lists and zero-column tables are omitted;
   only :class:`Raw` content with ``format="latex"`` is emitted.

   .. py:method:: render(report) -> str

.. py:class:: PdfRenderer(fonts=None, mono_fonts=None, highlight=False)

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
   :param bool highlight: Colour code blocks with Pygments.

   The document properties hold the report's title, author, description
   (subject), keywords and language, with ``reportsmith <version>`` as the
   creator.

   Sections become PDF outline bookmarks; links are clickable; missing
   images render as a ``[Image: alt]`` placeholder; table cells keep
   bold, italic, strikethrough and links (code and cross-references become
   plain text); :class:`Raw` content is skipped.

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
Malformed definition-list or task-list entry         ``ValueError`` (construction)
``save()`` with an unknown file extension            ``ValueError``
``keywords`` given as a single string                ``TypeError`` (construction)
Unknown HTML ``theme``                               ``ValueError`` (render)
``highlight=True`` without Pygments                  ``ImportError`` (render)
``add()`` given a ``Report``; sections in a callout  ``TypeError``
``TableOfContents`` depth outside 1–5                ``ValueError`` (construction)
Invalid figure source, width or label                ``ValueError`` / ``TypeError``
Label without a caption                              ``ValueError`` (construction)
Duplicate label, or ``ref()`` to an unknown label    ``ValueError`` (render)
Figure from plot/bytes in LaTeX without assets dir   ``ValueError`` (render)
Renderer meets an unknown ``Element`` subclass       ``TypeError`` (render)
PDF export without ``fpdf2`` installed               ``ImportError`` (render)
===================================================  ==============================
