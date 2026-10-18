"""Tests for building tables from records, CSV and DataFrames."""

import io
from decimal import Decimal

import pytest

from reportsmith import Report, Table, bold
from reportsmith.data import is_missing, parse_number

try:
    import pandas as pd
except ImportError:
    pd = None

requires_pandas = pytest.mark.skipif(pd is None, reason="pandas not installed")

SALES = [
    {"region": "EMEA", "revenue": 1234567.891, "growth": 0.08},
    {"region": "APAC", "revenue": 987654.3, "growth": None},
]


def cells(table: Table) -> list[list[str]]:
    return [["".join(map(str, cell)) for cell in row] for row in table.rows]


def headers(table: Table) -> list[str]:
    return ["".join(map(str, h)) for h in table.headers]


class TestHelpers:
    @pytest.mark.parametrize(
        "value", [None, float("nan"), Decimal("NaN")]
    )
    def test_missing(self, value):
        assert is_missing(value)

    @pytest.mark.parametrize("value", [0, "", "nan", False, 0.0])
    def test_not_missing(self, value):
        assert not is_missing(value)

    @pytest.mark.parametrize(
        "text, expected",
        [("42", 42), ("-7", -7), ("+3", 3), ("0", 0), ("1.5", 1.5), (".5", 0.5),
         ("1e3", 1000.0), ("-2.5E-2", -0.025), (" 12 ", 12)],
    )
    def test_parse_number(self, text, expected):
        assert parse_number(text) == expected

    @pytest.mark.parametrize("text", ["007", "1,234", "abc", "1.2.3", "", "inf", "nan", "12%"])
    def test_parse_number_keeps_text(self, text):
        assert parse_number(text) == text


class TestRecords:
    def test_headers_rows_and_auto_align(self):
        t = Table.from_records(SALES)
        assert headers(t) == ["region", "revenue", "growth"]
        assert cells(t) == [["EMEA", "1234567.891", "0.08"], ["APAC", "987654.3", ""]]
        assert t.align == ["left", "right", "right"]

    def test_key_union_in_first_seen_order(self):
        t = Table.from_records([{"a": 1}, {"b": 2, "a": 3}])
        assert headers(t) == ["a", "b"]
        assert cells(t) == [["1", ""], ["3", "2"]]

    def test_columns_select_and_order(self):
        t = Table.from_records(SALES, ["growth", "region"])
        assert headers(t) == ["growth", "region"]
        assert cells(t)[0] == ["0.08", "EMEA"]

    def test_unknown_column(self):
        with pytest.raises(ValueError, match="'revnue'"):
            Table.from_records(SALES, ["revnue"])

    def test_columns_with_no_records(self):
        t = Table.from_records([], ["a", "b"])
        assert headers(t) == ["a", "b"]
        assert t.rows == []
        assert t.align == ["left", "left"]

    def test_no_records_no_columns(self):
        t = Table.from_records([])
        assert t.headers == [] and t.rows == []

    def test_rejects_non_mapping(self):
        with pytest.raises(TypeError, match="Record 1"):
            Table.from_records([{"a": 1}, ["a", 1]])

    def test_accepts_generator(self):
        t = Table.from_records({"n": i} for i in range(3))
        assert cells(t) == [["0"], ["1"], ["2"]]


