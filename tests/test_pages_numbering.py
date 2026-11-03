"""Tests for running headers/footers and section numbering."""

import io

import pytest

from reportsmith import Report, Section, ref
from reportsmith.numbering import Numbering
from reportsmith.page import parse_band, segments
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


def numbered() -> Report:
    r = Report("T", date="", section_numbers=True)
    r.toc()
    r.paragraph(["See ", ref("method"), " and ", ref("deep"), "."])
    with r.section("Method", label="method") as s:
        with s.section("Data") as d:
            with d.section("Sources") as src:
                src.section("Very deep", label="deep")  # depth 4: beyond default depth 3
        s.callout().heading("In a callout")
    r.section("Results")
    r.heading("Loose")
    return r


class TestTemplates:
    def test_string_is_centred(self):
        assert parse_band("Page {page}", "footer") == ("", "Page {page}", "")

    def test_tuple(self):
        assert parse_band(("{title}", "", "{date}"), "header") == ("{title}", "", "{date}")

    def test_none_and_empty(self):
        assert parse_band(None, "header") is None
        assert parse_band("", "header") is None
        assert parse_band(("", "", ""), "header") is None

    @pytest.mark.parametrize(
        "value, match",
        [("{nope}", "Unknown placeholder"), ("{page:03}", "format"), ("{page!r}", "format"),
         ("{", "Invalid"), (("a", "b"), "tuple"), (("a", "b", 3), "tuple")],
    )
    def test_invalid(self, value, match):
        with pytest.raises(ValueError, match=match):
            parse_band(value, "footer")

    def test_segments(self):
        r = Report("Title", author="Ann", subtitle="Sub", date="2026-11-03")
        assert segments("{title} by {author} ({subtitle}, {date}) {page}/{pages} {{x}}", r) == [
            ("text", "Title by Ann (Sub, 2026-11-03) "), ("page", ""), ("text", "/"),
            ("pages", ""), ("text", " {x}"),
        ]


class TestReportOptions:
    def test_defaults(self):
        r = Report("T")
        assert (r.header, r.footer, r.section_numbers) == (None, ("", "{page}", ""), 0)

    def test_options(self):
        r = Report("T", header="{title}", footer=None, section_numbers=2)
        assert (r.header, r.footer, r.section_numbers) == (("", "{title}", ""), None, 2)
        assert Report("T", section_numbers=True).section_numbers == 3

    @pytest.mark.parametrize("value", [-1, 6])
    def test_invalid_depth(self, value):
        with pytest.raises(ValueError, match="section_numbers"):
            Report("T", section_numbers=value)

    def test_invalid_template_fails_at_construction(self):
        with pytest.raises(ValueError, match="footer"):
            Report("T", footer="{pgae}")


class TestNumbering:
    def test_numbers(self):
        r = numbered()
        n = Numbering(r)
        method, results, loose = r.children[2], r.children[3], r.children[4]
        data = method.children[0]
        sources = data.children[0]
        deep = sources.children[0]
        callout_heading = method.children[1].children[0]
        assert [n.section_number(x) for x in (method, data, sources, deep, results, loose)] == [
            "1", "1.1", "1.1.1", "", "2", "3"
        ]
        assert n.section_number(callout_heading) == ""

    def test_depth(self):
        r = numbered()
        r.section_numbers = 1
        n = Numbering(r)
        assert n.section_number(r.children[2]) == "1"
        assert n.section_number(r.children[2].children[0]) == ""

    def test_skipped_level_matches_latex(self):
        r = Report("T", section_numbers=True)
        r.section("A")
        r.heading("Skips a level", level=4)  # depth 3 right after depth 1
        assert Numbering(r).section_number(r.children[1]) == "1.0.1"

    def test_off_by_default(self):
        r = Report("T")
        r.section("A")
        assert not Numbering(r).sections_numbered

    def test_section_refs(self):
        n = Numbering(numbered())
        assert n.ref_text("method") == "Section 1"
        assert n.ref_text("deep") == "Very deep"  # unnumbered: falls back to the title
        assert n.ref_text("method", "the method") == "the method"

    def test_section_ref_without_numbering(self):
        r = Report("T")
        r.section(["The ", "intro"], label="intro")
        assert Numbering(r).ref_text("intro") == "The intro"

    def test_labels_shared_with_figures_and_tables(self):
        r = Report("T")
        r.section("A", label="x")
        r.table(["A"], [["1"]], caption="C", label="x")
        with pytest.raises(ValueError, match="Duplicate label 'x'"):
            r.to_markdown()

    def test_invalid_section_label(self):
        with pytest.raises(ValueError, match="Invalid label"):
            Report("T").section("A", label="has space")
        with pytest.raises(ValueError):
            Section("A", label="-x")

    def test_extend_prefixes_section_labels(self):
        src = Report("S")
        src.paragraph([ref("intro")])
        src.section("Intro", label="intro")
        r = Report("T", date="", section_numbers=True)
        with r.section("Merged") as m:
            m.extend(src, label_prefix="s-")
        assert r.children[0].children[1].label == "s-intro"
        assert "Section 1.1" in r.to_markdown()


