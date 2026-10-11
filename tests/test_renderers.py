"""Renderer edge cases: escaping, empty content, unicode, direct renderer use."""

import pytest

from reportsmith import (
    Heading,
    HtmlRenderer,
    ListElement,
    MarkdownRenderer,
    Report,
    bold,
    code,
    link,
)
from reportsmith.elements import Element


class TestMarkdownEdgeCases:
    def test_empty_report(self):
        md = Report("Empty", author="", date="").to_markdown()
        assert md == "# Empty\n"

    def test_no_author_still_shows_date(self):
        md = Report("T", date="2026-01-01").to_markdown()
        assert "**Author:**" not in md
        assert "**Date:** 2026-01-01" in md

    def test_empty_quote_renders_marker(self):
        r = Report("T", date="")
        r.quote("")
        assert "\n>\n" in r.to_markdown().replace("> ", ">")

    def test_multiline_cell_becomes_br(self):
        r = Report("T", date="")
        r.table(["h"], [["line1\nline2"]])
        assert "line1<br>line2" in r.to_markdown()

    def test_fence_widens_repeatedly(self):
        r = Report("T", date="")
        r.code("````\nfour backticks inside")
        assert "`````\n" in r.to_markdown()

    def test_image_without_title_has_no_quotes(self):
        r = Report("T", date="")
        r.image("a.png", alt="alt")
        assert "![alt](a.png)" in r.to_markdown()

    def test_raw_both_appears(self):
        r = Report("T", date="")
        r.raw("VERBATIM")
        assert "VERBATIM" in r.to_markdown()

    def test_deep_section_nesting_headings(self):
        r = Report("T", date="")
        s = r.section("L2")
        s = s.section("L3")
        s = s.section("L4")
        md = r.to_markdown()
        assert "## L2" in md and "### L3" in md and "#### L4" in md

    def test_ordered_list_numbering_skips_nested_lists(self):
        r = Report("T", date="")
        r.numbered_list(["one", ListElement(["sub"]), "two"])
        md = r.to_markdown()
        assert "1. one" in md
        assert "2. two" in md  # nested list must not consume a number

    def test_unicode_passthrough(self):
        r = Report("Zażółć", date="")
        r.paragraph("gęślą jaźń — ünïcodé ✓")
        md = r.to_markdown()
        assert "gęślą jaźń — ünïcodé ✓" in md

    def test_unknown_element_raises(self):
        class Mystery(Element):
            pass

        r = Report("T", date="")
        r.add(Mystery())
        with pytest.raises(TypeError, match="Mystery"):
            r.to_markdown()

    def test_renderer_direct_use(self):
        r = Report("T", date="")
        assert MarkdownRenderer().render(r) == r.to_markdown()


