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

import io
import logging
import re
import os
from typing import TYPE_CHECKING, Optional, Sequence

from ..elements import (
    Callout,
    CodeBlock,
    Element,
    Figure,
    Heading,
    HorizontalRule,
    Image,
    ListElement,
    Paragraph,
    Quote,
    Raw,
    Section,
    Table,
    TableOfContents,
)
from ..inline import Inline, InlineContent
from ..numbering import Numbering
from ..toc import collect_entries, find_tocs, plain_text

if TYPE_CHECKING:
    from ..report import Report

PAGE_MARGIN = 18  # mm
BODY_SIZE = 11
_HEADING_SIZES = {1: 20, 2: 16, 3: 13.5, 4: 12, 5: 11, 6: 10.5}
_TOC_TITLE_H = 10  # mm
_TOC_ROW_H = 7
_TOC_INDENT = 6
_TOC_PAGE_W = 12  # width of the page-number column

_TEXT = (31, 41, 55)
_MUTED = (107, 114, 128)
_ACCENT = (29, 78, 216)
_BORDER = (183, 189, 196)
_CODE_BG = (243, 244, 246)
_CALLOUT_COLORS = {
    "note": (29, 78, 216),
    "tip": (21, 128, 61),
    "important": (124, 58, 237),
    "warning": (180, 83, 9),
    "caution": (185, 28, 28),
}
_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
_SUBSCRIPT = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
# fpdf2 markdown markers for styled spans in table cells.
_CELL_MARKERS = {"bold": "**", "italic": "__", "strike": "~~"}
# Link text fpdf2's markdown link pattern accepts: no brackets.
_LINKABLE = re.compile(r"[^\[\]]+")

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
        # fpdf2 supports one TOC per document, so only the first is rendered.
        self._toc = next(find_tocs(report), None)
        self._toc_entries = collect_entries(report, self._toc.depth) if self._toc else []
        self._toc_ids = {id(entry.element) for entry in self._toc_entries}
        self._toc_targets: dict[int, tuple[int, int]] = {}  # id -> (link, page)
        self._footnotes: list[tuple[str, int]] = []  # (text, link)
        self._numbering = Numbering(report)
        self._ref_links: dict[str, int] = {}  # label -> fpdf link id
        pdf.add_page()
        pdf.set_title(report.title)
        if report.author:
            pdf.set_author(report.author)
        self._title_block(pdf, report)
        for child in report.children:
            self._element(pdf, child)
        if self._footnotes:
            self._endnotes(pdf)
        return bytes(pdf.output())

    # -- setup -----------------------------------------------------------

    def _setup_fonts(self, pdf) -> None:
        # fontTools logs a benign warning per unsupported table when
        # subsetting system fonts (e.g. Arial's MERG table); silence it.
        logging.getLogger("fontTools.subset").setLevel(logging.ERROR)
        # Links in table cells (rendered from markdown) match body links.
        pdf.MARKDOWN_LINK_COLOR = _ACCENT
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
            self._mark_toc_target(pdf, el)
            self._heading(pdf, el.title_parts, el._level)
            for child in el.children:
                self._element(pdf, child)
        elif isinstance(el, Heading):
            self._keep_with_next(pdf)
            self._mark_toc_target(pdf, el)
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
        elif isinstance(el, Figure):
            self._figure(pdf, el)
        elif isinstance(el, Image):
            self._image(pdf, el)
        elif isinstance(el, HorizontalRule):
            pdf.ln(2)
            pdf.set_draw_color(*_BORDER)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(4)
        elif isinstance(el, Raw):
            pass  # format-specific passthrough has no meaning in PDF
        elif isinstance(el, Callout):
            self._callout(pdf, el)
        elif isinstance(el, TableOfContents):
            if el is self._toc:
                # The TOC is drawn after the rest of the document, once page
                # numbers are known, into pages reserved here.
                self._toc_start = pdf.page_no()
                self._toc_pages = self._toc_page_count(pdf)
                pdf.insert_toc_placeholder(self._render_toc, pages=self._toc_pages)
        else:
            raise TypeError(f"Cannot render element of type {type(el).__name__}")

    # -- table of contents -----------------------------------------------

    def _mark_toc_target(self, pdf, el: Element) -> None:
        if id(el) in self._toc_ids:
            link = pdf.add_link()
            pdf.set_link(link, y=pdf.get_y(), page=pdf.page_no())
            self._toc_targets[id(el)] = (link, pdf.page_no())

    def _toc_page_count(self, pdf) -> int:
        # Must mirror the pagination in _render_toc exactly: fpdf2 raises if
        # the TOC ends on any page other than the last one reserved.
        y, pages = pdf.get_y(), 1

        def advance(h: float) -> None:
            nonlocal y, pages
            if y + h > pdf.page_break_trigger:
                pages += 1
                y = pdf.t_margin
            y += h

        assert self._toc is not None  # only called while rendering a TOC
        if self._toc.title:
            advance(_TOC_TITLE_H)
            y += 2
        for _ in self._toc_entries:
            advance(_TOC_ROW_H)
        return pages

    def _render_toc(self, pdf, outline) -> None:
        def make_room(h: float) -> None:
            if pdf.get_y() + h > pdf.page_break_trigger:
                pdf.add_page()

        assert self._toc is not None
        pdf.set_text_color(*_TEXT)
        if self._toc.title:
            make_room(_TOC_TITLE_H)
            pdf.set_font(self.body_family, "B", _HEADING_SIZES[2])
            pdf.cell(0, _TOC_TITLE_H, self._t(self._toc.title), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        for entry in self._toc_entries:
            make_room(_TOC_ROW_H)
            link, page = self._toc_targets.get(id(entry.element), ("", 0))
            indent = _TOC_INDENT * (entry.depth - 1)
            name_w = pdf.epw - indent - _TOC_PAGE_W
            pdf.set_font(self.body_family, "B" if entry.depth == 1 else "", BODY_SIZE)
            name = self._fit(pdf, self._t(plain_text(entry.parts)), name_w - 2)
            pdf.set_x(pdf.l_margin + indent)
            pdf.cell(name_w, _TOC_ROW_H, name, link=link)
            pdf.cell(_TOC_PAGE_W, _TOC_ROW_H, str(page or ""), align="R", link=link,
                     new_x="LMARGIN", new_y="NEXT")
        while pdf.page_no() < self._toc_start + self._toc_pages - 1:
            pdf.add_page()

    def _fit(self, pdf, text: str, width: float) -> str:
        """Truncate ``text`` with an ellipsis so it fits on one line."""
        if pdf.get_string_width(text) <= width:
            return text
        ellipsis = "…" if self.unicode else "..."
        while text and pdf.get_string_width(text + ellipsis) > width:
            text = text[:-1]
        return text.rstrip() + ellipsis

    def _callout(self, pdf, el: Callout) -> None:
        color = _CALLOUT_COLORS[el.kind]
        root = pdf.l_margin
        self._keep_with_next(pdf)
        pdf.ln(1)
        start_page, start_y = pdf.page_no(), pdf.get_y()
        pdf.set_left_margin(root + 5)
        pdf.set_x(root + 5)
        pdf.set_font(self.body_family, "B", BODY_SIZE)
        pdf.set_text_color(*color)
        pdf.multi_cell(0, 6.5, self._t(el.display_title), new_x="LMARGIN", new_y="NEXT")
        for child in el.children:
            self._element(pdf, child)
        end_page, end_y = pdf.page_no(), pdf.get_y()
        pdf.set_left_margin(root)
        # The coloured bar runs down the left edge, continuing across page
        # breaks: go back to each page the callout touched and draw on it.
        for page in range(start_page, end_page + 1):
            pdf.page = page
            # fpdf2 only writes colour/width when they change, and a revisited
            # page's stream may hold other values, so force both to be written.
            pdf.set_draw_color(*(255 - c for c in color))
            pdf.set_draw_color(*color)
            pdf.set_line_width(0.5)
            pdf.set_line_width(1)
            top = start_y if page == start_page else pdf.t_margin
            bottom = end_y if page == end_page else pdf.h - pdf.b_margin
            pdf.line(root + 1.5, top, root + 1.5, bottom)
        pdf.page = end_page
        pdf.set_line_width(0.2)
        pdf.set_y(end_y)
        pdf.ln(2)

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

    def _ref_link(self, pdf, label: str) -> int:
        # Created on first use, so references may come before their target.
        if label not in self._ref_links:
            self._ref_links[label] = pdf.add_link()
        return self._ref_links[label]

    def _mark_target(self, pdf, el: "Figure | Table") -> None:
        if el.label:
            pdf.set_link(self._ref_link(pdf, el.label), y=pdf.get_y(), page=pdf.page_no())

    def _caption(self, pdf, el: "Figure | Table", align: str = "L") -> None:
        pdf.ln(1)
        pdf.set_text_color(*_MUTED)
        pdf.set_font(self.body_family, "I", 9)
        text = f"**{self._numbering.caption_label(el)}:** {self._md_escape(el.caption)}"
        pdf.multi_cell(0, 5, self._t(text), align=align, markdown=True, new_x="LMARGIN", new_y="NEXT")

    def _figure(self, pdf, el: Figure) -> None:
        self._mark_target(pdf, el)
        w = pdf.epw * (el.width or 1)
        x = pdf.l_margin + (pdf.epw - w) / 2
        try:
            if el.kind == "path":
                source: object = str(el.source)
            else:
                source = io.BytesIO(el.image_data("png")[0])
            pdf.image(source, x=x, w=w)
        except Exception:
            # Missing/unreadable file: render a placeholder, keep going.
            pdf.set_font(self.body_family, "I", 10)
            pdf.set_text_color(*_MUTED)
            missing = el.alt or (str(el.source) if el.kind == "path" else "figure")
            pdf.multi_cell(0, 6, self._t(f"[Figure: {missing}]"), new_x="LMARGIN", new_y="NEXT")
        if el.caption:
            self._caption(pdf, el, align="C")
        pdf.ln(2.5)

    @staticmethod
    def _md_escape(text: str) -> str:
        # Escape fpdf2's markdown markers so caption text is shown literally.
        for marker in ("\\", "**", "__", "~~", "--"):
            text = text.replace(marker, "\\" + marker)
        return text

    def _table(self, pdf, el: Table) -> None:
        self._mark_target(pdf, el)
        pdf.set_font(self.body_family, "", 10)
        pdf.set_text_color(*_TEXT)
        pdf.set_draw_color(*_BORDER)
        aligns = tuple(a.upper() for a in el.align)
        with pdf.table(text_align=aligns, line_height=6, markdown=True) as table:
            header = table.row()
            for parts in el.headers:
                header.cell(self._t(self._cell_text(pdf, parts, heading=True)))
            for row_parts in el.rows:
                row = table.row()
                for parts in row_parts:
                    row.cell(self._t(self._cell_text(pdf, parts)))
        if el.caption:
            self._caption(pdf, el)
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
                elif part.style == "strike":
                    pdf.set_font(self.body_family, self._merge(base_style, "S"), size)
                    pdf.write(h, text)
                elif part.style in ("sub", "sup"):
                    pdf.set_font(self.body_family, base_style, size)
                    pdf.char_vpos = part.style.upper()
                    pdf.write(h, text)
                    pdf.char_vpos = "LINE"
                elif part.style == "ref":
                    shown = self._numbering.ref_text(part.href, part.text)
                    pdf.set_font(self.body_family, base_style, size)
                    pdf.set_text_color(*_ACCENT)
                    pdf.write(h, self._t(shown), link=self._ref_link(pdf, part.href))
                    pdf.set_text_color(*color)
                elif part.style == "footnote":
                    n, link = self._add_footnote(pdf, part.text)
                    pdf.set_font(self.body_family, base_style, size)
                    pdf.set_text_color(*_ACCENT)
                    pdf.char_vpos = "SUP"
                    pdf.write(h, str(n), link=link)
                    pdf.char_vpos = "LINE"
                    pdf.set_text_color(*color)
                else:
                    pdf.set_font(self.body_family, base_style, size)
                    pdf.write(h, text)
            else:
                pdf.set_font(self.body_family, base_style, size)
                pdf.write(h, self._t(str(part)))

    @staticmethod
    def _merge(base: str, extra: str) -> str:
        return "".join(s for s in ("B", "I", "U", "S") if s in base or s in extra)

    @staticmethod
    def _plain(parts: list[InlineContent]) -> str:
        return plain_text(parts)

    def _cell_text(self, pdf, parts: list[InlineContent], heading: bool = False) -> str:
        """Table cell content in fpdf2's markdown, which tables render with
        mixed styles: bold, italic, strikethrough and links. All text is
        escaped, so user text is never read as markup. Code spans and
        cross-references become plain text (cells can't switch fonts or hold
        internal links); footnotes and digit sub/superscripts use Unicode
        superscript/subscript characters when the font has them."""
        out = []
        for p in parts:
            if not isinstance(p, Inline):
                out.append(self._md_escape(str(p)))
            elif heading and p.style == "bold":
                # Header cells are already bold; a marker would toggle it off.
                out.append(self._md_escape(p.text))
            elif p.style in _CELL_MARKERS:
                marker = _CELL_MARKERS[p.style]
                out.append(f"{marker}{self._md_escape(p.text)}{marker}")
            elif p.style == "link" and _LINKABLE.fullmatch(p.text) and "(" not in p.href and ")" not in p.href:
                # Link text is taken literally by fpdf2, so it isn't escaped.
                out.append(f"[{p.text}]({p.href})")
            elif p.style == "footnote":
                n, _ = self._add_footnote(pdf, p.text)
                marker = str(n).translate(_SUPERSCRIPT)
                out.append(marker if self._has_glyphs(pdf, marker) else f"[{n}]")
            elif p.style in ("sub", "sup") and p.text.isdigit():
                # Digits have Unicode sub/superscript forms (CO₂, m²), but
                # not every font has them (Arial lacks subscripts).
                mapped = p.text.translate(_SUPERSCRIPT if p.style == "sup" else _SUBSCRIPT)
                out.append(mapped if self._has_glyphs(pdf, mapped) else p.text)
            elif p.style == "ref":
                out.append(self._md_escape(self._numbering.ref_text(p.href, p.text)))
            else:
                out.append(self._md_escape(p.text))
        return "".join(out)

    def _has_glyphs(self, pdf, text: str) -> bool:
        if not self.unicode:
            return False
        cmap = getattr(pdf.current_font, "cmap", None)
        return cmap is not None and all(ord(ch) in cmap for ch in text)

    # -- footnotes -------------------------------------------------------

    def _add_footnote(self, pdf, text: str) -> tuple[int, int]:
        # PDF has no automatic page-bottom footnotes, so notes are collected
        # here and rendered as linked endnotes after the content.
        link = pdf.add_link()
        self._footnotes.append((text, link))
        return len(self._footnotes), link

    def _endnotes(self, pdf) -> None:
        self._keep_with_next(pdf)
        pdf.start_section(self._t("Notes"), level=0)
        self._heading(pdf, ["Notes"], 2)
        for n, (text, link) in enumerate(self._footnotes, start=1):
            pdf.set_link(link, y=pdf.get_y(), page=pdf.page_no())
            pdf.set_font(self.body_family, "", 10)
            pdf.set_text_color(*_TEXT)
            pdf.multi_cell(0, 5.5, self._t(f"{n}. {text}"), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