class TestMarkdown:
    def test_headings_and_toc(self):
        md = numbered().to_markdown()
        assert "## 1 Method" in md and "### 1.1 Data" in md and "#### 1.1.1 Sources" in md
        assert "##### Very deep" in md  # beyond the numbering depth
        assert "- [1 Method](#1-method)" in md
        assert "  - [1.1 Data](#11-data)" in md
        assert "- [3 Loose](#3-loose)" in md
        assert "See Section 1 and Very deep." in md
        assert "> ### In a callout" in md

    def test_unnumbered_unchanged(self):
        r = Report("T", date="")
        r.toc()
        r.section("Method")
        assert "## Method" in r.to_markdown() and "[Method](#method)" in r.to_markdown()


class TestHtml:
    def test_headings_ids_and_refs(self):
        html = numbered().to_html(full_document=False)
        assert '<h2 id="sec-method"><span class="section-number">1</span> Method</h2>' in html
        assert '<h3 id="11-data"><span class="section-number">1.1</span> Data</h3>' in html
        assert '<a href="#sec-method"><span class="section-number">1</span> Method</a>' in html
        assert '<a href="#sec-method" class="ref">Section 1</a>' in html
        assert '<a href="#sec-deep" class="ref">Very deep</a>' in html
        assert "<h3>In a callout</h3>" in html

    def test_labelled_section_gets_id_without_toc(self):
        r = Report("T", date="")
        r.section("Intro", label="intro")
        r.section("Other")
        html = r.to_html(full_document=False)
        assert '<h2 id="sec-intro">Intro</h2>' in html and "<h2>Other</h2>" in html

    def test_default_footer_page_rule(self):
        css = page_css(Report("T"))
        assert "@page {\n  margin: 20mm 18mm;\n  @bottom-center { content: counter(page);" in css
        assert "@page :first" not in css

    def test_header_hidden_on_first_page(self):
        css = page_css(Report("T", header=("{title}", "", "Page {page} of {pages}"), footer=None))
        assert '@top-left { content: "T";' in css
        assert '@top-right { content: "Page " counter(page) " of " counter(pages);' in css
        assert "@bottom" not in css
        assert "@page :first {\n  @top-left { content: none; }" in css

    def test_no_bands_no_page_rules(self):
        r = Report("T", footer=None)
        assert page_css(r) == "" and "@page" not in r.to_html()

    def test_css_string_escaping(self):
        css = page_css(Report('Say "hi" \\ </style><script>', footer="{title}"))
        assert 'content: "Say \\"hi\\" \\\\ \\3C /style>\\3C script>";' in css
        assert "</style>" not in css

    def test_in_document_not_fragment(self):
        r = Report("T")
        assert "@page" in r.to_html()
        assert "@page" not in r.to_html(full_document=False)
        assert "@page" in r.to_html(css="body{}")  # report setting, kept with custom CSS


