"""Tests for the cover page."""

import io
import struct
import zlib
from pathlib import Path

import pytest

from reportsmith import Cover, Report
from reportsmith.renderers.html import page_css

try:
    import fpdf
except ImportError:
    fpdf = None
try:
    import pypdf
except ImportError:
    pypdf = None

requires_pdf = pytest.mark.skipif(fpdf is None or pypdf is None, reason="fpdf2 and pypdf needed")


def tiny_png(width: int = 4, height: int = 2) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    raw = b"".join(b"\x00" + b"\x1d\x4e\xd8" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def covered(**cover) -> Report:
    r = Report(
        "Annual & Review",
        subtitle="Year two",
        author="Ops Team",
        date="2026-11-05",
        cover=Cover(**cover) if cover else True,
    )
    with r.section("Intro") as s:
        s.paragraph("Body text.")
    return r


class TestCoverObject:
    def test_defaults(self):
        c = Cover()
        assert c.logo is None and c.organization == "" and c.note == ""

    def test_true_false_none(self):
        assert isinstance(Report("T", cover=True).cover, Cover)
        assert Report("T", cover=False).cover is None
        assert Report("T", cover=None).cover is None
        assert Report("T").cover is None

    def test_settable_after_construction(self):
        r = Report("T")
        r.cover = True
        assert isinstance(r.cover, Cover)
        r.cover = None
        assert r.cover is None

    def test_rejects_other_types(self):
        with pytest.raises(TypeError, match="cover must be"):
            Report("T", cover="yes")  # type: ignore[arg-type]

    @pytest.mark.parametrize("width", [0, -0.1, 1.5])
    def test_logo_width_range(self, width):
        with pytest.raises(ValueError, match="logo_width"):
            Cover(logo_width=width)

    def test_logo_is_a_figure(self):
        c = Cover(logo=tiny_png(), organization="Acme", logo_width=0.5)
        assert c.logo is not None
        assert c.logo.kind == "bytes" and c.logo.format == "png"
        assert c.logo.width == 0.5 and c.logo.alt == "Acme logo"
        assert Cover(logo="logo.png").logo.alt == "Logo"

    def test_bad_logo_source(self):
        with pytest.raises(TypeError):
            Cover(logo=42)

    def test_extend_does_not_copy_cover(self):
        r = Report("T")
        r.extend(covered())
        assert r.cover is None


class TestMarkdown:
    def test_plain_cover(self):
        md = covered().to_markdown()
        assert md.startswith("# Annual & Review\n\n*Year two*  \n**Author:** Ops Team  \n")
        assert '**Date:** 2026-11-05  \n\n<div style="break-after: page"></div>\n\n## Intro' in md

    def test_full_cover(self):
        md = covered(logo="img/logo.png", organization="Acme", note="Confidential").to_markdown()
        assert md.startswith("![Acme logo](img/logo.png)\n\n**Acme**\n\n# Annual & Review\n\n")
        assert "\n\n*Confidential*\n\n<div" in md

    def test_logo_bytes_embedded_or_saved(self, tmp_path):
        r = covered(logo=tiny_png())
        assert "![Logo](data:image/png;base64," in r.to_markdown()
        r.save_markdown(tmp_path / "r.md")
        assert "![Logo](r_files/" in (tmp_path / "r.md").read_text(encoding="utf-8")
        assert len(list((tmp_path / "r_files").iterdir())) == 1

    def test_no_cover_unchanged(self):
        md = Report("T", date="d").to_markdown()
        assert md == "# T\n\n**Date:** d  \n"


class TestHtml:
    def test_cover_replaces_title_block(self):
        html = covered(organization="Acme", note="Internal").to_html()
        assert '<header class="cover">' in html
        assert "<h1>Annual &amp; Review</h1>" in html
        assert '<div class="cover-subtitle">Year two</div>' in html
        assert '<div class="cover-meta">Ops Team<br>\n2026-11-05</div>' in html
        assert '<div class="cover-org">Acme</div>' in html
        assert '<div class="cover-note">Internal</div>' in html
        assert 'class="report-meta"' not in html
        assert html.count("<h1>") == 1

    def test_logo(self):
        html = covered(logo=tiny_png(), logo_width=0.25).to_html()
        assert '<img class="cover-logo" src="data:image/png;base64,' in html
        assert 'alt="Logo" style="width:25%">' in html
        html = covered(logo=Path("img") / "logo.png").to_html()
        assert '<img class="cover-logo" src="img/logo.png"' in html

    def test_escaping(self):
        html = covered(organization="<A&B>", note='"x"').to_html()
        assert "&lt;A&amp;B&gt;" in html and "&quot;x&quot;" in html

    def test_print_css(self):
        css = Report("T").to_html()
        assert ".cover { height: 100vh;" in css and "break-after: page" in css

    def test_first_page_has_no_bands(self):
        css = page_css(Report("T", header="{title}", cover=True))
        first = css[css.index("@page :first"):]
        for edge in ("top", "bottom"):
            for position in ("left", "center", "right"):
                assert f"@{edge}-{position} {{ content: none; }}" in first

    def test_without_cover_footer_stays_on_first_page(self):
        css = page_css(Report("T", header="{title}"))
        assert "@bottom-center { content: none; }" not in css

    def test_no_bands_no_page_rules(self):
        assert page_css(Report("T", footer=None, cover=True)) == ""


class TestLatex:
    def test_titlepage(self):
        tex = covered(organization="Acme", note="Confidential").to_latex()
        assert "\\maketitle" not in tex
        body = tex[tex.index("\\begin{document}"):]
        assert body.startswith("\\begin{document}\n\\begin{titlepage}\n\\centering\n")
        assert "{\\large\\bfseries Acme\\par}" in body
        assert "{\\Huge\\bfseries Annual \\& Review\\par}" in body
        assert "{\\Large\\color{black!60}Year two\\par}" in body
        assert "{\\large Ops Team\\\\[0.5em]\n2026-11-05\\par}" in body
        assert "{\\small\\color{black!60}Confidential\\par}" in body
        assert "\\end{titlepage}\n\\setcounter{page}{2}\n\n\\section{Intro}" in body

    def test_plain_cover_has_no_rule_without_author_or_date(self):
        tex = Report("T", date="", cover=True).to_latex()
        assert "\\rule{3cm}" not in tex and "\\begin{titlepage}" in tex

    def test_logo_from_path(self):
        tex = covered(logo="img/logo.png", logo_width=0.4).to_latex()
        assert "\\includegraphics[width=0.4\\linewidth]{img/logo.png}\\par" in tex

    def test_logo_bytes_need_assets(self, tmp_path):
        r = covered(logo=tiny_png())
        with pytest.raises(ValueError, match="logo.*save_latex"):
            r.to_latex()
        r.save_latex(tmp_path / "r.tex")
        assert "{r_files/" in (tmp_path / "r.tex").read_text(encoding="utf-8")

    def test_svg_logo_rejected(self, tmp_path):
        r = covered(logo=b'<svg xmlns="http://www.w3.org/2000/svg"></svg>')
        with pytest.raises(ValueError, match="SVG logo"):
            r.to_latex(assets_dir=tmp_path)

    def test_fragment_has_no_cover(self):
        tex = covered().to_latex(full_document=False)
        assert "titlepage" not in tex and tex.startswith("\\section{Intro}")


@requires_pdf
class TestPdf:
    def pages(self, r: Report, fonts=None) -> list[str]:
        reader = pypdf.PdfReader(io.BytesIO(r.to_pdf(fonts=fonts)))
        return [p.extract_text() for p in reader.pages]

    @pytest.mark.parametrize("fonts", [None, ()])
    def test_cover_is_its_own_page(self, fonts):
        r = covered(organization="Acme", note="Confidential")
        r.header = ("{title}", "", "")
        r.footer = ("", "Page {page} of {pages}", "")
        pages = self.pages(r, fonts)
        assert len(pages) == 2
        cover, body = pages
        for text in ("Acme", "Annual & Review", "Year two", "Ops Team", "2026-11-05", "Confidential"):
            assert text in cover
        assert "Page" not in cover and "Intro" not in cover  # no header or footer
        assert body.startswith("Annual & Review")  # header from page 2 on
        assert "Page 2 of 2" in body and "Intro" in body

    def test_logo(self, tmp_path):
        png = tmp_path / "logo.png"
        png.write_bytes(tiny_png(40, 20))
        for logo in (png, tiny_png()):
            data = covered(logo=logo).to_pdf()
            reader = pypdf.PdfReader(io.BytesIO(data))
            assert len(reader.pages[0].images) == 1

    def test_missing_logo_placeholder(self, tmp_path):
        pages = self.pages(covered(logo=tmp_path / "missing.png"))
        assert "[Logo:" in pages[0] and len(pages) == 2

    def test_toc_after_cover(self):
        r = Report("T", date="", cover=True)
        r.toc()
        r.section("Intro").paragraph("Body text.")
        pages = self.pages(r)
        assert "Contents" not in pages[0]
        assert "Contents" in pages[1] and "Intro" in pages[1]
