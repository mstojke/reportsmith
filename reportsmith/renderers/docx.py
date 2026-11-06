"""Word (.docx) renderer, written with the standard library only.

The output is an Office Open XML package (a zip of XML parts) that Word,
LibreOffice and Google Docs open: headings in Word's built-in heading styles
(so the navigation pane and Word's own TOC work), real footnotes, numbered
and bulleted lists, tables with repeating header rows, embedded images,
internal links for cross-references, and running headers and footers with
page fields.
"""

from __future__ import annotations

import io
import re
import struct
import zipfile
import zlib
from typing import TYPE_CHECKING, Optional, Sequence
from xml.sax.saxutils import escape as _xml_escape

from ..colors import to_hex
from ..elements import (
    Callout,
    CellStyle,
    CodeBlock,
    DefinitionList,
    Element,
    Equation,
    Figure,
    Heading,
    HorizontalRule,
    Image,
    ListElement,
    PageBreak,
    Paragraph,
    Quote,
    Raw,
    Section,
    Table,
    TableOfContents,
    TaskList,
)
from ..omml import M_NS, tex_to_omml
from ..highlight import pdf_tokens, require_pygments
from ..inline import Inline, InlineContent
from ..labels import callout_title, labels_for, toc_title
from ..numbering import Numbering, iter_elements
from ..page import segments
from ..toc import collect_entries, find_tocs, plain_text

if TYPE_CHECKING:
    from ..report import Report

# Page geometry (A4), in twentieths of a point ("twips").
PAGE_W, PAGE_H = 11906, 16838
MARGIN = 1134  # 2 cm
TEXT_W = PAGE_W - 2 * MARGIN
EMU_PER_TWIP = 635
TEXT_W_EMU = TEXT_W * EMU_PER_TWIP

_TEXT = "1F2937"
_MUTED = "6B7280"
_ACCENT = "1D4ED8"
_BORDER = "B7BDC4"
_CODE_BG = "F3F4F6"
_STRIPE = "F8F9FB"
_CALLOUT_COLORS = {
    "note": "1D4ED8",
    "tip": "15803D",
    "important": "7C3AED",
    "warning": "B45309",
    "caution": "B91C1C",
}
_TASK_MARKS = {True: "☑", False: "☐"}  # ☑ ☐
_BODY_FONT = "Calibri"
_MONO_FONT = "Consolas"

_NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
    f'xmlns:m="{M_NS}"'
)
_XML_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
# Characters XML 1.0 forbids: C0 controls other than tab, line feed and
# carriage return, and the noncharacters U+FFFE / U+FFFF. A str.translate
# table that deletes them (written as code points, so no invisible
# characters end up in this file).
_INVALID_XML = dict.fromkeys([c for c in range(0x20) if c not in (0x09, 0x0A, 0x0D)] + [0xFFFE, 0xFFFF])


def _esc(text: str, quote: bool = False) -> str:
    text = text.translate(_INVALID_XML)
    return _xml_escape(text, {'"': "&quot;"} if quote else {})


def _tint(hex_color: str, amount: float = 0.08) -> str:
    """``hex_color`` mixed with white: a pale background for callouts."""
    rgb = [int(hex_color[i:i + 2], 16) for i in (0, 2, 4)]
    return "".join(f"{round(255 - (255 - c) * amount):02X}" for c in rgb)


def image_size(data: bytes, fmt: str) -> Optional[tuple[int, int]]:
    """``(width, height)`` in pixels of PNG, JPEG or GIF data, or None."""
    try:
        if fmt == "png":
            return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        if fmt == "gif":
            return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
        if fmt == "jpeg":
            i = 2
            while i + 9 < len(data):
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                length = int.from_bytes(data[i + 2:i + 4], "big")
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    return int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big")
                i += 2 + length
    except (IndexError, ValueError):
        return None
    return None


_SVG_LENGTH = re.compile(r"^\s*([0-9.]+)\s*(px|pt|pc|mm|cm|in|em|ex|%)?\s*$")
_SVG_UNITS = {"": 1.0, "px": 1.0, "pt": 96 / 72, "pc": 16.0, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96.0,
              "em": 16.0, "ex": 8.0}


def svg_size(data: bytes) -> tuple[float, float]:
    """An SVG's intrinsic size in CSS pixels, from its ``width``/``height``
    (or ``viewBox``); 300 x 150, the browser default, when it has neither."""
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return 300.0, 150.0

    def length(value: str | None) -> float | None:
        match = _SVG_LENGTH.match(value or "")
        if not match or match.group(2) == "%":
            return None
        return float(match.group(1)) * _SVG_UNITS[match.group(2) or ""]

    width, height = length(root.get("width")), length(root.get("height"))
    box = (root.get("viewBox") or "").replace(",", " ").split()
    if len(box) == 4:
        box_w, box_h = float(box[2]), float(box[3])
        if box_w > 0 and box_h > 0:
            if width is None and height is None:
                width, height = box_w, box_h
            elif width is None and height is not None:
                width = height * box_w / box_h
            elif height is None and width is not None:
                height = width * box_h / box_w
    if not width or not height:
        return 300.0, 150.0
    return width, height


