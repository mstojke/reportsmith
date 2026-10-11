"""Tests for the PDF renderer (skipped entirely if fpdf2 is not installed)."""

import sys

import pytest

pytest.importorskip("fpdf")

from reportsmith import ListElement, PdfRenderer, Report, bold, code, italic, link
from reportsmith.elements import Element


def full_report() -> Report:
    r = Report("PDF Test", author="Alice", subtitle="All elements", date="2026-08-26")
    with r.section("Section") as s:
        s.paragraph(["Plain, ", bold("bold"), ", ", italic("italic"), ", ", code("mono"), ", ", link("a link", "https://example.com"), "."])
        s.quote("A wise quote.")
        s.code("print('hello')\nprint('world')", language="python")
        s.bullet_list(["one", ListElement(["nested"], ordered=True), "two"])
        s.table(["A", "B"], [["1", "2"], ["3", "4"]], caption="Cap", align=["left", "right"])
        s.image("does-not-exist.png", alt="missing chart")
        s.horizontal_rule()
        s.raw("IGNORED IN PDF", format="both")
        with s.section("Nested") as inner:
            inner.paragraph("Deep content.")
    r.heading("Standalone heading", level=3)
    return r


class TestPdfOutput:
    def test_returns_pdf_bytes(self):
        out = full_report().to_pdf()
        assert isinstance(out, bytes)
        assert out.startswith(b"%PDF-")
        assert len(out) > 1000

    def test_save_pdf_roundtrip(self, tmp_path):
        path = full_report().save_pdf(tmp_path / "r.pdf")
        assert path.read_bytes().startswith(b"%PDF-")

    def test_renderer_direct_use(self):
        assert PdfRenderer().render(full_report()).startswith(b"%PDF-")

    def test_long_content_paginates(self):
        r = Report("Long", date="")
        for i in range(120):
            r.paragraph(f"Paragraph number {i} with some filler text to occupy space.")
        out = r.to_pdf()
        # Multiple /Page objects => more than one page.
        assert out.count(b"/Type /Page") > 2

    def test_empty_report(self):
        assert Report("Only Title", author="", date="").to_pdf().startswith(b"%PDF-")

    def test_unicode_text_does_not_crash(self):
        r = Report("Zażółć gęślą jaźń", date="")
        r.paragraph("Unicode: ünïcodé — ✓ — zażółć")
        assert r.to_pdf().startswith(b"%PDF-")

    def test_core_font_fallback(self):
        # fonts=() disables auto-detection and forces Latin-1 core fonts;
        # non-Latin-1 text must degrade instead of crashing.
        r = Report("Fallback", date="")
        r.paragraph("Unicode: zażółć ✓")
        r.bullet_list(["item"])
        r.code("x = 1")
        renderer = PdfRenderer(fonts=(), mono_fonts=())
        out = renderer.render(r)
        assert out.startswith(b"%PDF-")
        assert renderer.unicode is False
        assert renderer.body_family == "helvetica"
        assert renderer.mono_family == "courier"

    def test_unknown_element_raises(self):
        class Mystery(Element):
            pass

        r = Report("T", date="")
        r.add(Mystery())
        with pytest.raises(TypeError, match="Mystery"):
            r.to_pdf()


class TestPdfMetadataAndStructure:
    def test_document_metadata_embedded(self):
        out = Report("MetaTitle", author="MetaAuthor", date="").to_pdf()
        assert b"MetaTitle" in out
        assert b"MetaAuthor" in out

    def test_sections_create_outline(self):
        out = full_report().to_pdf()
        assert b"/Outlines" in out

    def test_existing_image_embedded(self, tmp_path):
        png = tmp_path / "dot.png"
        # Minimal valid 1x1 red PNG.
        png.write_bytes(bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
            "53de0000000c4944415408d763f8cfc0000000030001879261880000000049"
            "454e44ae426082"
        ))
        r = Report("Img", date="")
        r.image(str(png), alt="dot", title="A dot")
        out = r.to_pdf()
        assert b"/Image" in out


class TestMissingDependency:
    def test_helpful_error_without_fpdf2(self, monkeypatch):
        for mod in list(sys.modules):
            if mod == "fpdf" or mod.startswith("fpdf."):
                monkeypatch.delitem(sys.modules, mod)
        monkeypatch.setitem(sys.modules, "fpdf", None)  # forces ImportError
        with pytest.raises(ImportError, match=r"pip install reportsmith\[pdf\]"):
            Report("T", date="").to_pdf()
