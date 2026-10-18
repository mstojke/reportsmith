"""Tests for the table of contents element across all renderers."""

import io
import re

import pytest

try:
    import fpdf
except ImportError:
    fpdf = None

from reportsmith import Report, TableOfContents, bold, link
from reportsmith.toc import Slugger, build_tree, collect_entries


def sample_report() -> Report:
    r = Report("Annual Report", date="")
    r.toc()
    with r.section("Overview") as s:
        s.paragraph("Intro.")
        with s.section(["Revenue ", bold("growth")]) as sub:
            with sub.section("By region") as deep:
                deep.section("Too deep")
    with r.section("Next steps") as s:
        s.paragraph("Plans.")
    return r


class TestElement:
    def test_builder_adds_element_and_chains(self):
        r = Report("T")
        assert r.toc(title="In this report", depth=2) is r
        el = r.children[0]
        assert isinstance(el, TableOfContents)
        assert (el.title, el.depth) == ("In this report", 2)

    def test_defaults(self):
        el = TableOfContents()
        assert (el.title, el.depth) == ("Contents", 3)

    @pytest.mark.parametrize("depth", [0, 6, -1])
    def test_invalid_depth(self, depth):
        with pytest.raises(ValueError):
            TableOfContents(depth=depth)

    def test_available_on_sections(self):
        r = Report("T")
        with r.section("A") as s:
            s.toc()
        assert isinstance(r.children[0].children[0], TableOfContents)


class TestEntries:
    def test_collects_sections_and_headings_in_order(self):
        r = Report("T")
        with r.section("A") as s:
            s.heading("A heading")
        r.section("B")
        names = [e.parts[0] for e in collect_entries(r, 3)]
        assert names == ["A", "A heading", "B"]

    def test_depth_filters(self):
        r = sample_report()
        assert len(collect_entries(r, 1)) == 2
        assert len(collect_entries(r, 3)) == 4
        assert len(collect_entries(r, 4)) == 5

    def test_level_one_heading_counts_as_top_level(self):
        r = Report("T")
        r.heading("Top", level=1)
        assert collect_entries(r, 1)[0].depth == 1

    def test_tree_nests_skipped_levels_under_nearest_parent(self):
        r = Report("T")
        r.section("A")
        r.heading("Deep", level=4)  # depth 3 directly after depth 1
        r.section("B")
        tree = build_tree(collect_entries(r, 3))
        assert [e.parts[0] for e in tree] == ["A", "B"]
        assert tree[0].children[0].parts[0] == "Deep"

    def test_tree_with_leading_deep_entry(self):
        r = Report("T")
        r.heading("Deep", level=3)
        r.section("A")
        tree = build_tree(collect_entries(r, 3))
        assert [e.parts[0] for e in tree] == ["Deep", "A"]


class TestSlugger:
    def test_github_style(self):
        s = Slugger()
        assert s.slug("Hello, World!") == "hello-world"
        assert s.slug("Q3 / Q4 results") == "q3--q4-results"
        assert s.slug("snake_case-and-dash") == "snake_case-and-dash"
        assert s.slug("Zażółć gęślą") == "zażółć-gęślą"

    def test_duplicates_get_suffixes(self):
        s = Slugger()
        assert [s.slug("A"), s.slug("A"), s.slug("A")] == ["a", "a-1", "a-2"]

    def test_suffix_collision_with_literal_heading(self):
        s = Slugger()
        assert [s.slug("A"), s.slug("A-1"), s.slug("A")] == ["a", "a-1", "a-2"]


class TestMarkdown:
    def test_nested_linked_list(self):
        md = sample_report().to_markdown()
        assert (
            "**Contents**\n\n"
            "- [Overview](#overview)\n"
            "  - [Revenue growth](#revenue-growth)\n"
            "    - [By region](#by-region)\n"
            "- [Next steps](#next-steps)\n"
        ) in md
        assert "Too deep](" not in md

    def test_toc_position_follows_document_order(self):
        md = sample_report().to_markdown()
        assert md.index("**Contents**") < md.index("## Overview")

    def test_anchor_skips_report_title_slug(self):
        r = Report("Summary", date="")
        r.toc()
        r.section("Summary")
        r.section("Summary")
        md = r.to_markdown()
        assert "[Summary](#summary-1)" in md
        assert "[Summary](#summary-2)" in md

    def test_brackets_escaped_and_markup_flattened(self):
        r = Report("T", date="")
        r.toc()
        r.section(["See ", link("[docs]", "https://x.y")])
        assert "- [See \\[docs\\]](#see-docs)" in r.to_markdown()

    def test_no_title(self):
        r = Report("T", date="")
        r.toc(title="")
        r.section("A")
        md = r.to_markdown()
        assert "**" not in md
        assert "# T\n\n- [A](#a)" in md

    def test_empty_report_renders_only_title(self):
        r = Report("T", date="")
        r.toc()
        assert r.to_markdown() == "# T\n\n**Contents**\n"