class TestHtmlEdgeCases:
    def test_empty_report_full_document(self):
        html = Report("Empty", date="").to_html()
        assert html.startswith("<!DOCTYPE html>")
        assert html.rstrip().endswith("</html>")
        assert "<h1>Empty</h1>" in html

    def test_title_escaped_in_head_and_body(self):
        html = Report("<Tag> & Co", date="").to_html()
        assert "<title>&lt;Tag&gt; &amp; Co</title>" in html
        assert "<h1>&lt;Tag&gt; &amp; Co</h1>" in html

    def test_metadata_escaped(self):
        html = Report("T", author="A & B <esc>", subtitle="<sub>", date="").to_html()
        assert "A &amp; B &lt;esc&gt;" in html
        assert "&lt;sub&gt;" in html

    def test_no_meta_block_when_all_empty(self):
        # Check the fragment: the full document's CSS mentions .report-meta.
        html = Report("T", date="").to_html(full_document=False)
        assert "report-meta" not in html

    def test_code_block_escaped_with_language_class(self):
        r = Report("T", date="")
        r.code("<script>alert(1)</script>", language="html")
        html = r.to_html()
        assert '<code class="language-html">' in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "<script>alert(1)" not in html

    def test_raw_html_not_escaped(self):
        r = Report("T", date="")
        r.raw('<div class="custom">x</div>', format="html")
        assert '<div class="custom">x</div>' in r.to_html()

    def test_raw_markdown_only_skipped(self):
        r = Report("T", date="")
        r.raw("MD ONLY", format="markdown")
        assert "MD ONLY" not in r.to_html()

    def test_ordered_list_uses_ol(self):
        r = Report("T", date="")
        r.numbered_list(["a"])
        html = r.to_html()
        assert "<ol>" in html and "</ol>" in html

    def test_nested_list_first_item_is_list(self):
        # A nested list with no preceding sibling gets its own <li>.
        r = Report("T", date="")
        r.bullet_list([ListElement(["only child"])])
        html = r.to_html()
        assert "<li><ul>\n<li>only child</li>\n</ul>\n</li>" in html

    def test_heading_element_renders_at_level(self):
        r = Report("T", date="")
        r.add(Heading("H4", 4))
        assert "<h4>H4</h4>" in r.to_html()

    def test_image_attributes_escaped(self):
        r = Report("T", date="")
        r.image('a"b.png', alt='x"y', title='t"1')
        html = r.to_html()
        assert 'src="a&quot;b.png"' in html
        assert 'alt="x&quot;y"' in html
        assert 'title="t&quot;1"' in html

    def test_inline_spans_in_table_cells(self):
        r = Report("T", date="")
        r.table(["h"], [[[bold("b"), " ", code("c"), " ", link("l", "u")]]])
        html = r.to_html()
        assert "<strong>b</strong> <code>c</code> <a href=\"u\">l</a>" in html

    def test_unknown_element_raises(self):
        class Mystery(Element):
            pass

        r = Report("T", date="")
        r.add(Mystery())
        with pytest.raises(TypeError, match="Mystery"):
            r.to_html()

    def test_renderer_direct_use_fragment(self):
        r = Report("T", date="")
        r.paragraph("x")
        fragment = HtmlRenderer(full_document=False).render(r)
        assert fragment == r.to_html(full_document=False)
        assert "<style>" not in fragment

    def test_unicode_survives(self):
        r = Report("Zażółć", date="")
        r.paragraph("gęślą jaźń ✓")
        assert "gęślą jaźń ✓" in r.to_html()

    def test_sections_nest_heading_levels(self):
        r = Report("T", date="")
        with r.section("Top") as s:
            s.paragraph("hello")
            with s.section("Inner") as inner:
                inner.paragraph("world")
        html = r.to_html(full_document=False)
        assert "<h2>Top</h2>" in html
        assert "<h3>Inner</h3>" in html
        assert html.index("<h2>") < html.index("<p>hello</p>") < html.index("<h3>")

    def test_quote_and_hr(self):
        r = Report("T", date="")
        r.quote(["wise ", bold("words")])
        r.horizontal_rule()
        html = r.to_html()
        assert "<blockquote><p>wise <strong>words</strong></p></blockquote>" in html
        assert "<hr>" in html

    def test_italic_span(self):
        from reportsmith import italic

        r = Report("T", date="")
        r.paragraph([italic("soft")])
        assert "<em>soft</em>" in r.to_html()


class TestInlineFallback:
    def test_unknown_inline_style_renders_as_plain_text(self):
        from reportsmith.inline import Inline

        r = Report("T", date="")
        r.paragraph([Inline("sparkle", "plain & simple")])
        assert "plain & simple" in r.to_markdown()
        assert "plain &amp; simple" in r.to_html()


class TestMarkdownMetadataAndHeadings:
    def test_subtitle_rendered(self):
        md = Report("T", subtitle="A closer look", date="").to_markdown()
        assert "*A closer look*" in md

    def test_explicit_heading_element(self):
        r = Report("T", date="")
        r.heading("Deep", level=5)
        assert "##### Deep" in r.to_markdown()