class TestFormatting:
    def test_single_format_applies_to_numbers_only(self):
        t = Table.from_records(SALES, formats="{:,.1f}")
        assert cells(t)[0] == ["EMEA", "1,234,567.9", "0.1"]

    def test_per_column_formats(self):
        t = Table.from_records(SALES, formats={"revenue": "${:,.0f}", "growth": "{:+.1%}"})
        assert cells(t) == [["EMEA", "$1,234,568", "+8.0%"], ["APAC", "$987,654", ""]]

    def test_per_column_format_applies_to_text(self):
        t = Table.from_records(SALES, formats={"region": str.lower})
        assert cells(t)[0][0] == "emea"

    def test_callable_may_return_inline(self):
        t = Table.from_records(SALES, formats={"region": bold})
        assert t.rows[0][0] == [bold("EMEA")]

    def test_format_unknown_column(self):
        with pytest.raises(ValueError, match="formats"):
            Table.from_records(SALES, formats={"nope": "{}"})

    def test_missing_placeholder(self):
        t = Table.from_records(SALES, missing="—", formats={"growth": "{:.0%}"})
        assert cells(t)[1][2] == "—"

    def test_bool_and_inline_values(self):
        t = Table.from_records([{"ok": True, "name": bold("x")}])
        assert t.align == ["left", "left"]  # bools are not numeric
        assert t.rows[0] == [["True"], [bold("x")]]

    def test_textlike_list_value_kept(self):
        t = Table.from_records([{"v": ["a ", bold("b")]}], formats={"v": "{}!"})
        assert t.rows[0][0] == ["a ", bold("b")]

    def test_decimal_is_numeric(self):
        t = Table.from_records([{"d": Decimal("1.50")}], formats="{:.1f}")
        assert t.align == ["right"]
        assert cells(t) == [["1.5"]]


class TestHeadersAndAlign:
    def test_header_mapping(self):
        t = Table.from_records(SALES, headers={"revenue": "Revenue ($)"})
        assert headers(t) == ["region", "Revenue ($)", "growth"]

    def test_header_sequence(self):
        t = Table.from_records(SALES, ["region", "growth"], headers=["Region", bold("Growth")])
        assert t.headers[1] == [bold("Growth")]

    def test_header_sequence_wrong_length(self):
        with pytest.raises(ValueError, match="headers has 1"):
            Table.from_records(SALES, headers=["only one"])

    def test_header_mapping_unknown_column(self):
        with pytest.raises(ValueError, match="headers"):
            Table.from_records(SALES, headers={"nope": "x"})

    def test_explicit_align_overrides_auto(self):
        t = Table.from_records(SALES, align=["center"] * 3)
        assert t.align == ["center"] * 3

    def test_explicit_align_validated(self):
        with pytest.raises(ValueError):
            Table.from_records(SALES, align=["left"])

    def test_all_missing_column_left_aligned(self):
        t = Table.from_records([{"a": None}, {"a": float("nan")}])
        assert t.align == ["left"]

    def test_caption(self):
        assert Table.from_records(SALES, caption="Sales").caption == "Sales"


class TestCsv:
    CSV = "id,zip,amount,label\n1,00501,12.5,a\n2,90210,1e3,\n3,02134,-4,c|d\n"

    def test_parses_numbers_per_column(self):
        t = Table.from_csv(io.StringIO(self.CSV))
        assert cells(t) == [
            ["1", "00501", "12.5", "a"],
            ["2", "90210", "1000.0", ""],
            ["3", "02134", "-4", "c|d"],
        ]
        assert t.align == ["right", "left", "right", "left"]

    def test_parse_numbers_off(self):
        t = Table.from_csv(io.StringIO(self.CSV), parse_numbers=False)
        assert t.align == ["left"] * 4
        assert cells(t)[1][2] == "1e3"

    def test_path_columns_and_formats(self, tmp_path):
        path = tmp_path / "data.csv"
        path.write_text(self.CSV, encoding="utf-8")
        t = Table.from_csv(path, ["label", "amount"], formats={"amount": "{:.2f}"}, missing="-")
        assert cells(t) == [["a", "12.50"], ["-", "1000.00"], ["c|d", "-4.00"]]

    def test_str_path_encoding_and_bom(self, tmp_path):
        path = tmp_path / "data.csv"
        path.write_text("﻿name;city\nZoë;Kraków\n", encoding="utf-8")
        t = Table.from_csv(str(path), delimiter=";")
        assert headers(t) == ["name", "city"]
        assert cells(t) == [["Zoë", "Kraków"]]

    def test_latin1_encoding(self, tmp_path):
        path = tmp_path / "data.csv"
        path.write_bytes("city\nMünchen\n".encode("latin-1"))
        assert cells(Table.from_csv(path, encoding="latin-1")) == [["München"]]

    def test_quoted_fields_and_blank_lines(self):
        t = Table.from_csv(io.StringIO('a,b\n"x, y","line1\nline2"\n\n1,2\n'))
        assert cells(t) == [["x, y", "line1\nline2"], ["1", "2"]]

    def test_short_rows_padded(self):
        t = Table.from_csv(io.StringIO("a,b,c\n1\n"), missing="?")
        assert cells(t) == [["1", "?", "?"]]

    def test_unknown_column(self):
        with pytest.raises(ValueError, match="'nope'"):
            Table.from_csv(io.StringIO(self.CSV), ["id", "nope"])

    def test_long_row_rejected(self):
        with pytest.raises(ValueError, match="line 2"):
            Table.from_csv(io.StringIO("a,b\n1,2,3\n"))

    def test_empty_input(self):
        with pytest.raises(ValueError, match="empty"):
            Table.from_csv(io.StringIO(""))

    def test_header_only(self):
        t = Table.from_csv(io.StringIO("a,b\n"))
        assert headers(t) == ["a", "b"] and t.rows == []


