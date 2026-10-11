"""PDF renderer — renders a Report to PDF via the optional fpdf2 dependency.

fpdf2 is imported lazily inside :meth:`PdfRenderer.render`, so importing this
module (and the reportsmith package) works without it; only actually rendering
a PDF requires ``pip install reportsmith[pdf]``.

Unicode: the PDF core fonts (Helvetica/Courier) only cover Latin-1, so the
renderer probes for a system TrueType family (Arial/Segoe UI on Windows,
DejaVu on Linux, Arial on macOS) and embeds it when found. Without one,
unsupported characters degrade to ``?`` instead of crashing. Pass explicit
font paths to control the typeface.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Optional, Sequence

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

PAGE_MARGIN = 18  # mm
BODY_SIZE = 11
_HEADING_SIZES = {1: 20, 2: 16, 3: 13.5, 4: 12, 5: 11, 6: 10.5}

_TEXT = (31, 41, 55)
_MUTED = (107, 114, 128)
_ACCENT = (29, 78, 216)
_BORDER = (183, 189, 196)
_CODE_BG = (243, 244, 246)

_WIN_FONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
_MAC_FONTS = "/System/Library/Fonts/Supplemental"
_DEJAVU = "/usr/share/fonts/truetype/dejavu"

# (regular, bold, italic, bold-italic) quadruples, first complete one wins.
_BODY_FONT_CANDIDATES = [
    tuple(os.path.join(_WIN_FONTS, f) for f in ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf")),
    tuple(os.path.join(_WIN_FONTS, f) for f in ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf")),
    tuple(os.path.join(_DEJAVU, f) for f in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique.ttf")),
    tuple(os.path.join(_MAC_FONTS, f) for f in ("Arial.ttf", "Arial Bold.ttf", "Arial Italic.ttf", "Arial Bold Italic.ttf")),
]
_MONO_FONT_CANDIDATES = [
    tuple(os.path.join(_WIN_FONTS, f) for f in ("consola.ttf", "consolab.ttf", "consolai.ttf", "consolaz.ttf")),
    tuple(os.path.join(_DEJAVU, f) for f in ("DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf", "DejaVuSansMono-Oblique.ttf", "DejaVuSansMono-BoldOblique.ttf")),
    tuple(os.path.join(_MAC_FONTS, f) for f in ("Courier New.ttf", "Courier New Bold.ttf", "Courier New Italic.ttf", "Courier New Bold Italic.ttf")),
]


def _find_fonts(candidates, override) -> Optional[tuple]:
    if override is not None:
        return tuple(override) if override else None
    for quad in candidates:
        if all(os.path.isfile(p) for p in quad):
            return quad
    return None


class PdfRenderer:
    """Renders a Report to a PDF document (A4).

    :param fonts: optional (regular, bold, italic, bold-italic) TTF paths for
        body text; ``None`` auto-detects a system family, ``()`` forces the
        Latin-1 core Helvetica.
    :param mono_fonts: same, for code; falls back to core Courier.
    """

    def __init__(
        self,
        fonts: Optional[Sequence[str]] = None,
        mono_fonts: Optional[Sequence[str]] = None,
    ):
        self._fonts = fonts
        self._mono_fonts = mono_fonts
        self.unicode = False
        self.body_family = "helvetica"
        self.mono_family = "courier"

    def render(self, report: "Report") -> bytes:
        try:
            from fpdf import FPDF
        except ImportError:
            raise ImportError(
                "PDF export requires the optional dependency fpdf2. "
                "Install it with: pip install reportsmith[pdf]"
            ) from None

        pdf = FPDF(format="A4")
        pdf.set_margins(PAGE_MARGIN, PAGE_MARGIN)
        pdf.set_auto_page_break(True, margin=PAGE_MARGIN)
        self._setup_fonts(pdf)
        pdf.add_page()
        pdf.set_title(report.title)
        if report.author:
            pdf.set_author(report.author)
        self._title_block(pdf, report)
        for child in report.children:
            self._element(pdf, child)
        return bytes(pdf.output())

    # -- setup -----------------------------------------------------------

    def _setup_fonts(self, pdf) -> None:
        # fontTools logs a benign warning per unsupported table when
        # subsetting system fonts (e.g. Arial's MERG table); silence it.
        logging.getLogger("fontTools.subset").setLevel(logging.ERROR)
        body = _find_fonts(_BODY_FONT_CANDIDATES, self._fonts)
        if body:
            for style, path in zip(("", "B", "I", "BI"), body):
                pdf.add_font("rsbody", style, path)
            self.body_family, self.unicode = "rsbody", True
        mono = _find_fonts(_MONO_FONT_CANDIDATES, self._mono_fonts)
        if mono:
            for style, path in zip(("", "B", "I", "BI"), mono):
                pdf.add_font("rsmono", style, path)
            self.mono_family = "rsmono"

    def _t(self, text: str) -> str:
        # Core fonts are Latin-1 only; degrade unsupported chars to '?'.
        if self.unicode:
            return text
        return text.encode("latin-1", "replace").decode("latin-1")

    def _title_block(self, pdf, report: "Report") -> None:
        pdf.set_text_color(*_TEXT)
        pdf.set_font(self.body_family, "B", 22)
        pdf.multi_cell(0, 10, self._t(report.title), new_x="LMARGIN", new_y="NEXT")
        if report.subtitle:
            pdf.set_font(self.body_family, "I", 12)
            pdf.set_text_color(*_MUTED)
            pdf.multi_cell(0, 7, self._t(report.subtitle), new_x="LMARGIN", new_y="NEXT")
        meta = " · ".join(x for x in (report.author, report.date) if x)
        if meta:
            pdf.set_font(self.body_family, "", 10)
            pdf.set_text_color(*_MUTED)
            pdf.multi_cell(0, 6, self._t(meta), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        pdf.set_draw_color(*_BORDER)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(6)

    # -- elements --------------------------------------------------------

    def _element(self, pdf, el: Element) -> None:
        if isinstance(el, Section):
            self._keep_with_next(pdf)
            # PDF outline (bookmarks): top-level sections at outline level 0.
            pdf.start_section(self._t(self._plain(el.title_parts)), level=el._level - 2)
            self._heading(pdf, el.title_parts, el._level)
            for child in el.children:
                self._element(pdf, child)
        elif isinstance(el, Heading):
            self._keep_with_next(pdf)
            self._heading(pdf, el.parts, el.level)
        elif isinstance(el, Paragraph):
            self._write_parts(pdf, el.parts, BODY_SIZE)
            pdf.ln(BODY_SIZE * 0.55)
            pdf.ln(1.5)
        elif isinstance(el, Quote):
            self._quote(pdf, el)
        elif isinstance(el, CodeBlock):
            pdf.set_font(self.mono_family, "", 9.5)
            pdf.set_text_color(*_TEXT)
            pdf.set_fill_color(*_CODE_BG)
            pdf.multi_cell(0, 5, self._t(el.source), fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2.5)
        elif isinstance(el, ListElement):
            root = pdf.l_margin
            self._list_items(pdf, el, root, 0)
            pdf.set_left_margin(root)
            pdf.ln(1.5)
        elif isinstance(el, Table):
            self._table(pdf, el)
        elif isinstance(el, Image):
            self._image(pdf, el)
        elif isinstance(el, HorizontalRule):
            pdf.ln(2)
            pdf.set_draw_color(*_BORDER)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(4)
        elif isinstance(el, Raw):
            pass  # format-specific passthrough has no meaning in PDF
        else:
            raise TypeError(f"Cannot render element of type {type(el).__name__}")

    def _keep_with_next(self, pdf) -> None:
        # Avoid a heading orphaned at the bottom of a page.
        if pdf.get_y() > pdf.h - PAGE_MARGIN - 30:
            pdf.add_page()

    def _heading(self, pdf, parts: list[InlineContent], level: int) -> None:
        size = _HEADING_SIZES[level]
        pdf.ln(2.5)
        self._write_parts(pdf, parts, size, base_style="B")
        pdf.ln(size * 0.55)
        pdf.ln(2)

    def _quote(self, pdf, el: Quote) -> None:
        root = pdf.l_margin
        pdf.set_left_margin(root + 6)
        pdf.set_x(root + 6)
        page_before, y_before = pdf.page_no(), pdf.get_y()
        self._write_parts(pdf, el.parts, BODY_SIZE, base_style="I", color=_MUTED)
        pdf.ln(BODY_SIZE * 0.55)
        if pdf.page_no() == page_before:
            pdf.set_draw_color(*_BORDER)
            pdf.set_line_width(0.8)
            pdf.line(root + 2, y_before, root + 2, pdf.get_y())
            pdf.set_line_width(0.2)
        pdf.set_left_margin(root)
        pdf.ln(1.5)

    def _list_items(self, pdf, el: ListElement, root: float, depth: int) -> None:
        counter = 0
        for item in el.items:
            if isinstance(item, ListElement):
                self._list_items(pdf, item, root, depth + 1)
            else:
                counter += 1
                bullet = "\u2022" if self.unicode else "-"
                marker = f"{counter}." if el.ordered else bullet
                pdf.set_left_margin(root + 6 * depth)
                pdf.set_x(root + 6 * depth)
                pdf.set_font(self.body_family, "", BODY_SIZE)
                pdf.set_text_color(*_TEXT)
                pdf.write(BODY_SIZE * 0.55, f"{marker} ")
                self._write_parts(pdf, item, BODY_SIZE)
                pdf.ln(BODY_SIZE * 0.55)

    def _table(self, pdf, el: Table) -> None:
        pdf.set_font(self.body_family, "", 10)
        pdf.set_text_color(*_TEXT)
        pdf.set_draw_color(*_BORDER)
        aligns = tuple(a.upper() for a in el.align)
        with pdf.table(text_align=aligns, line_height=6) as table:
            header = table.row()
            for parts in el.headers:
                header.cell(self._t(self._plain(parts)))
            for row_parts in el.rows:
                row = table.row()
                for parts in row_parts:
                    row.cell(self._t(self._plain(parts)))
        if el.caption:
            pdf.ln(1)
            pdf.set_font(self.body_family, "I", 9)
            pdf.set_text_color(*_MUTED)
            pdf.multi_cell(0, 5, self._t(el.caption), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2.5)

    def _image(self, pdf, el: Image) -> None:
        try:
            pdf.image(el.src, w=pdf.epw)
        except Exception:
            # Missing/remote/unreadable file: render a placeholder, keep going.
            pdf.set_font(self.body_family, "I", 10)
            pdf.set_text_color(*_MUTED)
            pdf.multi_cell(0, 6, self._t(f"[Image: {el.alt or el.src}]"), new_x="LMARGIN", new_y="NEXT")
        else:
            if el.title:
                pdf.set_font(self.body_family, "I", 9)
                pdf.set_text_color(*_MUTED)
                pdf.multi_cell(0, 5, self._t(el.title), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    # -- inline ----------------------------------------------------------

    def _write_parts(
        self,
        pdf,
        parts: list[InlineContent],
        size: float,
        base_style: str = "",
        color: tuple = _TEXT,
    ) -> None:
        h = size * 0.55
        pdf.set_text_color(*color)
        for part in parts:
            if isinstance(part, Inline):
                text = self._t(part.text)
                if part.style == "bold":
                    pdf.set_font(self.body_family, self._merge(base_style, "B"), size)
                    pdf.write(h, text)
                elif part.style == "italic":
                    pdf.set_font(self.body_family, self._merge(base_style, "I"), size)
                    pdf.write(h, text)
                elif part.style == "code":
                    pdf.set_font(self.mono_family, base_style, size * 0.92)
                    pdf.write(h, text)
                elif part.style == "link":
                    pdf.set_font(self.body_family, self._merge(base_style, "U"), size)
                    pdf.set_text_color(*_ACCENT)
                    pdf.write(h, text, link=part.href)
                    pdf.set_text_color(*color)
                else:
                    pdf.set_font(self.body_family, base_style, size)
                    pdf.write(h, text)
            else:
                pdf.set_font(self.body_family, base_style, size)
                pdf.write(h, self._t(str(part)))

    @staticmethod
    def _merge(base: str, extra: str) -> str:
        return "".join(s for s in ("B", "I", "U") if s in base or s in extra)

    @staticmethod
    def _plain(parts: list[InlineContent]) -> str:
        return "".join(p.text if isinstance(p, Inline) else str(p) for p in parts)