class TestHtml:
    def test_nav_with_nested_links(self):
        html = sample_report().to_html(full_document=False)
        assert '<nav class="toc" aria-label="Contents">' in html
        assert '<div class="toc-title">Contents</div>' in html
        assert '<li><a href="#overview">Overview</a>\n<ul>\n' in html
        assert '<a href="#revenue-growth">Revenue <strong>growth</strong></a>' in html
        assert "Too deep</a>" not in html

    def test_headings_get_matching_ids(self):
        html = sample_report().to_html(full_document=False)
        assert '<h2 id="overview">Overview</h2>' in html
        assert '<h3 id="revenue-growth">' in html
        assert '<h5 id="too-deep">Too deep</h5>' in html

    def test_links_in_titles_not_nested(self):
        r = Report("T", date="")
        r.toc()
        r.section(["See ", link("docs", "https://x.y")])
        html = r.to_html(full_document=False)
        assert '<a href="#see-docs">See docs</a>' in html
        assert '<h2 id="see-docs">See <a href="https://x.y">docs</a></h2>' in html

    def test_explicit_heading_ids(self):
        r = Report("T", date="")
        r.toc()
        r.heading("Loose", level=2)
        html = r.to_html(full_document=False)
        assert '<h2 id="loose">Loose</h2>' in html
        assert '<a href="#loose">Loose</a>' in html

    def test_no_ids_without_toc(self):
        r = Report("T", date="")
        r.section("A")
        assert "<h2>A</h2>" in r.to_html(full_document=False)

    def test_title_escaped(self):
        r = Report("T", date="")
        r.toc(title="<Index>")
        html = r.to_html(full_document=False)
        assert 'aria-label="&lt;Index&gt;"' in html
        assert '<div class="toc-title">&lt;Index&gt;</div>' in html

    def test_untitled_toc_keeps_accessible_label(self):
        r = Report("T", date="")
        r.toc(title="")
        r.section("A")
        html = r.to_html(full_document=False)
        assert 'aria-label="Contents"' in html
        assert "toc-title" not in html

    def test_default_css_styles_toc(self):
        assert "nav.toc" in sample_report().to_html()


class TestLatex:
    def test_tableofcontents_command(self):
        tex = sample_report().to_latex()
        assert (
            "{\\renewcommand{\\contentsname}{Contents}"
            "\\setcounter{tocdepth}{3}\\tableofcontents}"
        ) in tex
        assert tex.index("\\maketitle") < tex.index("\\tableofcontents")

    def test_title_escaped_and_depth(self):
        r = Report("T")
        r.toc(title="50% done", depth=1)
        tex = r.to_latex(full_document=False)
        assert "{50\\% done}" in tex
        assert "\\setcounter{tocdepth}{1}" in tex


@pytest.mark.skipif(fpdf is None, reason="fpdf2 not installed")
class TestPdf:
    def test_renders(self):
        out = sample_report().to_pdf()
        assert out.startswith(b"%PDF-")

    @pytest.mark.parametrize("fonts", [None, ()])
    def test_multi_page_toc(self, fonts):
        r = Report("T")
        for i in range(30):
            r.paragraph(f"filler {i}")  # TOC starts low on the first page
        r.toc(depth=2)
        for i in range(80):
            with r.section(f"Section {i} " + "very long title " * (10 if i == 3 else 0)) as s:
                s.section(f"Sub {i}")
        assert r.to_pdf(fonts=fonts).startswith(b"%PDF-")

    def test_toc_at_end_and_only_first_rendered(self):
        r = Report("T")
        r.toc()
        r.section("A")
        r.toc(title="Second")
        assert r.to_pdf().startswith(b"%PDF-")

    def test_page_numbers_point_at_headings(self):
        pypdf = pytest.importorskip("pypdf")
        r = Report("T")
        r.toc(depth=2)
        for i in range(60):
            with r.section(f"Section {i}") as s:
                s.paragraph("Body text. " * 30)
                s.section(f"Sub {i}")
        reader = pypdf.PdfReader(io.BytesIO(r.to_pdf()))
        texts = [p.extract_text() for p in reader.pages]
        rows = 0
        for text in texts:
            for line in text.splitlines():
                m = re.fullmatch(r"\s*((?:Section|Sub) \d+)\s+(\d+)\s*", line)
                if not m:
                    continue
                rows += 1
                name, page = m.group(1), int(m.group(2))
                assert name in [line_.strip() for line_ in texts[page - 1].splitlines()]
        assert rows == 120
