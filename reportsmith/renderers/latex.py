"""LaTeX renderer — produces a standalone compilable document or a body fragment."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
)
from ..inline import Inline, InlineContent

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
\usepackage{fancyvrb}
\usepackage{xcolor}
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
    """

    def __init__(
        self,
        full_document: bool = True,
        document_class: str = "article",
        class_options: str = "11pt,a4paper",
        preamble: str = "",
        numbered: bool = False,
    ):
        self.full_document = full_document
        self.document_class = document_class
        self.class_options = class_options
        self.preamble = preamble
        self.numbered = numbered

    def render(self, report: "Report") -> str:
        body = "".join(self._render_element(child) for child in report.children)
        if not self.full_document:
            return body
        options = f"[{self.class_options}]" if self.class_options else ""
        title = escape_latex(report.title)
        if report.subtitle:
            title += r"\\[0.3em]\large " + escape_latex(report.subtitle)
        parts = [
            f"\\documentclass{options}{{{self.document_class}}}\n",
            DEFAULT_PREAMBLE,
        ]
        if not self.numbered:
            # Unnumbered, but unlike \section* still in bookmarks/ToC.
            parts.append("\\setcounter{secnumdepth}{0}\n")
        parts.append(
            f"\\hypersetup{{pdftitle={{{escape_latex(report.title)}}}, "
            f"pdfauthor={{{escape_latex(report.author)}}}}}\n"
        )
        if self.preamble:
            parts.append(self.preamble.rstrip("\n") + "\n")
        parts.append(
            "\n"
            f"\\title{{{title}}}\n"
            f"\\author{{{escape_latex(report.author)}}}\n"
            f"\\date{{{escape_latex(report.date)}}}\n"
            "\n\\begin{document}\n\\maketitle\n\n"
            f"{body}"
            "\\end{document}\n"
        )
        return "".join(parts)

    # -- elements --------------------------------------------------------

    def _render_element(self, el: Element) -> str:
        if isinstance(el, Section):
            cmd = _SECTION_COMMANDS[el._level]
            out = [f"\\{cmd}{{{self._inline(el.title_parts)}}}\n\n"]
            out.extend(self._render_element(child) for child in el.children)
            return "".join(out)
        if isinstance(el, Heading):
            return f"\\{_SECTION_COMMANDS[el.level]}{{{self._inline(el.parts)}}}\n\n"
        if isinstance(el, Paragraph):
            return f"{self._inline(el.parts)}\n\n"
        if isinstance(el, Quote):
            return f"\\begin{{quote}}\n{self._inline(el.parts)}\n\\end{{quote}}\n\n"
        if isinstance(el, CodeBlock):
            return self._code(el)
        if isinstance(el, ListElement):
            return self._list(el) + "\n" if el.items else ""
        if isinstance(el, Table):
            return self._table(el)
        if isinstance(el, Image):
            return self._image(el)
        if isinstance(el, HorizontalRule):
            return "\\par\\noindent\\rule{\\linewidth}{0.4pt}\\par\n\n"
        if isinstance(el, Raw):
            return el.content + "\n\n" if el.format == "latex" else ""
        raise TypeError(f"Cannot render element of type {type(el).__name__}")

    def _code(self, el: CodeBlock) -> str:
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
        spec = "".join(_ALIGN_SPEC[a] for a in el.align)

        def row(cells: list[list[InlineContent]]) -> str:
            return " & ".join(
                self._cell(cell, _ALIGN_SPEC[a]) for cell, a in zip(cells, el.align)
            ) + " \\\\\n"

        out = [
            f"\\begin{{longtable}}{{{spec}}}\n",
            "\\toprule\n",
            row(el.headers),
            "\\midrule\n\\endhead\n",
        ]
        out.extend(row(r) for r in el.rows)
        out.append("\\bottomrule\n")
        if el.caption:
            out.append(f"\\caption{{{escape_latex(el.caption)}}} \\\\\n")
        out.append("\\end{longtable}\n\n")
        return "".join(out)

    def _cell(self, parts: list[InlineContent], align: str) -> str:
        text = self._inline(parts)
        if "\n" not in text:
            return text
        # Multi-line cells become a nested single-column tabular.
        lines = " \\\\ ".join(text.split("\n"))
        return f"\\begin{{tabular}}[t]{{@{{}}{align}@{{}}}}{lines}\\end{{tabular}}"

    def _image(self, el: Image) -> str:
        caption = el.title or el.alt
        if el.src.startswith(("http://", "https://")):
            # LaTeX can't embed remote images; link to them instead.
            label = escape_latex(caption or el.src)
            return f"\\href{{{_escape_url(el.src)}}}{{[Image: {label}]}}\n\n"
        out = ["\\begin{figure}[htbp]\n\\centering\n", f"\\includegraphics{{{el.src}}}\n"]
        if caption:
            out.append(f"\\caption{{{escape_latex(caption)}}}\n")
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
        return text
