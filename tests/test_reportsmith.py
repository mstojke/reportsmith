import datetime

import pytest

from reportsmith import ListElement, Report, Table, bold, code, italic, link


def make_report() -> Report:
    return Report("Test Report", author="Alice", date="2026-08-26")


class TestMarkdown:
    def test_title_and_metadata(self):
        md = make_report().to_markdown()
        assert md.startswith("# Test Report")
        assert "**Author:** Alice" in md
        assert "**Date:** 2026-08-26" in md

    def test_sections_nest_heading_levels(self):
        r = make_report()
        with r.section("Top") as s:
            s.paragraph("hello")
            with s.section("Inner") as inner:
                inner.paragraph("world")
        md = r.to_markdown()
        assert "## Top" in md
        assert "### Inner" in md
        assert md.index("## Top") < md.index("hello") < md.index("### Inner")

    def test_inline_formatting(self):
        r = make_report()
        r.paragraph(["a ", bold("b"), " ", italic("c"), " ", code("d"), " ", link("e", "https://x.io")])
        md = r.to_markdown()
        assert "a **b** *c* `d` [e](https://x.io)" in md

    def test_table_with_alignment_and_escaping(self):
        r = make_report()
        r.table(
            ["Name", "Value"],
            [["pipe|here", "1"], ["b", "2"]],
            caption="My caption",
            align=["left", "right"],
        )
        md = r.to_markdown()
        assert "| Name | Value |" in md
        assert "| :--- | ---: |" in md
        assert "pipe\\|here" in md
        assert "*My caption*" in md

    def test_lists(self):
        r = make_report()
        r.bullet_list(["one", "two", ListElement(["nested"], ordered=True)])
        r.numbered_list(["first", "second"])
        md = r.to_markdown()
        assert "- one\n- two\n  1. nested" in md
        assert "1. first\n2. second" in md

    def test_code_block_fence_widens(self):
        r = make_report()
        r.code("print('x')\n```\nnot a fence", language="python")
        md = r.to_markdown()
        assert "````python" in md

    def test_quote_image_hr_raw(self):
        r = make_report()
        r.quote("wise words\nsecond line")
        r.image("img.png", alt="alt text", title="the title")
        r.horizontal_rule()
        r.raw("MD ONLY", format="markdown")
        r.raw("<div>HTML ONLY</div>", format="html")
        md = r.to_markdown()
        assert "> wise words\n> second line" in md
        assert '![alt text](img.png "the title")' in md
        assert "\n---\n" in md
        assert "MD ONLY" in md
        assert "HTML ONLY" not in md


class TestHtml:
    def test_full_document(self):
        html = make_report().to_html()
        assert html.startswith("<!DOCTYPE html>")
        assert "<title>Test Report</title>" in html
        assert "<style>" in html
        assert "<h1>Test Report</h1>" in html

    def test_fragment(self):
        html = make_report().to_html(full_document=False)
        assert "<!DOCTYPE html>" not in html
        assert "<h1>Test Report</h1>" in html

    def test_escaping(self):
        r = make_report()
        r.paragraph("5 < 6 & \"quotes\" <script>")
        html = r.to_html()
        assert "5 &lt; 6 &amp;" in html
        assert "<script>" not in html

    def test_inline_and_link_escaping(self):
        r = make_report()
        r.paragraph([bold("b<i>"), link("click", 'https://x.io/?a=1&b="2"')])
        html = r.to_html()
        assert "<strong>b&lt;i&gt;</strong>" in html
        assert 'href="https://x.io/?a=1&amp;b=&quot;2&quot;"' in html

    def test_table(self):
        r = make_report()
        r.table(["H1", "H2"], [["a", "b"]], caption="Cap", align=["center", "right"])
        html = r.to_html()
        assert '<th style="text-align:center">H1</th>' in html
        assert '<td style="text-align:right">b</td>' in html
        assert "<caption>Cap</caption>" in html

    def test_nested_list_markup(self):
        r = make_report()
        r.bullet_list(["parent", ListElement(["child"], ordered=False)])
        html = r.to_html()
        assert "<li>parent\n<ul>\n<li>child</li>\n</ul>\n</li>" in html

    def test_custom_css(self):
        html = make_report().to_html(css="body { color: red; }")
        assert "body { color: red; }" in html
        assert "--accent" not in html


class TestValidation:
    def test_table_row_width_mismatch(self):
        with pytest.raises(ValueError, match="expected 2"):
            Table(["a", "b"], [["only one"]])

    def test_bad_alignment(self):
        with pytest.raises(ValueError, match="Invalid alignment"):
            Table(["a"], [], align=["middle"])

    def test_bad_heading_level(self):
        r = make_report()
        with pytest.raises(ValueError, match="1-6"):
            r.heading("x", level=7)

    def test_bad_raw_format(self):
        r = make_report()
        with pytest.raises(ValueError, match="markdown"):
            r.raw("x", format="rtf")


class TestReportMeta:
    def test_date_from_date_object(self):
        r = Report("T", date=datetime.date(2026, 1, 2))
        assert r.date == "2026-01-02"

    def test_date_defaults_to_today(self):
        assert Report("T").date == datetime.date.today().isoformat()

    def test_save_roundtrip(self, tmp_path):
        r = make_report()
        r.paragraph("body")
        md_path = r.save_markdown(tmp_path / "r.md")
        html_path = r.save_html(tmp_path / "r.html")
        assert "body" in md_path.read_text(encoding="utf-8")
        assert "<p>body</p>" in html_path.read_text(encoding="utf-8")
