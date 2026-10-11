"""Tests for reportsmith.inline — span helpers and input normalization."""

import pytest

from reportsmith.inline import Inline, bold, code, italic, link, normalize


class TestHelpers:
    def test_bold(self):
        span = bold("x")
        assert span == Inline("bold", "x")

    def test_italic(self):
        assert italic("x") == Inline("italic", "x")

    def test_code(self):
        assert code("x") == Inline("code", "x")

    def test_link_carries_href(self):
        span = link("text", "https://example.com")
        assert span.style == "link"
        assert span.text == "text"
        assert span.href == "https://example.com"

    def test_inline_is_immutable(self):
        with pytest.raises(AttributeError):
            bold("x").text = "y"


class TestNormalize:
    def test_plain_string_wraps_in_list(self):
        assert normalize("hello") == ["hello"]

    def test_single_inline_wraps_in_list(self):
        span = bold("x")
        assert normalize(span) == [span]

    def test_list_passes_through(self):
        parts = ["a", bold("b"), "c"]
        assert normalize(parts) == parts

    def test_tuple_accepted(self):
        assert normalize(("a", "b")) == ["a", "b"]

    def test_non_string_items_coerced_to_str(self):
        assert normalize([1, 2.5, None]) == ["1", "2.5", "None"]

    def test_non_iterable_non_string_coerced(self):
        assert normalize(42) == ["42"]

    def test_empty_list(self):
        assert normalize([]) == []

    def test_generator_consumed(self):
        assert normalize(str(i) for i in range(3)) == ["0", "1", "2"]