@requires_pandas
class TestDataFrame:
    def frame(self):
        return pd.DataFrame(
            {"region": ["EMEA", "APAC", None], "revenue": [1.5, None, 3.0], "units": [10, 20, 30]},
            index=pd.Index(["a", "b", "c"], name="key"),
        )

    def test_basic(self):
        t = Table.from_dataframe(self.frame(), formats="{:.1f}")
        assert headers(t) == ["region", "revenue", "units"]
        assert cells(t) == [["EMEA", "1.5", "10.0"], ["APAC", "", "20.0"], ["", "3.0", "30.0"]]
        assert t.align == ["left", "right", "right"]

    def test_index(self):
        t = Table.from_dataframe(self.frame(), ["units"], index=True)
        assert headers(t) == ["key", "units"]
        assert cells(t)[0] == ["a", "10"]

    def test_unnamed_index(self):
        df = pd.DataFrame({"v": [1]})
        t = Table.from_dataframe(df, index=True)
        assert headers(t) == ["", "v"]
        assert cells(t) == [["0", "1"]]

    def test_pandas_na_and_nat(self):
        df = pd.DataFrame({
            "n": pd.array([1, None], dtype="Int64"),
            "t": [pd.Timestamp("2026-01-02"), pd.NaT],
        })
        t = Table.from_dataframe(df, missing="n/a")
        assert cells(t) == [["1", "2026-01-02 00:00:00"], ["n/a", "n/a"]]
        assert t.align == ["right", "left"]

    def test_numpy_scalars_numeric(self):
        df = pd.DataFrame({"x": [1, 2]})
        t = Table.from_dataframe(df, formats="{:03d}")
        assert cells(t) == [["001"], ["002"]]


class TestBuilder:
    def test_methods_chain_and_render_everywhere(self):
        r = Report("T", date="")
        out = (
            r.table_from_records(SALES, formats={"revenue": "{:,.0f}"}, caption="Sales")
            .table_from_csv(io.StringIO("a,b\n1,x\n"))
        )
        assert out is r
        with r.section("S") as s:
            assert s.table_from_records([{"k": 1}]) is s
        md = r.to_markdown()
        assert "| region | revenue | growth |\n| :--- | ---: | ---: |" in md
        assert "| EMEA | 1,234,568 | 0.08 |" in md
        assert '<td style="text-align:right">1,234,568</td>' in r.to_html()
        assert "\\begin{longtable}{lrr}" in r.to_latex()

    def test_rejects_non_dataframe(self):
        with pytest.raises(TypeError, match="DataFrame"):
            Table.from_dataframe([{"a": 1}])

    @requires_pandas
    def test_dataframe_builder(self):
        r = Report("T", date="")
        r.table_from_dataframe(pd.DataFrame({"a": [1]}), headers=["A"])
        assert "| A |\n| ---: |\n| 1 |" in r.to_markdown()

    def test_missing_placeholder_unicode_roundtrip(self, tmp_path):
        r = Report("T", date="")
        r.table_from_records(SALES, missing="—")
        path = r.save_markdown(tmp_path / "r.md")
        assert "| APAC | 987654.3 | — |" in path.read_text(encoding="utf-8")
