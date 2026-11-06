"""reportsmith — a small, dependency-free library for building reports.

Build a report programmatically from typed elements (headings, paragraphs,
tables, lists, code blocks, images, ...) and export it to Markdown, a
standalone styled HTML document, LaTeX, PDF, or Word (.docx).

Quick start::

    from reportsmith import Report, bold, link

    report = Report("Q3 Sales Report", author="Jane Doe")
    with report.section("Overview") as s:
        s.paragraph(["Revenue was ", bold("up 12%"), " quarter over quarter."])
        s.table(["Region", "Revenue"], [["EMEA", "$1.2M"], ["APAC", "$0.9M"]])

    report.save_markdown("report.md")
    report.save_html("report.html")
"""

from .inline import Inline, bold, code, footnote, italic, link, math, ref, strike, sub, sup
from .elements import (
    Callout,
    Cell,
    CodeBlock,
    Equation,
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
from .cover import Cover
from .report import Report
from .renderers.markdown import MarkdownRenderer
from .renderers.html import HtmlRenderer
from .renderers.pdf import PdfRenderer
from .renderers.latex import LatexRenderer
from .renderers.docx import DocxRenderer

__version__ = "0.8"

__all__ = [
    "Report",
    "Cover",
    "Section",
    "Heading",
    "Paragraph",
    "Table",
    "Cell",
    "TableOfContents",
    "ListElement",
    "DefinitionList",
    "TaskList",
    "PageBreak",
    "CodeBlock",
    "Image",
    "Figure",
    "Equation",
    "Quote",
    "HorizontalRule",
    "Raw",
    "Callout",
    "Inline",
    "bold",
    "italic",
    "code",
    "link",
    "strike",
    "sub",
    "sup",
    "math",
    "footnote",
    "ref",
    "MarkdownRenderer",
    "HtmlRenderer",
    "PdfRenderer",
    "LatexRenderer",
    "DocxRenderer",
]