class TestLatex:
    def test_numbering_depth_and_labels(self):
        tex = numbered().to_latex()
        assert "\\setcounter{secnumdepth}{3}" in tex
        assert "\\section{Method}\\label{sec:method}" in tex
        assert "\\paragraph{Very deep}\\label{sec:deep}" in tex
        assert "\\hyperref[sec:method]{Section~\\ref*{sec:method}}" in tex
        assert "\\subsection*{In a callout}" in tex

    def test_unnumbered_refs_use_title(self):
        r = Report("T", date="")
        r.section("Intro", label="intro")
        r.paragraph([ref("intro")])
        tex = r.to_latex()
        assert "\\setcounter{secnumdepth}{0}" in tex
        assert "\\hyperref[sec:intro]{Intro}" in tex
        assert "\\hyperref[sec:intro]{Section~\\ref*{sec:intro}}" in r.to_latex(numbered=True)

    def test_section_numbers_overrides_numbered(self):
        r = Report("T", section_numbers=2)
        assert "\\setcounter{secnumdepth}{2}" in r.to_latex(numbered=True)

    def test_page_style(self):
        tex = Report("A & B", header=("{title}", "", ""), footer="Page {page} of {pages}").to_latex()
        assert "\\usepackage{fancyhdr}\n\\usepackage{lastpage}\n" in tex
        assert "\\fancyhead[L]{\\small\\color{black!60}A \\& B}" in tex
        assert "\\fancyfoot[C]{\\small\\color{black!60}Page \\thepage of \\pageref*{LastPage}}" in tex
        plain = tex[tex.index("\\fancypagestyle{plain}"):].splitlines()[0]
        assert "fancyfoot[C]" in plain and "fancyhead" not in plain

    def test_no_bands(self):
        tex = Report("T", footer=None).to_latex()
        assert "\\fancyhf{}\n\\pagestyle{fancy}" in tex
        assert "\\fancyfoot" not in tex and "\\fancyhead" not in tex

    def test_fragment_has_no_page_style(self):
        assert "fancyhdr" not in Report("T").to_latex(full_document=False)


@requires_pdf
class TestPdf:
    def long_report(self, **kwargs) -> Report:
        r = Report("Long", date="2026-11-03", **kwargs)
        r.paragraph(["See ", ref("p2"), "."])
        for i in range(1, 4):
            with r.section(f"Part {i}", label=f"p{i}") as s:
                for j in range(25):
                    s.paragraph(f"Paragraph {j} with enough words to fill a line of text.")
        return r

    def pages(self, r: Report, fonts=()):
        reader = pypdf.PdfReader(io.BytesIO(r.to_pdf(fonts=fonts)))
        return reader, [p.extract_text() for p in reader.pages]

    def test_default_page_numbers(self):
        _, pages = self.pages(self.long_report())
        assert len(pages) >= 3
        for i, text in enumerate(pages, start=1):
            assert text.rstrip().endswith(str(i))

    @pytest.mark.parametrize("fonts", [None, ()])
    def test_header_and_page_of_pages(self, fonts):
        r = self.long_report(header=("{title}", "", "{date}"), footer=("", "Page {page} of {pages}", ""))
        _, pages = self.pages(r, fonts)
        n = len(pages)
        for i, text in enumerate(pages, start=1):
            assert f"Page {i} of {n}" in text
        assert not pages[0].startswith("Long 2026-11-03")  # no header on page 1
        assert pages[1].startswith("Long 2026-11-03")

    def test_no_footer(self):
        _, pages = self.pages(self.long_report(footer=None))
        assert not pages[0].rstrip().endswith("1")

    def test_numbered_headings_bookmarks_and_refs(self):
        r = self.long_report(section_numbers=True)
        reader, pages = self.pages(r)
        assert "1 Part 1" in pages[0] and "See Section 2." in pages[0]
        assert [o.title for o in reader.outline] == ["1 Part 1", "2 Part 2", "3 Part 3"]
        links = [a.get_object() for a in reader.pages[0].get("/Annots", [])]
        assert any(link.get("/Subtype") == "/Link" and "/Dest" in link for link in links)

    def test_toc_numbered_and_placed(self):
        r = self.long_report(section_numbers=True, footer="Page {page} of {pages}")
        r.children.insert(0, __import__("reportsmith").TableOfContents())
        _, pages = self.pages(r)
        first = pages[0]
        assert "Contents" in first and "1 Part 1" in first and "Page 1 of" in first
