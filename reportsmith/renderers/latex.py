"""LaTeX renderer — produces a standalone compilable document or a body fragment."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

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
from ..assets import Assets, path_reference
from ..colors import to_hex
from ..highlight import latex_block, latex_style_defs, require_pygments
from ..inline import Inline, InlineContent
from ..numbering import LATEX_PREFIXES, KIND_NAMES, Numbering
from ..page import segments

if TYPE_CHECKING:
    from ..report import Report

# Works with pdfLaTeX, XeLaTeX and LuaLaTeX.
DEFAULT_PREAMBLE = r"""\usepackage{iftex}
\ifPDFTeX
  \usepackage[T1]{fontenc}
  \usepackage[utf8]{inputenc}
  \usepackage{lmodern}
\else
  \usepackage{fontspec}
\fi
\usepackage[margin=2.5cm]{geometry}
\usepackage{parskip}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}
\usepackage{colortbl}
\usepackage{caption}
\usepackage{amssymb}
\usepackage{fancyvrb}
\usepackage{xcolor}
\usepackage[normalem]{ulem}
\usepackage{tcolorbox}
\tcbuselibrary{breakable}
\definecolor{rsnote}{HTML}{1D4ED8}
\definecolor{rstip}{HTML}{15803D}
\definecolor{rsimportant}{HTML}{7C3AED}
\definecolor{rswarning}{HTML}{B45309}
\definecolor{rscaution}{HTML}{B91C1C}
% Callout box: #1 = colour, #2 = title.
\newtcolorbox{rscallout}[2]{breakable, sharp corners, boxrule=0pt, leftrule=3pt,
  colframe=#1, colback=#1!6!white, colbacktitle=#1!6!white, coltitle=#1,
  fonttitle=\bfseries, title={#2}}
\usepackage{hyperref}
\hypersetup{colorlinks=true, linkcolor=blue!60!black, urlcolor=blue!60!black}
% Scale images down to the line width, but never up.
\makeatletter
\def\maxwidth{\ifdim\Gin@nat@width>\linewidth\linewidth\else\Gin@nat@width\fi}
\makeatother
\setkeys{Gin}{width=\maxwidth,keepaspectratio}
"""

_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    # Brackets would otherwise be read as optional arguments after \item or \\.
    "[": "{[}",
    "]": "{]}",
}
_ESCAPE_TABLE = str.maketrans(_ESCAPES)
_VERBATIM_ESCAPE_TABLE = str.maketrans({"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}"})

# Section depth (2 = top-level section, since the report title is level 1).
_SECTION_COMMANDS = {
    1: "section",
    2: "section",
    3: "subsection",
    4: "subsubsection",
    5: "paragraph",
    6: "subparagraph",
}
_ALIGN_SPEC = {"left": "l", "center": "c", "right": "r"}
# Paragraph-column alignment for tables with widths (array package).
_RAGGED = {"left": r"\raggedright", "center": r"\centering", "right": r"\raggedleft"}
# Shading for every other body row of a striped table (colortbl).
_STRIPE = r"\rowcolor[HTML]{F5F6F8}"
# Frame and size of code blocks, shared with highlighted (Pygments) blocks.
_VERBATIM_OPTIONS = r"frame=single, framesep=2mm, fontsize=\small"
# Task list checkboxes (amssymb), keyed by "done".
_TASK_MARKS = {True: r"$\boxtimes$", False: r"$\square$"}


def escape_latex(text: str) -> str:
    """Escape LaTeX special characters in plain text."""
    return text.translate(_ESCAPE_TABLE)


def _escape_url(url: str) -> str:
    # Characters that can't survive inside \href are percent-encoded first,
    # then the remaining specials are backslash-escaped.
    url = url.replace("\\", "%5C").replace("{", "%7B").replace("}", "%7D")
    return url.replace("%", r"\%").replace("#", r"\#")


class LatexRenderer:
    """Renders a Report to LaTeX.

    With ``full_document=True`` output is a complete document (preamble,
    ``\\maketitle``, body) ready for ``pdflatex``/``xelatex``/``lualatex``;
    otherwise only the body content is produced, for ``\\input`` into an
    existing document. ``preamble`` is appended after the default preamble,
    and ``numbered=True`` turns on section numbering.

    Figures from plots or bytes must be written to files for
    ``\\includegraphics``: pass ``assets_dir`` (referenced as ``assets_url``
    + file name, default the directory path). ``Report.save_latex()`` does
    this automatically.
    """

    def __init__(
        self,
        full_document: bool = True,
        document_class: str = "article",
        class_options: str = "11pt,a4paper",
        preamble: str = "",
        numbered: bool = False,
        assets_dir: Optional[Union[str, Path]] = None,
        assets_url: Optional[str] = None,
        highlight: bool = False,
    ):
        self.assets_dir = assets_dir
        self.assets_url = assets_url
        self.highlight = highlight
        if highlight:
            require_pygments()
        self.full_document = full_document
        self.document_class = document_class
        self.class_options = class_options
        self.preamble = preamble
        self.numbered = numbered

    def render(self, report: "Report") -> str:
        # numbered=True keeps working: LaTeX's usual three levels.
        self._depth = report.section_numbers or (3 if self.numbered else 0)
        self._numbering = Numbering(report, section_depth=self._depth)
        self._in_callout = 0
        self._assets = Assets(self.assets_dir, self.assets_url) if self.assets_dir is not None else None
        body = "".join(self._render_element(child) for child in report.children)
        if not self.full_document:
            return body
        title_page = self._cover(report) if report.cover is not None else "\\maketitle\n"
        options = f"[{self.class_options}]" if self.class_options else ""
        title = escape_latex(report.title)
        if report.subtitle:
            title += r"\\[0.3em]\large " + escape_latex(report.subtitle)
        parts = [
            f"\\documentclass{options}{{{self.document_class}}}\n",
            DEFAULT_PREAMBLE,
        ]
        # Depth 0 is unnumbered, but unlike \section* still in bookmarks/ToC.
        parts.append(f"\\setcounter{{secnumdepth}}{{{self._depth}}}\n")
        fields = [
            ("pdftitle", report.title),
            ("pdfauthor", report.author),
            ("pdfsubject", report.description),
            ("pdfkeywords", ", ".join(report.keywords)),
            ("pdflang", report.language),
        ]
        setup = ", ".join(f"{key}={{{escape_latex(value)}}}" for key, value in fields if value or key == "pdfauthor")
        parts.append(f"\\hypersetup{{{setup}}}\n")
        parts.append(self._page_style(report))
        if self.highlight:
            parts.append(latex_style_defs())
        if self.preamble:
            parts.append(self.preamble.rstrip("\n") + "\n")
        parts.append(
            "\n"
            f"\\title{{{title}}}\n"
            f"\\author{{{escape_latex(report.author)}}}\n"
            f"\\date{{{escape_latex(report.date)}}}\n"
            "\n\\begin{document}\n"
            f"{title_page}\n"
            f"{body}"
            "\\end{document}\n"
        )
        return "".join(parts)

    # -- elements --------------------------------------------------------

    def _render_element(self, el: Element) -> str:
        if isinstance(el, Section):
            out = [self._heading(_SECTION_COMMANDS[el._level], el.title_parts, el.label)]
            out.extend(self._render_element(child) for child in el.children)
            return "".join(out)
        if isinstance(el, Heading):
            return self._heading(_SECTION_COMMANDS[el.level], el.parts)
        if isinstance(el, Paragraph):
            return f"{self._inline(el.parts)}\n\n"
        if isinstance(el, Quote):
            return f"\\begin{{quote}}\n{self._inline(el.parts)}\n\\end{{quote}}\n\n"
        if isinstance(el, CodeBlock):
            return self._code(el)
        if isinstance(el, ListElement):
            return self._list(el) + "\n" if el.items else ""
        if isinstance(el, DefinitionList):
            if not el.items:
                return ""
            # Braces keep a "]" in the term from ending the optional argument.
            items = "".join(
                f"\\item[{{{self._inline(term)}}}] {self._inline(definition)}\n"
                for term, definition in el.items
            )
            return f"\\begin{{description}}\n{items}\\end{{description}}\n\n"
        if isinstance(el, TaskList):
            if not el.items:
                return ""
            items = "".join(
                f"\\item[{_TASK_MARKS[done]}] {self._inline(text)}\n"
                for done, text in el.items
            )
            return f"\\begin{{itemize}}\n{items}\\end{{itemize}}\n\n"
        if isinstance(el, PageBreak):
            # \clearpage also places any pending figures first.
            return "\\clearpage\n\n"
        if isinstance(el, Table):
            return self._table(el)
        if isinstance(el, Figure):
            return self._figure(el)
        if isinstance(el, Image):
            return self._image(el)
        if isinstance(el, HorizontalRule):
            return "\\par\\noindent\\rule{\\linewidth}{0.4pt}\\par\n\n"
        if isinstance(el, Raw):
            return el.content + "\n\n" if el.format == "latex" else ""
        if isinstance(el, TableOfContents):
            # Grouped so the renamed heading stays local to this TOC. Our
            # depth 1 (top-level sections) is LaTeX's tocdepth 1 (\section).
            return (
                f"{{\\renewcommand{{\\contentsname}}{{{escape_latex(el.title)}}}"
                f"\\setcounter{{tocdepth}}{{{el.depth}}}\\tableofcontents}}\n\n"
            )
        if isinstance(el, Callout):
            self._in_callout += 1
            body = "".join(self._render_element(child) for child in el.children)
            self._in_callout -= 1
            return (
                f"\\begin{{rscallout}}{{rs{el.kind}}}{{{escape_latex(el.display_title)}}}\n"
                f"{body.rstrip(chr(10))}\n"
                "\\end{rscallout}\n\n"
            )
        raise TypeError(f"Cannot render element of type {type(el).__name__}")

    def _cover(self, report: "Report") -> str:
        """A ``titlepage`` for the cover. It has no header or footer, and
        the page after it is numbered 2, as in the PDF and HTML output."""
        cover = report.cover
        assert cover is not None
        out = ["\\begin{titlepage}\n\\centering\n"]
        if cover.logo is not None:
            path = self._image_path(cover.logo, "logo")
            out.append(f"\\includegraphics[width={cover.logo.width:g}\\linewidth]{{{path}}}\\par\n")
        if cover.organization:
            out.append(f"\\vspace{{1em}}{{\\large\\bfseries {escape_latex(cover.organization)}\\par}}\n")
        out.append("\\vspace*{\\fill}\n")
        out.append(f"{{\\Huge\\bfseries {escape_latex(report.title)}\\par}}\n")
        if report.subtitle:
            out.append(f"\\vspace{{1em}}{{\\Large\\color{{black!60}}{escape_latex(report.subtitle)}\\par}}\n")
        meta = [escape_latex(x) for x in (report.author, report.date) if x]
        if meta:
            out.append("\\vspace{2em}{\\color{rsnote}\\rule{3cm}{1.5pt}}\\par\\vspace{2em}\n")
            out.append("{\\large " + "\\\\[0.5em]\n".join(meta) + "\\par}\n")
        out.append("\\vspace*{\\fill}\n")
        if cover.note:
            out.append(f"{{\\small\\color{{black!60}}{escape_latex(cover.note)}\\par}}\n")
        out.append("\\end{titlepage}\n\\setcounter{page}{2}\n")
        return "".join(out)

    def _image_path(self, el: Figure, what: str = "figure") -> str:
        """The ``\\includegraphics`` path of a figure, writing it to the
        assets folder first when it isn't a file."""
        if el.kind == "path":
            return path_reference(el.source)
        if el.format == "svg":
            raise ValueError(f"LaTeX can't include an SVG {what}; pass PNG/JPEG data or a plot")
        if self._assets is None:
            raise ValueError(
                f"A {what} from a plot or image bytes needs a file for LaTeX: use "
                "save_latex(), or pass assets_dir to to_latex()"
            )
        # Plots are saved as PDF, so they stay vector graphics.
        return self._assets.write(*el.image_data("pdf"))

    def _page_style(self, report: "Report") -> str:
        """fancyhdr setup for the running header and footer. The first page
        (``plain``, used by ``\\maketitle``) gets the footer but no header."""

        def fill(text: str) -> str:
            pieces = []
            for kind, value in segments(text, report):
                if kind == "page":
                    pieces.append("\\thepage")
                elif kind == "pages":
                    pieces.append("\\pageref*{LastPage}")
                else:
                    pieces.append(escape_latex(value))
            return "".join(pieces)

        def fields(band, where: str) -> str:
            if band is None:
                return ""
            return "".join(
                f"\\fancy{where}[{side}]{{\\small\\color{{black!60}}{fill(text)}}}"
                for text, side in zip(band, "LCR")
                if text
            )

        head, foot = fields(report.header, "head"), fields(report.footer, "foot")
        return (
            "\\usepackage{fancyhdr}\n"
            "\\usepackage{lastpage}\n"
            "\\setlength{\\headheight}{14pt}\n"
            "\\renewcommand{\\headrulewidth}{0pt}\n"
            f"\\fancyhf{{}}{head}{foot}\n"
            "\\pagestyle{fancy}\n"
            f"\\fancypagestyle{{plain}}{{\\fancyhf{{}}\\renewcommand{{\\headrulewidth}}{{0pt}}{foot}}}\n"
        )

    def _heading(self, cmd: str, parts: list[InlineContent], label: str = "") -> str:
        title = self._inline(parts)
        if self._in_callout:
            # Headings in callouts are left out of numbering and the TOC, as
            # in the other formats.
            return f"\\{cmd}*{{{title}}}\n\n"
        target = f"\\label{{sec:{label}}}" if label else ""
        if not any(isinstance(p, Inline) and p.style == "footnote" for p in parts):
            return f"\\{cmd}{{{title}}}{target}\n\n"
        # A footnote can't go into the TOC or PDF bookmarks, so give the
        # heading a short title without it.
        short = self._inline(
            [p for p in parts if not (isinstance(p, Inline) and p.style == "footnote")]
        )
        return f"\\{cmd}[{{{short}}}]{{{title}}}{target}\n\n"

    def _code(self, el: CodeBlock) -> str:
        if self.highlight:
            block = latex_block(el.source, el.language, _VERBATIM_OPTIONS)
            if block is not None:
                return block + "\n"
        return self._plain_code(el)

    def _plain_code(self, el: CodeBlock) -> str:
        # With commandchars, only \ { } need escaping, and an escaped
        # "\end{Verbatim}" in the source can no longer close the environment.
        source = el.source.translate(_VERBATIM_ESCAPE_TABLE)
        return (
            "\\begin{Verbatim}[commandchars=\\\\\\{\\}, frame=single, "
            "framesep=2mm, fontsize=\\small]\n"
            f"{source}\n"
            "\\end{Verbatim}\n\n"
        )

    def _list(self, el: ListElement) -> str:
        env = "enumerate" if el.ordered else "itemize"
        out = [f"\\begin{{{env}}}\n"]
        has_item = False
        for item in el.items:
            if isinstance(item, ListElement):
                if not item.items:
                    continue
                # A nested list belongs to the preceding item; open an empty
                # one if there is none, mirroring the HTML renderer.
                if not has_item:
                    out.append("\\item\n")
                    has_item = True
                out.append(self._list(item))
            else:
                # "{}" stops a leading "[" from being read as an item label.
                out.append(f"\\item{{}} {self._inline(item)}\n")
                has_item = True
        out.append(f"\\end{{{env}}}\n")
        return "".join(out)

    def _table(self, el: Table) -> str:
        if not el.headers:
            return ""
        if el.widths:
            # Fixed-width columns that keep each column's alignment.
            spec = "".join(
                f">{{{_RAGGED[a]}\\arraybackslash}}p{{\\dimexpr {w:.4f}\\linewidth-2\\tabcolsep\\relax}}"
                for a, w in zip(el.align, el.widths)
            )
        else:
            spec = "".join(_ALIGN_SPEC[a] for a in el.align)

        def row(cells: list[list[InlineContent]], styles: list[CellStyle], prefix: str = "") -> str:
            return prefix + " & ".join(
                self._styled(self._cell(cell, _ALIGN_SPEC[a]), style)
                for cell, a, style in zip(cells, el.align, styles)
            ) + " \\\\\n"

        out = [
            f"\\begin{{longtable}}{{{spec}}}\n",
            "\\toprule\n",
            row(el.headers, [CellStyle()] * len(el.headers)),
            "\\midrule\n\\endhead\n",
        ]
        for i, cells in enumerate(el.rows):
            stripe = _STRIPE if el.striped and i % 2 == 1 else ""
            out.append(row(cells, [el.style_at(i, j) for j in range(len(cells))], stripe))
        if el.footer is not None:
            footer_styles = [
                CellStyle(s.color, s.background, True)
                for s in (el.footer_styles.get(j, CellStyle()) for j in range(len(el.footer)))
            ]
            out.append("\\midrule\n")
            out.append(row(el.footer, footer_styles))
        out.append("\\bottomrule\n")
        if el.caption:
            label = f"\\label{{tab:{el.label}}}" if el.label else ""
            out.append(f"\\caption{{{escape_latex(el.caption)}}}{label} \\\\\n")
        out.append("\\end{longtable}\n\n")
        return "".join(out)

    @staticmethod
    def _styled(text: str, style: CellStyle) -> str:
        if style.bold and text:
            text = f"\\textbf{{{text}}}"
        if style.color:
            text = f"\\textcolor[HTML]{{{to_hex(style.color)[1:].upper()}}}{{{text}}}"
        if style.background:
            text = f"\\cellcolor[HTML]{{{to_hex(style.background, True)[1:].upper()}}}{text}"
        return text

    def _cell(self, parts: list[InlineContent], align: str) -> str:
        text = self._inline(parts)
        if "\n" not in text:
            return text
        # Multi-line cells become a nested single-column tabular.
        lines = " \\\\ ".join(text.split("\n"))
        return f"\\begin{{tabular}}[t]{{@{{}}{align}@{{}}}}{lines}\\end{{tabular}}"

    def _figure(self, el: Figure) -> str:
        path = self._image_path(el)
        width = f"[width={el.width:g}\\linewidth]" if el.width else ""
        out = ["\\begin{figure}[htbp]\n\\centering\n", f"\\includegraphics{width}{{{path}}}\n"]
        if el.caption:
            label = f"\\label{{fig:{el.label}}}" if el.label else ""
            out.append(f"\\caption{{{escape_latex(el.caption)}}}{label}\n")
        out.append("\\end{figure}\n\n")
        return "".join(out)

    def _image(self, el: Image) -> str:
        caption = el.title or el.alt
        if el.src.startswith(("http://", "https://")):
            # LaTeX can't embed remote images; link to them instead.
            label = escape_latex(caption or el.src)
            return f"\\href{{{_escape_url(el.src)}}}{{[Image: {label}]}}\n\n"
        out = ["\\begin{figure}[htbp]\n\\centering\n", f"\\includegraphics{{{el.src}}}\n"]
        if caption:
            out.append(f"\\caption*{{{escape_latex(caption)}}}\n")
        out.append("\\end{figure}\n\n")
        return "".join(out)

    # -- inline ----------------------------------------------------------

    def _inline(self, parts: list[InlineContent]) -> str:
        out = []
        for part in parts:
            if isinstance(part, Inline):
                out.append(self._span(part))
            else:
                out.append(escape_latex(str(part)))
        return "".join(out)

    def _span(self, span: Inline) -> str:
        text = escape_latex(span.text)
        if span.style == "bold":
            return f"\\textbf{{{text}}}"
        if span.style == "italic":
            return f"\\emph{{{text}}}"
        if span.style == "code":
            return f"\\texttt{{{text}}}"
        if span.style == "link":
            return f"\\href{{{_escape_url(span.href)}}}{{{text}}}"
        if span.style == "strike":
            return f"\\sout{{{text}}}"
        if span.style == "sub":
            return f"\\textsubscript{{{text}}}"
        if span.style == "sup":
            return f"\\textsuperscript{{{text}}}"
        if span.style == "ref":
            kind, _ = self._numbering.resolve(span.href)
            target = f"{LATEX_PREFIXES[kind]}:{span.href}"
            # \ref* is the number without its own link; the whole phrase links.
            if span.text:
                shown = escape_latex(span.text)
            elif kind == "section" and not self._numbering.resolve(span.href)[1]:
                # Unnumbered sections are referred to by title.
                shown = escape_latex(self._numbering.ref_text(span.href))
            else:
                shown = f"{KIND_NAMES[kind]}~\\ref*{{{target}}}"
            return f"\\hyperref[{target}]{{{shown}}}"
        if span.style == "footnote":
            return f"\\footnote{{{text}}}"
        return text
