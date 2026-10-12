"""reportsmith — a small, dependency-free library for building reports.

Build a report programmatically from typed elements (headings, paragraphs,
tables, lists, code blocks, images, ...) and export it to Markdown, a
standalone styled HTML document, LaTeX, or PDF.

Quick start::

    from reportsmith import Report, bold, link

    report = Report("Q3 Sales Report", author="Jane Doe")
    with report.section("Overview") as s:
        s.paragraph(["Revenue was ", bold("up 12%"), " quarter over quarter."])
        s.table(["Region", "Revenue"], [["EMEA", "$1.2M"], ["APAC", "$0.9M"]])

    report.save_markdown("report.md")
    report.save_html("report.html")
"""

from .inline import Inline, bold, code, italic, link
from .elements import (
    CodeBlock,
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
from .report import Report
from .renderers.markdown import MarkdownRenderer
from .renderers.html import HtmlRenderer
from .renderers.pdf import PdfRenderer
from .renderers.latex import LatexRenderer

__version__ = "0.2.0"

__all__ = [
    "Report",
    "Section",
    "Heading",
    "Paragraph",
    "Table",
    "ListElement",
    "CodeBlock",
    "Image",
    "Quote",
    "HorizontalRule",
    "Raw",
    "Inline",
    "bold",
    "italic",
    "code",
    "link",
    "MarkdownRenderer",
    "HtmlRenderer",
    "PdfRenderer",
    "LatexRenderer",
]
