"""Tests for reportsmith.elements — construction, validation, builder API."""

import pytest

from reportsmith import (
    CodeBlock,
    Heading,
    HorizontalRule,
    Image,
    ListElement,
    Paragraph,
    Quote,
    Raw,
    Report,
    Section,
    Table,
    bold,
)


class TestHeading:
    def test_valid_levels(self):
        for level in range(1, 7):
            assert Heading("t", level).level == level

    @pytest.mark.parametrize("level", [0, 7, -1])
    def test_invalid_levels_rejected(self, level):
        with pytest.raises(ValueError, match="1-6"):
            Heading("t", level)

    def test_content_normalized(self):
        h = Heading(["a", bold("b")])
        assert h.parts == ["a", bold("b")]


class TestTable:
    def test_row_width_validated(self):
        with pytest.raises(ValueError, match="Row 1 has 3 cells, expected 2"):
            Table(["a", "b"], [["1", "2"], ["1", "2", "3"]])

    def test_align_length_validated(self):
        with pytest.raises(ValueError, match="one entry per column"):
            Table(["a", "b"], [], align=["left"])

    def test_align_values_validated(self):
        with pytest.raises(ValueError, match="Invalid alignment: 'top'"):
            Table(["a"], [], align=["top"])

    def test_align_defaults_to_left(self):
        assert Table(["a", "b"], []).align == ["left", "left"]

    def test_empty_rows_allowed(self):
        assert Table(["a"], []).rows == []

    def test_cells_normalized(self):
        t = Table(["h"], [[bold("cell")]])
        assert t.rows[0][0] == [bold("cell")]


class TestListElement:
    def test_flat_items_normalized(self):
        el = ListElement(["a", ["b", bold("c")]])
        assert el.items == [["a"], ["b", bold("c")]]

    def test_nested_list_kept_as_is(self):
        inner = ListElement(["x"])
        outer = ListElement(["a", inner])
        assert outer.items[1] is inner

    def test_ordered_flag(self):
        assert ListElement([], ordered=True).ordered
        assert not ListElement([]).ordered


class TestRaw:
    @pytest.mark.parametrize("fmt", ["markdown", "html", "both"])
    def test_valid_formats(self, fmt):
        assert Raw("x", fmt).format == fmt

    def test_invalid_format_rejected(self):
        with pytest.raises(ValueError, match="'markdown', 'html' or 'both'"):
            Raw("x", "pdf")


class TestBuilderApi:
    def test_methods_chain(self):
        r = Report("T")
        result = (
            r.paragraph("p")
            .heading("h", level=2)
            .quote("q")
            .code("c")
            .bullet_list(["i"])
            .numbered_list(["i"])
            .table(["h"], [["c"]])
            .image("img.png")
            .horizontal_rule()
            .raw("raw")
        )
        assert result is r
        assert len(r.children) == 10

    def test_children_have_expected_types(self):
        r = Report("T")
        r.paragraph("p").quote("q").code("c").image("i.png").horizontal_rule()
        types = [type(c) for c in r.children]
        assert types == [Paragraph, Quote, CodeBlock, Image, HorizontalRule]

    def test_add_appends_prebuilt_element(self):
        r = Report("T")
        el = Paragraph("x")
        r.add(el)
        assert r.children == [el]

    def test_section_returns_new_section(self):
        r = Report("T")
        s = r.section("S")
        assert isinstance(s, Section)
        assert r.children == [s]

    def test_section_context_manager_is_passthrough(self):
        r = Report("T")
        with r.section("S") as s:
            s.paragraph("inside")
        assert s.children[0].parts == ["inside"]

    def test_heading_level_defaults_to_container_depth(self):
        r = Report("T")
        r.heading("top")  # report is level 1 -> heading level 2
        s = r.section("S")  # level 2
        s.heading("inner")  # -> level 3
        assert r.children[0].level == 2
        assert s.children[0].level == 3


class TestSectionNesting:
    def test_levels_increase_with_depth(self):
        r = Report("T")
        s1 = r.section("a")
        s2 = s1.section("b")
        s3 = s2.section("c")
        assert (s1._level, s2._level, s3._level) == (2, 3, 4)

    def test_level_capped_at_six(self):
        r = Report("T")
        s = r
        for name in "abcdefgh":
            s = s.section(name)
        assert s._level == 6
