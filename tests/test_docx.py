"""Tests for the Word (.docx) renderer."""

import io
import re
import struct
import zipfile
import zlib
from xml.dom import minidom

import pytest

from reportsmith import Cell, Cover, DocxRenderer, ListElement, Report, bold, code, footnote, italic, link, math, ref
from reportsmith.renderers.docx import _order_rpr, image_size

try:
    import docx as python_docx
except ImportError:
    python_docx = None
try:
    import pygments
except ImportError:
    pygments = None

requires_python_docx = pytest.mark.skipif(python_docx is None, reason="python-docx needed")


def tiny_png(width: int = 4, height: int = 2) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    raw = b"".join(b"\x00" + b"\x00\x00\xff" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


class Package:
    """An unpacked .docx: parts by name, as text (media as bytes)."""

    def __init__(self, data: bytes):
        self.zip = zipfile.ZipFile(io.BytesIO(data))
        self.names = self.zip.namelist()

    def __getitem__(self, name: str) -> str:
        return self.zip.read(name).decode("utf-8")

    @property
    def document(self) -> str:
        return self["word/document.xml"]


def package(r: Report, **options) -> Package:
    return Package(r.to_docx(**options))


def body(build, **report_options) -> str:
    r = Report("T", date="", footer=None, **report_options)
    build(r)
    return package(r).document


class TestPackage:
    def test_parts_and_well_formed(self):
        r = Report("T", header="{title}", footer="{page}")
        r.paragraph(["x", footnote("n")])
        pkg = package(r)
        for name in ("[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/styles.xml",
                     "word/settings.xml", "word/numbering.xml", "word/footnotes.xml",
                     "word/_rels/document.xml.rels", "docProps/core.xml", "docProps/app.xml"):
            assert name in pkg.names
        for name in pkg.names:
            if name.endswith((".xml", ".rels")):
                minidom.parseString(pkg.zip.read(name))  # raises if malformed

    def test_content_types_cover_every_part(self):
        r = Report("T", header="{title}")
        r.figure(tiny_png())
        pkg = package(r)
        types = pkg["[Content_Types].xml"]
        for name in pkg.names:
            if name.startswith("word/") and name.endswith(".xml"):
                assert f'PartName="/{name}"' in types
        assert 'Extension="png"' in types

    def test_relationships_resolve(self):
        r = Report("T", header="{title}")
        r.figure(tiny_png())
        r.paragraph([link("x", "https://example.com/?a=1&b=2")])
        pkg = package(r)
        rels = pkg["word/_rels/document.xml.rels"]
        for target, mode in re.findall(r'Target="([^"]+)"( TargetMode="External")?', rels):
            if not mode:
                assert f"word/{target}" in pkg.names
        assert 'Target="https://example.com/?a=1&amp;b=2" TargetMode="External"' in rels
        for rid in re.findall(r'r:(?:id|embed)="(rId\d+)"', pkg.document):
            assert f'Id="{rid}"' in rels

    def test_deterministic(self):
        def build():
            r = Report("T", date="2026-01-01")
            r.paragraph("x")
            return r.to_docx()

        assert build() == build()

    def test_metadata(self):
        r = Report("A & B", author="Jane", description="Desc", keywords=["k1", "k2"], language="pl")
        pkg = package(r)
        core = pkg["docProps/core.xml"]
        assert "<dc:title>A &amp; B</dc:title>" in core
        assert "<dc:creator>Jane</dc:creator>" in core
        assert "<dc:subject>Desc</dc:subject>" in core
        assert "<cp:keywords>k1, k2</cp:keywords>" in core
        assert "<dc:language>pl</dc:language>" in core
        assert '<w:lang w:val="pl"/>' in pkg["word/styles.xml"]
        assert "<Application>reportsmith " in pkg["docProps/app.xml"]

    def test_save_and_extension(self, tmp_path):
        r = Report("T")
        assert r.save_docx(tmp_path / "a.docx").read_bytes()[:2] == b"PK"
        assert r.save(tmp_path / "b.DOCX").read_bytes()[:2] == b"PK"

    def test_renderer_direct(self):
        assert DocxRenderer().render(Report("T"))[:2] == b"PK"

    def test_invalid_xml_characters_dropped(self):
        doc = body(lambda r: r.paragraph("a\x00b\x0bc"))
        assert ">abc<" in doc


class TestText:
    def test_title_block(self):
        r = Report("Title", subtitle="Sub", author="Me", date="2026-11-06", footer=None)
        doc = package(r).document
        assert '<w:pStyle w:val="Title"/>' in doc and ">Title<" in doc
        assert '<w:pStyle w:val="Subtitle"/>' in doc
        assert ">Author: <" in doc and ">Me<" in doc and ">Date: <" in doc

    def test_inline_styles(self):
        doc = body(lambda r: r.paragraph([bold("b"), italic("i"), code("c")]))
        assert "<w:rPr><w:b/></w:rPr>" in doc
        assert "<w:rPr><w:i/></w:rPr>" in doc
        assert 'w:ascii="Consolas"' in doc

    def test_strike_sub_sup_math(self):
        from reportsmith import strike, sub, sup

        doc = body(lambda r: r.paragraph([strike("x"), sub("2"), sup("3"), math(r"\alpha^2")]))
        assert "<w:strike/>" in doc
        assert '<w:vertAlign w:val="subscript"/>' in doc and '<w:vertAlign w:val="superscript"/>' in doc
        assert 'w:ascii="Cambria Math"' in doc and ">α²<" in doc

    def test_breaks_tabs_and_escaping(self):
        doc = body(lambda r: r.paragraph("a <b> & c\nd\te"))
        assert "a &lt;b&gt; &amp; c</w:t><w:br/>" in doc
        assert "<w:tab/>" in doc

    def test_quote_code_rule_break(self):
        def build(r):
            r.quote("q")
            r.code("x = 1\ny = 2")
            r.horizontal_rule()
            r.page_break()

        doc = body(build)
        assert '<w:pStyle w:val="Quote"/>' in doc
        assert '<w:pStyle w:val="Code"/>' in doc and "x = 1</w:t><w:br/>" in doc
        assert '<w:bottom w:val="single" w:sz="6"' in doc
        assert '<w:br w:type="page"/>' in doc

    @pytest.mark.skipif(pygments is None, reason="pygments needed")
    def test_highlight(self):
        r = Report("T")
        r.code("def f(): return 1", language="python")
        assert "<w:color w:val=" in package(r, highlight=True).document.split("Code")[-1]

    def test_raw_skipped(self):
        assert "RAW" not in body(lambda r: r.raw("RAW", format="html"))

    def test_rpr_order(self):
        assert _order_rpr('<w:vertAlign w:val="x"/><w:b/><w:rStyle w:val="H"/><w:b/>') == (
            '<w:rStyle w:val="H"/><w:b/><w:vertAlign w:val="x"/>'
        )


class TestHeadingsAndRefs:
    def test_heading_styles_and_numbers(self):
        r = Report("T", section_numbers=True, footer=None)
        with r.section("One") as s:
            s.section("Sub").heading("Deep")
        doc = package(r).document
        assert re.search(r'<w:pStyle w:val="Heading1"/>.*?>1 <.*?>One<', doc)
        assert re.search(r'<w:pStyle w:val="Heading2"/>.*?>1\.1 <.*?>Sub<', doc)
        assert '<w:pStyle w:val="Heading3"/>' in doc

    def test_refs_link_to_bookmarks(self):
        def build(r):
            r.paragraph([ref("sec"), ref("tab"), ref("fig"), ref("eq")])
            r.section("S", label="sec")
            r.table(["a"], [["1"]], caption="C", label="tab")
            r.figure(tiny_png(), caption="F", label="fig")
            r.equation("x", label="eq")

        doc = body(build)
        anchors = re.findall(r'<w:hyperlink w:anchor="([^"]+)"', doc)
        marks = set(re.findall(r'<w:bookmarkStart w:id="\d+" w:name="([^"]+)"/>', doc))
        assert len(anchors) == 4 and set(anchors) <= marks
        assert ">Table 1<" in doc and ">Figure 1<" in doc and ">Equation 1<" in doc and ">S<" in doc

    def test_bookmark_ids_unique_and_balanced(self):
        def build(r):
            r.toc()
            r.section("A", label="a").section("B")

        doc = body(build)
        starts = re.findall(r'<w:bookmarkStart w:id="(\d+)"', doc)
        ends = re.findall(r'<w:bookmarkEnd w:id="(\d+)"', doc)
        assert len(starts) == len(set(starts)) and sorted(starts) == sorted(ends)

    def test_footnotes(self):
        pkg = package(Report("T").paragraph(["x", footnote("Note <1>"), footnote("Two")]))
        assert '<w:footnoteReference w:id="1"/>' in pkg.document
        assert '<w:footnoteReference w:id="2"/>' in pkg.document
        notes = pkg["word/footnotes.xml"]
        assert 'w:type="separator" w:id="-1"' in notes
        assert '<w:footnote w:id="1">' in notes and "Note &lt;1&gt;" in notes


class TestLists:
    def test_numbering_instances(self):
        r = Report("T", footer=None)
        r.bullet_list(["a", ListElement(["n1"], ordered=True), "b"])
        r.numbered_list(["x"])
        pkg = package(r)
        numbering = pkg["word/numbering.xml"]
        assert numbering.count("<w:abstractNum ") == 3
        assert numbering.count("<w:num ") == 3
        assert '<w:numFmt w:val="bullet"/>' in numbering and '<w:numFmt w:val="decimal"/>' in numbering
        doc = pkg.document
        assert '<w:ilvl w:val="1"/><w:numId w:val="2"/>' in doc  # nested list, one level in
        assert '<w:ilvl w:val="0"/><w:numId w:val="3"/>' in doc  # second list restarts

    def test_definition_and_task_lists(self):
        def build(r):
            r.definition_list([("Term", "Def")])
            r.task_list([(True, "done"), (False, "todo")])

        doc = body(build)
        assert "<w:b/></w:rPr><w:t xml:space=\"preserve\">Term" in doc
        assert "☑" in doc and "☐" in doc


class TestTables:
    def table_doc(self, **options) -> str:
        return body(lambda r: r.table(
            ["Name", "Value"],
            [["a", Cell("1", color="red", background="green", bold=True)], ["b", "2"]],
            caption="Data", label="t", align=["left", "right"], **options))

    def test_structure(self):
        doc = self.table_doc()
        assert "<w:tblHeader/>" in doc
        assert '<w:jc w:val="right"/>' in doc
        assert re.search(r"<w:pStyle w:val=\"Caption\"/>.*?>Table 1: <.*?>Data<", doc)

    def test_cell_styles(self):
        from reportsmith.colors import BACKGROUND_COLORS, TEXT_COLORS

        doc = self.table_doc()
        assert f'<w:color w:val="{TEXT_COLORS["red"][1:].upper()}"/>' in doc
        assert f'w:fill="{BACKGROUND_COLORS["green"][1:].upper()}"' in doc

    def test_widths_stripes_footer(self):
        doc = self.table_doc(widths=[3, 1], striped=True, footer=["Total", "3"])
        assert '<w:tblLayout w:type="fixed"/>' in doc
        cols = [int(w) for w in re.findall(r'<w:gridCol w:w="(\d+)"/>', doc)]
        assert cols[0] == pytest.approx(3 * cols[1], abs=2)
        assert 'w:fill="F8F9FB"' in doc  # second body row
        assert '<w:tcBorders><w:top w:val="single" w:sz="12"' in doc

    def test_paragraph_after_uncaptioned_table(self):
        doc = body(lambda r: r.table(["a"], [["1"]]))
        assert doc.index("</w:tbl><w:p>") > 0


class TestFigures:
    def test_embedded_image(self):
        pkg = package(Report("T").figure(tiny_png(40, 20), caption="Cap", width=0.5))
        assert "word/media/image1.png" in pkg.names
        cx, cy = map(int, re.search(r'<wp:extent cx="(\d+)" cy="(\d+)"/>', pkg.document).groups())
        assert cx == pytest.approx(2 * cy, rel=0.01)
        assert ">Figure 1: <" in pkg.document

    def test_natural_size_capped(self):
        doc = package(Report("T").figure(tiny_png(5000, 100))).document
        from reportsmith.renderers.docx import TEXT_W_EMU

        cx = int(re.search(r'<wp:extent cx="(\d+)"', doc).group(1))
        assert cx == TEXT_W_EMU

    def test_missing_and_svg_placeholders(self, tmp_path):
        r = Report("T", language="de")
        r.figure(tmp_path / "missing.png", alt="Plan")
        r.figure(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', alt="Vector")
        doc = package(r).document
        assert "[Abbildung: Plan]" in doc and "[Abbildung: Vector]" in doc
        assert "<w:drawing>" not in doc

    def test_remote_image_is_a_link(self):
        pkg = package(Report("T").image("https://example.com/a.png", alt="Remote"))
        assert "[Image: Remote]" in pkg.document
        assert 'Target="https://example.com/a.png" TargetMode="External"' in pkg["word/_rels/document.xml.rels"]

    def test_image_sizes(self):
        assert image_size(tiny_png(7, 3), "png") == (7, 3)
        gif = b"GIF89a" + struct.pack("<HH", 9, 4) + b"\x00" * 10
        assert image_size(gif, "gif") == (9, 4)
        jpeg = b"\xff\xd8" + b"\xff\xc0" + struct.pack(">HBHH", 17, 8, 30, 50) + b"\x00" * 12
        assert image_size(jpeg, "jpeg") == (50, 30)
        assert image_size(b"junk", "jpeg") is None


class TestEquations:
    def test_unicode_fallback(self, monkeypatch):
        import reportsmith.renderers.docx as docx_module

        monkeypatch.setattr(docx_module, "render_equation", lambda *a, **k: None)
        doc = package(Report("T").equation("a^2 + b^2", label="e")).document
        assert ">a² + b²<" in doc and ">(1)<" in doc

    def test_picture_when_matplotlib(self):
        pytest.importorskip("matplotlib")
        pkg = package(Report("T").equation(r"\frac{a}{b}"))
        assert "<w:drawing>" in pkg.document and "word/media/image1.png" in pkg.names
        assert ">(1)<" not in pkg.document  # unlabelled: not numbered


class TestToc:
    def test_field_and_entries(self):
        r = Report("T", footer=None)
        r.toc(depth=2)
        r.section("A").section("B").section("C")
        pkg = package(r)
        doc = pkg.document
        assert 'TOC \\o "1-2" \\h \\z \\u' in doc
        assert '<w:pStyle w:val="TOCHeading"/>' in doc and ">Contents<" in doc
        assert '<w:pStyle w:val="TOC1"/>' in doc and '<w:pStyle w:val="TOC2"/>' in doc
        assert '<w:pStyle w:val="TOC3"/>' not in doc
        assert doc.count('w:fldCharType="begin"') == doc.count('w:fldCharType="end"') == 1
        assert '<w:updateFields w:val="true"/>' in pkg["word/settings.xml"]

    def test_no_toc_no_update_prompt(self):
        assert "updateFields" not in package(Report("T"))["word/settings.xml"]

    def test_empty_toc(self):
        r = Report("T")
        r.toc()
        doc = package(r).document
        assert doc.count('w:fldCharType="begin"') == doc.count('w:fldCharType="end"') == 1


class TestCallouts:
    def test_box(self):
        def build(r):
            with r.callout("warning") as c:
                c.paragraph("p")
                c.table(["a"], [["1"]])

        doc = body(build, language="pl")
        assert '<w:left w:val="single" w:sz="24" w:space="0" w:color="B45309"/>' in doc
        assert ">Ostrzeżenie<" in doc
        # Every table cell ends with a paragraph.
        assert "</w:tbl></w:tc>" not in doc


class TestPages:
    def test_header_footer_first_page(self):
        r = Report("T", header=("{title}", "", "{date}"), footer=("", "Page {page} of {pages}", ""))
        pkg = package(r)
        sect = pkg.document[pkg.document.rindex("<w:sectPr>"):]
        assert "<w:titlePg/>" in sect
        assert sect.count("<w:headerReference") == 2 and sect.count("<w:footerReference") == 2
        assert sect.index("headerReference") < sect.index("footerReference")
        footers = [pkg[n] for n in pkg.names if n.startswith("word/footer")]
        assert any('w:instr=" PAGE "' in f and 'w:instr=" NUMPAGES "' in f for f in footers)

    def test_footer_only(self):
        pkg = package(Report("T"))
        sect = pkg.document[pkg.document.rindex("<w:sectPr>"):]
        assert "<w:titlePg/>" not in sect and "headerReference" not in sect
        assert sect.count("<w:footerReference") == 1

    def test_no_bands(self):
        pkg = package(Report("T", footer=None))
        assert not [n for n in pkg.names if n.startswith(("word/header", "word/footer"))]

    def test_cover_section(self):
        r = Report("Title", author="A", header="{title}", cover=Cover(organization="Org", note="Conf"))
        doc = package(r).document
        cover_sect = doc[:doc.index("</w:sectPr>")]
        assert '<w:vAlign w:val="center"/>' in cover_sect
        assert "headerReference" not in cover_sect and ">Org<" in cover_sect and ">Conf<" in cover_sect
        body_sect = doc[doc.rindex("<w:sectPr>"):]
        assert "<w:titlePg/>" not in body_sect and "headerReference" in body_sect

    def test_cover_logo(self):
        pkg = package(Report("T", cover=Cover(logo=tiny_png())))
        assert "word/media/image1.png" in pkg.names


class TestLabels:
    def test_polish(self):
        r = Report("T", language="pl", author="A", date="d", footer=None)
        r.toc()
        r.table(["a"], [["1"]], caption="C")
        doc = package(r).document
        assert ">Autor: <" in doc and ">Data: <" in doc and ">Spis treści<" in doc and ">Tabela 1: <" in doc


@requires_python_docx
class TestReadBack:
    def test_python_docx_reads_text(self):
        r = Report("Read back", footer=None)
        r.toc()
        with r.section("Section") as s:
            s.paragraph(["Hello ", bold("world"), footnote("n")])
            s.bullet_list(["one", "two"])
            s.table(["A", "B"], [["1", "2"]], caption="Tab")
        d = python_docx.Document(io.BytesIO(r.to_docx()))
        texts = [p.text for p in d.paragraphs]
        assert "Read back" in texts and "Section" in texts and "Hello world" in texts
        assert [p.text for p in d.paragraphs if p.style.name == "List Paragraph"] == ["one", "two"]
        assert d.tables[0].cell(1, 1).text == "2"
        assert d.core_properties.title == "Read back"
        assert d.sections[0].page_width == 11906 * 635