def placeholder_png(width: float, height: float) -> bytes:
    """A plain light-grey PNG with the given aspect ratio: the fallback
    picture Word requires next to an SVG (shown only by readers without SVG
    support)."""
    scale = 200 / max(width, height)
    w, h = max(1, round(width * scale)), max(1, round(height * scale))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    raw = b"".join(b"\x00" + b"\xf3\xf4\xf6" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class DocxRenderer:
    """Renders a Report to a Word document (``.docx`` bytes).

    ``highlight=True`` colours code blocks with Pygments.
    """

    def __init__(self, highlight: bool = False):
        self.highlight = highlight
        if highlight:
            require_pygments()

    # -- package ------------------------------------------------------------

    def render(self, report: "Report") -> bytes:
        self._report = report
        self._numbering = Numbering(report)
        self._labels = labels_for(report)
        self._rels: list[tuple[str, str, str, bool]] = []  # (id, type, target, external)
        self._media: list[tuple[str, bytes]] = []  # (file name, data)
        self._footnotes: list[str] = []
        self._header_footer_parts: list[tuple[str, str]] = []  # (file name, xml)
        self._lists: list[bool] = []  # one entry per list instance: ordered?
        self._bookmark_id = 0
        self._drawing_id = 0
        self._has_toc = any(find_tocs(report))
        # Bookmarks: every heading (TOC links) and every labelled target (refs).
        self._heading_marks: dict[int, str] = {}
        self._label_marks: dict[str, str] = {}
        n = 0
        for el in iter_elements(report):
            if isinstance(el, (Section, Heading)):
                n += 1
                self._heading_marks[id(el)] = f"_Toc{n:06d}"
            label = getattr(el, "label", "")
            if label and isinstance(el, (Section, Figure, Table, Equation)):
                self._label_marks[label] = f"_Ref{len(self._label_marks) + 1:06d}"

        for kind, target in (("styles", "styles.xml"), ("settings", "settings.xml"),
                             ("numbering", "numbering.xml"), ("footnotes", "footnotes.xml")):
            self._rel(f"{_REL}/{kind}", target)

        body = []
        if report.cover is not None:
            body.append(self._cover(report))
        else:
            body.append(self._title_block(report))
        for child in report.children:
            body.append(self._element(child))
        body.append(self._final_section(report))
        document = (
            f"{_XML_HEAD}<w:document {_NS}><w:body>{''.join(body)}</w:body></w:document>"
        )

        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            def add(name: str, content) -> None:
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, content)

            add("[Content_Types].xml", self._content_types())
            add("_rels/.rels", self._package_rels())
            add("docProps/core.xml", self._core(report))
            add("docProps/app.xml", self._app())
            add("word/document.xml", document)
            add("word/styles.xml", self._styles(report))
            add("word/settings.xml", self._settings())
            add("word/numbering.xml", self._numbering_part())
            add("word/footnotes.xml", self._footnotes_part())
            for name, content in self._header_footer_parts:
                add(f"word/{name}", content)
            for name, data in self._media:
                add(f"word/media/{name}", data)
            add("word/_rels/document.xml.rels", self._document_rels())
        return out.getvalue()

    def _rel(self, rel_type: str, target: str, external: bool = False) -> str:
        rid = f"rId{len(self._rels) + 1}"
        self._rels.append((rid, rel_type, target, external))
        return rid

    def _document_rels(self) -> str:
        rels = "".join(
            f'<Relationship Id="{rid}" Type="{rtype}" Target="{_esc(target, True)}"'
            + (' TargetMode="External"' if external else "") + "/>"
            for rid, rtype, target, external in self._rels
        )
        return (
            f'{_XML_HEAD}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{rels}</Relationships>"
        )

    def _content_types(self) -> str:
        overrides = [
            ("/word/document.xml", "wordprocessingml.document.main"),
            ("/word/styles.xml", "wordprocessingml.styles"),
            ("/word/settings.xml", "wordprocessingml.settings"),
            ("/word/numbering.xml", "wordprocessingml.numbering"),
            ("/word/footnotes.xml", "wordprocessingml.footnotes"),
        ]
        for name, _ in self._header_footer_parts:
            kind = "header" if name.startswith("header") else "footer"
            overrides.append((f"/word/{name}", f"wordprocessingml.{kind}"))
        parts = "".join(
            f'<Override PartName="{name}" ContentType="application/vnd.openxmlformats-officedocument.{kind}+xml"/>'
            for name, kind in overrides
        )
        return (
            f'{_XML_HEAD}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="png" ContentType="image/png"/>'
            '<Default Extension="jpeg" ContentType="image/jpeg"/>'
            '<Default Extension="gif" ContentType="image/gif"/>'
            '<Default Extension="svg" ContentType="image/svg+xml"/>'
            f"{parts}"
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            "</Types>"
        )

    @staticmethod
    def _package_rels() -> str:
        return (
            f'{_XML_HEAD}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{_REL}/officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            f'<Relationship Id="rId3" Type="{_REL}/extended-properties" Target="docProps/app.xml"/>'
            "</Relationships>"
        )

    @staticmethod
    def _core(report: "Report") -> str:
        fields = [
            ("dc:title", report.title),
            ("dc:subject", report.description),
            ("dc:creator", report.author),
            ("cp:keywords", ", ".join(report.keywords)),
            ("dc:language", report.language),
        ]
        body = "".join(f"<{tag}>{_esc(value)}</{tag}>" for tag, value in fields if value)
        return (
            f'{_XML_HEAD}<cp:coreProperties '
            'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f"{body}</cp:coreProperties>"
        )

    @staticmethod
    def _app() -> str:
        from .. import __version__

        return (
            f'{_XML_HEAD}<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
            f"<Application>reportsmith {_esc(__version__)}</Application></Properties>"
        )

    def _settings(self) -> str:
        # Word fills in the TOC's page numbers when it updates fields on open.
        update = '<w:updateFields w:val="true"/>' if self._has_toc else ""
        return (
            f"{_XML_HEAD}<w:settings {_NS}>"
            '<w:defaultTabStop w:val="708"/>'
            '<w:characterSpacingControl w:val="doNotCompress"/>'
            f"{update}"
            '<w:footnotePr><w:footnote w:id="-1"/><w:footnote w:id="0"/></w:footnotePr>'
            '<w:compat><w:compatSetting w:name="compatibilityMode" '
            'w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat>'
            "</w:settings>"
        )

    def _styles(self, report: "Report") -> str:
        lang = _esc(report.language or "en", True)

        def para(style_id: str, name: str, ppr: str = "", rpr: str = "", based: str = "Normal",
                 extra: str = "") -> str:
            base = f'<w:basedOn w:val="{based}"/>' if based else ""
            return (
                f'<w:style w:type="paragraph" w:styleId="{style_id}"><w:name w:val="{name}"/>{base}'
                f'<w:next w:val="Normal"/>{extra}<w:qFormat/>'
                f"{f'<w:pPr>{ppr}</w:pPr>' if ppr else ''}{f'<w:rPr>{rpr}</w:rPr>' if rpr else ''}</w:style>"
            )

        sizes = {1: 32, 2: 26, 3: 23, 4: 22, 5: 22, 6: 22}
        headings = "".join(
            para(
                f"Heading{n}", f"heading {n}",
                ppr=(
                    "<w:keepNext/><w:keepLines/>"
                    + (f'<w:pBdr><w:bottom w:val="single" w:sz="4" w:space="2" w:color="{_BORDER}"/></w:pBdr>'
                       if n == 1 else "")
                    + f'<w:spacing w:before="{360 if n == 1 else 240}" w:after="120"/>'
                    + f'<w:outlineLvl w:val="{n - 1}"/>'
                ),
                rpr=f'<w:b/><w:color w:val="{_TEXT}"/><w:sz w:val="{sizes[n]}"/>',
            )
            for n in range(1, 7)
        )
        tocs = "".join(
            para(f"TOC{n}", f"toc {n}", ppr=f'<w:spacing w:after="60"/><w:ind w:left="{(n - 1) * 240}"/>')
            for n in range(1, 7)
        )
        return (
            f"{_XML_HEAD}<w:styles {_NS}>"
            "<w:docDefaults><w:rPrDefault><w:rPr>"
            f'<w:rFonts w:ascii="{_BODY_FONT}" w:hAnsi="{_BODY_FONT}" w:eastAsia="{_BODY_FONT}" w:cs="{_BODY_FONT}"/>'
            f'<w:color w:val="{_TEXT}"/><w:sz w:val="22"/><w:szCs w:val="22"/>'
            f'<w:lang w:val="{lang}"/>'
            "</w:rPr></w:rPrDefault>"
            '<w:pPrDefault><w:pPr><w:spacing w:after="160" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
            "</w:docDefaults>"
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
            + para("Title", "Title", ppr='<w:spacing w:after="60"/>',
                   rpr=f'<w:b/><w:color w:val="{_TEXT}"/><w:sz w:val="44"/>')
            + para("Subtitle", "Subtitle", ppr='<w:spacing w:after="60"/>',
                   rpr=f'<w:i/><w:color w:val="{_MUTED}"/><w:sz w:val="26"/>')
            + headings
            + para("Quote", "Quote",
                   ppr=(f'<w:pBdr><w:left w:val="single" w:sz="24" w:space="8" w:color="{_BORDER}"/></w:pBdr>'
                        '<w:ind w:left="284"/>'),
                   rpr=f'<w:color w:val="{_MUTED}"/>')
            + para("Caption", "caption", ppr='<w:spacing w:before="60" w:after="200"/>',
                   rpr=f'<w:i/><w:color w:val="{_MUTED}"/><w:sz w:val="18"/>')
            + para("Code", "Code",
                   ppr=(f'<w:shd w:val="clear" w:color="auto" w:fill="{_CODE_BG}"/>'
                        '<w:spacing w:after="160" w:line="240" w:lineRule="auto"/>'),
                   rpr=f'<w:rFonts w:ascii="{_MONO_FONT}" w:hAnsi="{_MONO_FONT}" w:cs="{_MONO_FONT}"/><w:sz w:val="19"/>')
            + para("ListParagraph", "List Paragraph", ppr='<w:spacing w:after="60"/><w:contextualSpacing/>')
            + para("TOCHeading", "TOC Heading", ppr='<w:keepNext/><w:spacing w:before="240" w:after="120"/>',
                   rpr='<w:b/><w:sz w:val="28"/>')
            + tocs
            + para("FootnoteText", "footnote text", ppr='<w:spacing w:after="0" w:line="240" w:lineRule="auto"/>',
                   rpr='<w:sz w:val="18"/>')
            + '<w:style w:type="character" w:styleId="FootnoteReference"><w:name w:val="footnote reference"/>'
            '<w:rPr><w:vertAlign w:val="superscript"/></w:rPr></w:style>'
            + '<w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/>'
            f'<w:rPr><w:color w:val="{_ACCENT}"/><w:u w:val="single"/></w:rPr></w:style>'
            + "</w:styles>"
        )

    def _numbering_part(self) -> str:
        abstracts, nums = [], []
        bullets = ["•", "◦", "▪"]
        for n, ordered in enumerate(self._lists):
            levels = []
            for lvl in range(9):
                if ordered:
                    fmt, text = "decimal", f"%{lvl + 1}."
                else:
                    fmt, text = "bullet", bullets[lvl % 3]
                levels.append(
                    f'<w:lvl w:ilvl="{lvl}"><w:start w:val="1"/><w:numFmt w:val="{fmt}"/>'
                    f'<w:lvlText w:val="{text}"/><w:lvlJc w:val="left"/>'
                    f'<w:pPr><w:ind w:left="{360 * (lvl + 2)}" w:hanging="360"/></w:pPr></w:lvl>'
                )
            abstracts.append(
                f'<w:abstractNum w:abstractNumId="{n}"><w:multiLevelType w:val="hybridMultilevel"/>'
                f'{"".join(levels)}</w:abstractNum>'
            )
            nums.append(f'<w:num w:numId="{n + 1}"><w:abstractNumId w:val="{n}"/></w:num>')
        return f"{_XML_HEAD}<w:numbering {_NS}>{''.join(abstracts)}{''.join(nums)}</w:numbering>"

    def _footnotes_part(self) -> str:
        notes = [
            '<w:footnote w:type="separator" w:id="-1"><w:p><w:pPr><w:spacing w:after="0"/></w:pPr>'
            "<w:r><w:separator/></w:r></w:p></w:footnote>",
            '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:pPr><w:spacing w:after="0"/></w:pPr>'
            "<w:r><w:continuationSeparator/></w:r></w:p></w:footnote>",
        ]
        for n, text in enumerate(self._footnotes, start=1):
            notes.append(
                f'<w:footnote w:id="{n}"><w:p><w:pPr><w:pStyle w:val="FootnoteText"/></w:pPr>'
                '<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteRef/></w:r>'
                f"{self._run(' ' + text)}</w:p></w:footnote>"
            )
        return f"{_XML_HEAD}<w:footnotes {_NS}>{''.join(notes)}</w:footnotes>"

    # -- sections, headers and footers --------------------------------------

    def _band_paragraph(self, band) -> str:
        """A header/footer line: left, centre and right text on tab stops."""
        report = self._report
        runs = []
        for i, text in enumerate(band):
            if i:
                runs.append(self._run_xml("<w:tab/>", self._band_rpr()))
            for kind, value in segments(text, report):
                if kind in ("page", "pages"):
                    instr = "PAGE" if kind == "page" else "NUMPAGES"
                    runs.append(
                        f'<w:fldSimple w:instr=" {instr} ">{self._run_xml("<w:t>1</w:t>", self._band_rpr())}</w:fldSimple>'
                    )
                else:
                    runs.append(self._run(value, self._band_rpr()))
        tabs = (
            f'<w:tabs><w:tab w:val="center" w:pos="{TEXT_W // 2}"/>'
            f'<w:tab w:val="right" w:pos="{TEXT_W}"/></w:tabs>'
        )
        return f'<w:p><w:pPr>{tabs}<w:spacing w:after="0"/></w:pPr>{"".join(runs)}</w:p>'

    @staticmethod
    def _band_rpr() -> str:
        return f'<w:color w:val="{_MUTED}"/><w:sz w:val="17"/>'

    def _band_part(self, kind: str, band, content: str = "") -> str:
        """Add a header/footer part (from a band, or ready-made paragraph
        ``content``); returns its relationship id."""
        tag = "hdr" if kind == "header" else "ftr"
        if not content:
            content = self._band_paragraph(band) if band is not None else "<w:p/>"
        name = f"{kind}{len(self._header_footer_parts) + 1}.xml"
        self._header_footer_parts.append((name, f"{_XML_HEAD}<w:{tag} {_NS}>{content}</w:{tag}>"))
        return self._rel(f"{_REL}/{kind}", name)

    def _sect_pr(self, refs: str = "", extra: str = "", first_page: bool = False) -> str:
        return (
            f"<w:sectPr>{refs}"
            f'<w:pgSz w:w="{PAGE_W}" w:h="{PAGE_H}"/>'
            f'<w:pgMar w:top="{MARGIN}" w:right="{MARGIN}" w:bottom="{MARGIN}" w:left="{MARGIN}" '
            'w:header="567" w:footer="567" w:gutter="0"/>'
            f"{extra}{'<w:titlePg/>' if first_page else ''}</w:sectPr>"
        )

    def _final_section(self, report: "Report") -> str:
        """The body's section properties: running header and footer. Without
        a cover, the first page (with the title block) has no header."""
        refs = []
        if report.header is not None:
            refs.append(f'<w:headerReference w:type="default" r:id="{self._band_part("header", report.header)}"/>')
        if report.footer is not None:
            refs.append(f'<w:footerReference w:type="default" r:id="{self._band_part("footer", report.footer)}"/>')
        elif report.cover is not None and report.cover.note:
            # Without its own footer, the body would inherit the cover's note.
            refs.append(f'<w:footerReference w:type="default" r:id="{self._band_part("footer", None)}"/>')
        first_page = report.header is not None and report.cover is None
        if first_page:
            refs.append(f'<w:headerReference w:type="first" r:id="{self._band_part("header", None)}"/>')
            if report.footer is not None:
                refs.append(f'<w:footerReference w:type="first" r:id="{self._band_part("footer", report.footer)}"/>')
        # Header references come before footer references in the schema.
        refs.sort(key=lambda ref: not ref.startswith("<w:header"))
        return self._sect_pr("".join(refs), first_page=first_page)

    # -- title block and cover ----------------------------------------------

    def _title_block(self, report: "Report") -> str:
        out = [self._para(self._run(report.title), style="Title")]
        if report.subtitle:
            out.append(self._para(self._run(report.subtitle), style="Subtitle"))
        meta = []
        if report.author:
            meta.append((self._labels["author"], report.author))
        if report.date:
            meta.append((self._labels["date"], report.date))
        if meta:
            runs = []
            rpr = f'<w:color w:val="{_MUTED}"/><w:sz w:val="19"/>'
            for i, (label, value) in enumerate(meta):
                if i:
                    runs.append(self._run_xml("<w:br/>", rpr))
                runs.append(self._run(f"{label}: ", "<w:b/>" + rpr))
                runs.append(self._run(value, rpr))
            border = f'<w:pBdr><w:bottom w:val="single" w:sz="4" w:space="6" w:color="{_BORDER}"/></w:pBdr>'
            out.append(self._para("".join(runs), ppr=border + '<w:spacing w:after="360"/>'))
        return "".join(out)

    def _cover(self, report: "Report") -> str:
        """The cover: its own section, centred vertically on the page, with
        no header or footer. The body continues on the next page."""
        cover = report.cover
        assert cover is not None
        center = '<w:jc w:val="center"/>'
        out = []
        if cover.logo is not None:
            out.append(self._para(self._figure_run(cover.logo), ppr='<w:spacing w:after="240"/>' + center))
        if cover.organization:
            out.append(self._para(
                self._run(cover.organization, f'<w:b/><w:color w:val="{_MUTED}"/><w:sz w:val="26"/>'),
                ppr='<w:spacing w:after="1200"/>' + center,
            ))
        out.append(self._para(self._run(report.title, '<w:sz w:val="56"/>'), style="Title",
                              ppr='<w:spacing w:after="200"/>' + center))
        if report.subtitle:
            out.append(self._para(self._run(report.subtitle, '<w:i w:val="0"/><w:sz w:val="30"/>'),
                                  style="Subtitle", ppr=center))
        meta = [x for x in (report.author, report.date) if x]
        if meta:
            rule = f'<w:pBdr><w:bottom w:val="single" w:sz="12" w:space="1" w:color="{_ACCENT}"/></w:pBdr>'
            out.append(self._para("", ppr=rule + '<w:spacing w:before="240" w:after="360"/>'
                                  f'<w:ind w:left="{TEXT_W // 2 - 850}" w:right="{TEXT_W // 2 - 850}"/>'))
            runs = []
            for i, value in enumerate(meta):
                if i:
                    runs.append(self._run_xml("<w:br/>", '<w:sz w:val="24"/>'))
                runs.append(self._run(value, '<w:sz w:val="24"/>'))
            out.append(self._para("".join(runs), ppr=center))
        refs = ""
        if cover.note:
            # The note goes in the cover section's footer: the foot of the page.
            note = self._para(self._run(cover.note, f'<w:color w:val="{_MUTED}"/><w:sz w:val="18"/>'),
                              ppr='<w:spacing w:after="0"/>' + center)
            refs = f'<w:footerReference w:type="default" r:id="{self._band_part("footer", None, note)}"/>'
        # The section break ends the cover's section: next page, vertically centred.
        sect = self._sect_pr(refs, extra='<w:vAlign w:val="center"/>')
        out.append(f"<w:p><w:pPr>{sect}</w:pPr></w:p>")
        return "".join(out)

    # -- block elements -----------------------------------------------------

    def _element(self, el: Element) -> str:
        if isinstance(el, Section):
            out = [self._heading(el, el.title_parts, el._level - 1, getattr(el, "label", ""))]
            out.extend(self._element(child) for child in el.children)
            return "".join(out)
        if isinstance(el, Heading):
            return self._heading(el, el.parts, el.level - 1)
        if isinstance(el, Paragraph):
            return self._para(self._inline(el.parts))
        if isinstance(el, Quote):
            return self._para(self._inline(el.parts), style="Quote")
        if isinstance(el, CodeBlock):
            return self._code(el)
        if isinstance(el, ListElement):
            return self._list(el, 0)
        if isinstance(el, DefinitionList):
            out = []
            for term, definition in el.items:
                out.append(self._para(self._inline(term, "<w:b/>"), ppr='<w:keepNext/><w:spacing w:after="0"/>'))
                out.append(self._para(self._inline(definition), ppr='<w:ind w:left="567"/>'))
            return "".join(out)
        if isinstance(el, TaskList):
            return "".join(
                self._para(self._run(f"{_TASK_MARKS[done]}\t") + self._inline(text),
                           style="ListParagraph",
                           ppr=f'<w:tabs><w:tab w:val="left" w:pos="{720}"/></w:tabs><w:ind w:left="720" w:hanging="360"/>')
                for done, text in el.items
            )
        if isinstance(el, PageBreak):
            return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
        if isinstance(el, Table):
            return self._table(el)
        if isinstance(el, Figure):
            return self._figure(el)
        if isinstance(el, Image):
            return self._image(el)
        if isinstance(el, Equation):
            return self._equation(el)
        if isinstance(el, HorizontalRule):
            border = f'<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="{_BORDER}"/></w:pBdr>'
            return self._para("", ppr=border)
        if isinstance(el, Raw):
            return ""  # format-specific passthrough has no Word variant
        if isinstance(el, TableOfContents):
            return self._toc(el)
        if isinstance(el, Callout):
            return self._callout(el)
        raise TypeError(f"Cannot render element of type {type(el).__name__}")

    def _heading(self, el: "Section | Heading", parts: list[InlineContent], level: int, label: str = "") -> str:
        level = min(max(level, 1), 6)
        number = self._numbering.section_number(el)
        runs = (self._run(f"{number} ") if number else "") + self._inline(parts)
        marks = [self._heading_marks[id(el)]]
        if label:
            marks.append(self._label_marks[label])
        return self._para(self._bookmarked(runs, marks), style=f"Heading{level}")

    def _bookmarked(self, content: str, names: Sequence[str]) -> str:
        starts, ends = [], []
        for name in names:
            self._bookmark_id += 1
            starts.append(f'<w:bookmarkStart w:id="{self._bookmark_id}" w:name="{name}"/>')
            ends.append(f'<w:bookmarkEnd w:id="{self._bookmark_id}"/>')
        return "".join(starts) + content + "".join(reversed(ends))

    def _code(self, el: CodeBlock) -> str:
        runs = pdf_tokens(el.source, el.language) if self.highlight else None
        if runs is None:
            return self._para(self._run(el.source), style="Code")
        out = []
        for text, rgb, font_style in runs:
            rpr = ("<w:b/>" if "B" in font_style else "") + ("<w:i/>" if "I" in font_style else "")
            if rgb:
                rpr += f'<w:color w:val="{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"/>'
            out.append(self._run(text, rpr))
        return self._para("".join(out), style="Code")

    def _list(self, el: ListElement, depth: int) -> str:
        self._lists.append(el.ordered)
        num_id = len(self._lists)
        out = []
        for item in el.items:
            if isinstance(item, ListElement):
                out.append(self._list(item, depth + 1))
            else:
                numpr = f'<w:numPr><w:ilvl w:val="{min(depth, 8)}"/><w:numId w:val="{num_id}"/></w:numPr>'
                out.append(self._para(self._inline(item), style="ListParagraph", ppr=numpr))
        return "".join(out)

    def _caption(self, el: "Figure | Table", align: str = "left") -> str:
        label = self._numbering.caption_label(el)
        runs = self._run(f"{label}: ", "<w:b/>") + self._run(el.caption)
        if el.label:
            runs = self._bookmarked(runs, [self._label_marks[el.label]])
        jc = f'<w:jc w:val="{align}"/>' if align != "left" else ""
        return self._para(runs, style="Caption", ppr=jc)

    def _table(self, el: Table) -> str:
        columns = len(el.headers)
        fractions = el.widths or [1 / columns] * columns
        grid = "".join(f'<w:gridCol w:w="{round(TEXT_W * f)}"/>' for f in fractions)
        border = f'w:val="single" w:sz="4" w:space="0" w:color="{_BORDER}"'
        tbl_pr = (
            '<w:tblPr><w:tblW w:w="5000" w:type="pct"/>'
            f"<w:tblBorders><w:top {border}/><w:left {border}/><w:bottom {border}/><w:right {border}/>"
            f"<w:insideH {border}/><w:insideV {border}/></w:tblBorders>"
            + ('<w:tblLayout w:type="fixed"/>' if el.widths else "")
            + '<w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:left w:w="100" w:type="dxa"/>'
            '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar>'
            '<w:tblLook w:val="0020" w:firstRow="1" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" '
            'w:noHBand="0" w:noVBand="1"/></w:tblPr>'
        )

        def cell(parts, column: int, style: CellStyle, fill: Optional[str] = None,
                 bold: bool = False, top_border: bool = False) -> str:
            rpr = "<w:b/>" if bold or style.bold else ""
            if style.color:
                rpr += f'<w:color w:val="{to_hex(style.color)[1:].upper()}"/>'
            if style.background:
                fill = to_hex(style.background, True)[1:].upper()
            tc_pr = f'<w:tcW w:w="{round(TEXT_W * fractions[column])}" w:type="dxa"/>'
            if top_border:
                tc_pr += f'<w:tcBorders><w:top w:val="single" w:sz="12" w:space="0" w:color="{_MUTED}"/></w:tcBorders>'
            if fill:
                tc_pr += f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>'
            align = {"left": "left", "center": "center", "right": "right"}[el.align[column]]
            jc = f'<w:jc w:val="{align}"/>' if align != "left" else ""
            p = self._para(self._inline(parts, rpr), ppr=f'<w:spacing w:after="0"/>{jc}')
            return f"<w:tc><w:tcPr>{tc_pr}</w:tcPr>{p}</w:tc>"

        rows = [
            '<w:tr><w:trPr><w:tblHeader/></w:trPr>'
            + "".join(cell(h, j, CellStyle(), fill=_CODE_BG, bold=True) for j, h in enumerate(el.headers))
            + "</w:tr>"
        ]
        for i, row in enumerate(el.rows):
            fill = _STRIPE if el.striped and i % 2 == 1 else None
            rows.append(
                "<w:tr><w:trPr><w:cantSplit/></w:trPr>"
                + "".join(cell(parts, j, el.style_at(i, j), fill=fill) for j, parts in enumerate(row))
                + "</w:tr>"
            )
        if el.footer is not None:
            rows.append(
                "<w:tr><w:trPr><w:cantSplit/></w:trPr>"
                + "".join(
                    cell(parts, j, el.footer_styles.get(j, CellStyle()), bold=True, top_border=True)
                    for j, parts in enumerate(el.footer)
                )
                + "</w:tr>"
            )
        out = f"<w:tbl>{tbl_pr}<w:tblGrid>{grid}</w:tblGrid>{''.join(rows)}</w:tbl>"
        if el.caption:
            return out + self._caption(el)
        # A paragraph keeps the next table (or the end of a cell) apart.
        return out + self._para("", ppr='<w:spacing w:after="120"/>')

    def _figure(self, el: Figure) -> str:
        p = self._para(self._figure_run(el), ppr='<w:keepNext/><w:spacing w:after="60"/><w:jc w:val="center"/>')
        if el.caption:
            return p + self._caption(el, align="center")
        return p

    def _figure_run(self, el: Figure) -> str:
        """An inline picture run for a figure, or placeholder text when the
        image can't be embedded (missing or unreadable file). SVG figures
        and plots are embedded as SVG, which Word shows, with a PNG next to
        them for readers without SVG support."""
        try:
            data, fmt = el.image_data("png")
        except OSError:
            data, fmt = b"", ""
        if fmt == "svg":
            width, height = svg_size(data)
            cx = round(TEXT_W_EMU * el.width) if el.width else min(round(width * 9525), TEXT_W_EMU)
            cy = round(cx * height / width)
            return self._drawing(placeholder_png(width, height), "png", cx, cy, el.alt, svg=data)
        size = image_size(data, fmt) if fmt in ("png", "jpeg", "gif") else None
        if size is None or not all(size):
            name = self._labels["figure"]
            missing = el.alt or (str(el.source) if el.kind == "path" else "")
            text = f"[{name}: {missing}]" if missing else f"[{name}]"
            return self._run(text, f'<w:i/><w:color w:val="{_MUTED}"/>')
        dpi = el.dpi if el.kind == "plot" else 96
        if el.width:
            cx = round(TEXT_W_EMU * el.width)
        else:
            cx = min(round(size[0] * 914400 / dpi), TEXT_W_EMU)
        cy = round(cx * size[1] / size[0])
        svg = None
        if el.kind == "plot":
            try:
                svg = el.image_data("svg")[0]  # vector in Word; the PNG is its fallback
            except Exception:  # a plot object that can't save SVG keeps just the PNG
                svg = None
        return self._drawing(data, fmt, cx, cy, el.alt, svg=svg)

    def _drawing(self, data: bytes, fmt: str, cx: int, cy: int, alt: str = "",
                 svg: Optional[bytes] = None) -> str:
        """An inline picture. With ``svg``, Word (2016 and later) shows the
        SVG and other readers the bitmap ``data``."""
        self._drawing_id += 1
        n = self._drawing_id
        name = f"image{len(self._media) + 1}.{fmt}"
        self._media.append((name, data))
        rid = self._rel(f"{_REL}/image", f"media/{name}")
        ext = ""
        if svg is not None:
            svg_name = f"image{len(self._media) + 1}.svg"
            self._media.append((svg_name, svg))
            svg_rid = self._rel(f"{_REL}/image", f"media/{svg_name}")
            ext = (
                '<a:extLst><a:ext uri="{96DAC541-7B7A-43D3-8B79-37D633B846F1}">'
                '<asvg:svgBlip xmlns:asvg="http://schemas.microsoft.com/office/drawing/2016/SVG/main" '
                f'r:embed="{svg_rid}"/></a:ext></a:extLst>'
            )
        return (
            '<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
            f'<wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:docPr id="{n}" name="Picture {n}" descr="{_esc(alt, True)}"/>'
            '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{n}" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}">{ext}</a:blip><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
            "</a:graphicData></a:graphic></wp:inline></w:drawing></w:r>"
        )

    def _image(self, el: Image) -> str:
        caption = el.title or el.alt
        if el.src.startswith(("http://", "https://")):
            # Word can't embed a remote image when the file is written: link it.
            name = self._labels["image"]
            run = self._hyperlink(self._run(f"[{name}: {caption or el.src}]", '<w:rStyle w:val="Hyperlink"/>'), el.src)
            return self._para(run)
        try:
            figure = Figure(el.src, alt=el.alt)
            run = self._figure_run(figure)
        except (TypeError, ValueError):
            run = self._run(f"[{self._labels['image']}: {caption or el.src}]", f'<w:i/><w:color w:val="{_MUTED}"/>')
        out = self._para(run, ppr='<w:spacing w:after="60"/><w:jc w:val="center"/>')
        if caption:
            out += self._para(self._run(caption), style="Caption", ppr='<w:jc w:val="center"/>')
        return out

    def _equation(self, el: Equation) -> str:
        """A display equation as an editable Word equation. A numbered one
        sits in a borderless three-column table, centred, with "(n)" at the
        right margin, so Word keeps it in display style."""
        number = self._numbering.equation_number(el)
        math = f"<m:oMathPara>{tex_to_omml(el.tex)}</m:oMathPara>"
        if el.label:
            math = self._bookmarked(math, [self._label_marks[el.label]])
        spacing = '<w:spacing w:before="120" w:after="200"/>'
        if not number:
            return self._para(math, ppr=spacing)
        side, middle = TEXT_W // 10, TEXT_W - 2 * (TEXT_W // 10)
        none = 'w:val="nil"'
        tbl_pr = (
            '<w:tblPr><w:tblW w:w="5000" w:type="pct"/>'
            f"<w:tblBorders><w:top {none}/><w:left {none}/><w:bottom {none}/><w:right {none}/>"
            f"<w:insideH {none}/><w:insideV {none}/></w:tblBorders>"
            '<w:tblLayout w:type="fixed"/></w:tblPr>'
        )

        def cell(width: int, content: str) -> str:
            return (f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/><w:vAlign w:val="center"/></w:tcPr>'
                    f"{content}</w:tc>")

        row = (
            cell(side, "<w:p/>")
            + cell(middle, self._para(math, ppr=spacing))
            + cell(side, self._para(self._run(f"({number})"), ppr='<w:spacing w:after="0"/><w:jc w:val="right"/>'))
        )
        grid = f'<w:gridCol w:w="{side}"/><w:gridCol w:w="{middle}"/><w:gridCol w:w="{side}"/>'
        return (f"<w:tbl>{tbl_pr}<w:tblGrid>{grid}</w:tblGrid><w:tr>{row}</w:tr></w:tbl>"
                + self._para("", ppr='<w:spacing w:after="0"/>'))

    def _toc(self, el: TableOfContents) -> str:
        """Word's TOC field, filled with linked entries so it reads well
        before Word updates it (and adds page numbers) on opening."""
        out = []
        title = toc_title(el, self._labels)
        if title:
            out.append(self._para(self._run(title), style="TOCHeading"))
        entries = collect_entries(self._report, el.depth, self._numbering)
        begin = (
            '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            f'<w:r><w:instrText xml:space="preserve"> TOC \\o "1-{el.depth}" \\h \\z \\u </w:instrText></w:r>'
            '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        )
        end = '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
        if not entries:
            return "".join(out) + self._para(begin + end)
        for i, entry in enumerate(entries):
            text = plain_text(entry.parts)
            if entry.number:
                text = f"{entry.number} {text}"
            link = self._hyperlink(self._run(text), anchor=self._heading_marks[id(entry.element)])
            runs = (begin if i == 0 else "") + link + (end if i == len(entries) - 1 else "")
            out.append(self._para(runs, style=f"TOC{min(entry.depth, 6)}"))
        return "".join(out)

    def _callout(self, el: Callout) -> str:
        """A one-cell table with a coloured left bar and a pale background."""
        color = _CALLOUT_COLORS[el.kind]
        title = self._para(self._run(callout_title(el, self._labels), f'<w:b/><w:color w:val="{color}"/>'),
                           ppr='<w:keepNext/><w:spacing w:after="60"/>')
        body = "".join(self._element(child) for child in el.children)
        if not body.endswith("</w:p>"):
            body += self._para("", ppr='<w:spacing w:after="0"/>')
        none = 'w:val="nil"'
        tbl_pr = (
            '<w:tblPr><w:tblW w:w="5000" w:type="pct"/>'
            f'<w:tblBorders><w:top {none}/><w:left w:val="single" w:sz="24" w:space="0" w:color="{color}"/>'
            f"<w:bottom {none}/><w:right {none}/><w:insideH {none}/><w:insideV {none}/></w:tblBorders>"
            '<w:tblCellMar><w:top w:w="100" w:type="dxa"/><w:left w:w="200" w:type="dxa"/>'
            '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="200" w:type="dxa"/></w:tblCellMar></w:tblPr>'
        )
        cell = (
            f'<w:tc><w:tcPr><w:tcW w:w="{TEXT_W}" w:type="dxa"/>'
            f'<w:shd w:val="clear" w:color="auto" w:fill="{_tint(color)}"/></w:tcPr>{title}{body}</w:tc>'
        )
        return (
            f'<w:tbl>{tbl_pr}<w:tblGrid><w:gridCol w:w="{TEXT_W}"/></w:tblGrid><w:tr>{cell}</w:tr></w:tbl>'
            + self._para("", ppr='<w:spacing w:after="120"/>')
        )

    # -- inline -------------------------------------------------------------

    def _inline(self, parts: list[InlineContent], base_rpr: str = "") -> str:
        out = self._inline_runs(parts, base_rpr)
        # Word shows a paragraph holding nothing but math as a centred display
        # equation; an invisible character keeps such math inline.
        if parts and all(
            (isinstance(p, Inline) and p.style == "math") or (isinstance(p, str) and not p.strip())
            for p in parts
        ):
            out += self._run("\u200b")
        return out

    def _inline_runs(self, parts: list[InlineContent], base_rpr: str) -> str:
        out = []
        for part in parts:
            if not isinstance(part, Inline):
                out.append(self._run(str(part), base_rpr))
                continue
            style = part.style
            if style == "bold":
                out.append(self._run(part.text, base_rpr + "<w:b/>"))
            elif style == "italic":
                out.append(self._run(part.text, base_rpr + "<w:i/>"))
            elif style == "code":
                out.append(self._run(
                    part.text,
                    f'<w:rFonts w:ascii="{_MONO_FONT}" w:hAnsi="{_MONO_FONT}" w:cs="{_MONO_FONT}"/>'
                    + base_rpr + f'<w:sz w:val="20"/><w:shd w:val="clear" w:color="auto" w:fill="{_CODE_BG}"/>',
                ))
            elif style == "link":
                out.append(self._hyperlink(self._run(part.text, '<w:rStyle w:val="Hyperlink"/>' + base_rpr), part.href))
            elif style == "strike":
                out.append(self._run(part.text, base_rpr + "<w:strike/>"))
            elif style in ("sub", "sup"):
                align = "subscript" if style == "sub" else "superscript"
                out.append(self._run(part.text, base_rpr + f'<w:vertAlign w:val="{align}"/>'))
            elif style == "math":
                out.append(tex_to_omml(part.text))  # an editable inline equation
            elif style == "ref":
                shown = self._numbering.ref_text(part.href, part.text)
                run = self._run(shown, '<w:rStyle w:val="Hyperlink"/>' + base_rpr)
                out.append(self._hyperlink(run, anchor=self._label_marks[part.href]))
            elif style == "footnote":
                self._footnotes.append(part.text)
                out.append(
                    '<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr>'
                    f'<w:footnoteReference w:id="{len(self._footnotes)}"/></w:r>'
                )
            else:
                out.append(self._run(part.text, base_rpr))
        return "".join(out)

    def _hyperlink(self, runs: str, href: str = "", anchor: str = "") -> str:
        if anchor:
            return f'<w:hyperlink w:anchor="{anchor}" w:history="1">{runs}</w:hyperlink>'
        rid = self._rel(f"{_REL}/hyperlink", href, external=True)
        return f'<w:hyperlink r:id="{rid}" w:history="1">{runs}</w:hyperlink>'

    # -- XML helpers --------------------------------------------------------

    @staticmethod
    def _para(runs: str, style: str = "", ppr: str = "") -> str:
        style_xml = f'<w:pStyle w:val="{style}"/>' if style else ""
        props = style_xml + ppr
        return f"<w:p>{f'<w:pPr>{props}</w:pPr>' if props else ''}{runs}</w:p>"

    @staticmethod
    def _run_xml(content: str, rpr: str = "") -> str:
        return f"<w:r>{f'<w:rPr>{_order_rpr(rpr)}</w:rPr>' if rpr else ''}{content}</w:r>"

    def _run(self, text: str, rpr: str = "") -> str:
        """A text run; line breaks and tabs become ``<w:br/>`` / ``<w:tab/>``."""
        if not text:
            return ""
        pieces = []
        for i, line in enumerate(text.split("\n")):
            if i:
                pieces.append("<w:br/>")
            for j, chunk in enumerate(line.split("\t")):
                if j:
                    pieces.append("<w:tab/>")
                if chunk:
                    pieces.append(f'<w:t xml:space="preserve">{_esc(chunk)}</w:t>')
        return self._run_xml("".join(pieces), rpr)


# Run properties must appear in schema order, but are built up piecemeal.
_RPR_ORDER = ["rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "dstrike",
              "vanish", "color", "spacing", "w", "kern", "position", "sz", "szCs", "highlight", "u",
              "effect", "bdr", "shd", "fitText", "vertAlign", "rtl", "cs", "em", "lang"]
_RPR_TAG = re.compile(r"<w:(\w+)[^>]*/>")


def _order_rpr(rpr: str) -> str:
    """Sort run properties into schema order, keeping the last of duplicates."""
    found: dict[str, str] = {}
    for match in _RPR_TAG.finditer(rpr):
        found[match.group(1)] = match.group(0)
    return "".join(found[tag] for tag in _RPR_ORDER if tag in found)
