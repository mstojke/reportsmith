"""Tests for table styling: widths, stripes, footers and styled cells."""

import io

import pytest

from reportsmith import Cell, Report, Table, bold, ref
from reportsmith.colors import check_color, to_hex, to_rgb
from reportsmith.elements import CellStyle
from reportsmith.renderers.html import theme_css

try:
    import fpdf
except ImportError:
    fpdf = None
try:
    import pypdf
except ImportError:
    pypdf = None

requires_pdf = pytest.mark.skipif(fpdf is None or pypdf is None, reason="fpdf2 and pypdf needed")


def styled() -> Report:
    r = Report("T", date="")
    r.table(
        ["Region", "Growth", "Notes"],
        [
            ["EMEA", Cell("+8%", color="green"), "Steady"],
            ["Americas", Cell("-4%", color="red", bold=True), Cell("Behind", background="amber")],
            ["Other", "0%", Cell("Hex", color="#7c3aed", background="#eef")],
        ],
        caption="Growth",
        align=["left", "right", "left"],
        widths=[2, 1, 3],
        striped=True,
        footer=["Total", Cell("+3%", color="green"), ""],
    )
    return r


class TestColors:
    @pytest.mark.parametrize(
        "value, expected",
        [("red", "red"), ("grey", "gray"), ("#ABC", "#aabbcc"), ("#B91C1C", "#b91c1c"), (None, None)],
    )
    def test_check(self, value, expected):
        assert check_color(value) == expected

    @pytest.mark.parametrize("value", ["pink", "#12", "#gggggg", "b91c1c", ""])
    def test_invalid(self, value):
        with pytest.raises(ValueError, match="Invalid color"):
            check_color(value)

    def test_conversion(self):
        assert to_hex("red") == "#b91c1c" and to_hex("red", background=True) == "#fee2e2"
        assert to_hex("#123456") == "#123456"
        assert to_rgb("#ff0080") == (255, 0, 128)


class TestModel:
    def test_cell(self):
        c = Cell(["a ", bold("b")], color="red", background="#eee", bold=1)
        assert c.parts == ["a ", bold("b")]
        assert c.style == CellStyle("red", "#eeeeee", True)
        assert not CellStyle() and CellStyle(bold=True)

    def test_table_options(self):
        t = styled().children[0]
        assert t.widths == pytest.approx([2 / 6, 1 / 6, 3 / 6])
        assert t.striped is True
        assert t.footer == [["Total"], ["+3%"], [""]]
        assert t.footer_styles == {1: CellStyle(color="green")}
        assert t.rows[1] == [["Americas"], ["-4%"], ["Behind"]]
        assert t.style_at(1, 1) == CellStyle(color="red", bold=True)
        assert t.style_at(0, 0) == CellStyle()

    def test_defaults(self):
        t = Table(["A"], [["1"]])
        assert (t.widths, t.striped, t.footer, t.cell_styles) == (None, False, None, {})

    @pytest.mark.parametrize(
        "kwargs, match",
        [
            ({"widths": [1]}, "one entry per column"),
            ({"widths": [1, 0]}, "positive"),
            ({"widths": [1, True]}, "positive"),
            ({"widths": [1, "2"]}, "positive"),
            ({"footer": ["only one"]}, "footer has 1 cells"),
        ],
    )
    def test_validation(self, kwargs, match):
        with pytest.raises(ValueError, match=match):
            Table(["A", "B"], [["1", "2"]], **kwargs)

    def test_header_cells_cant_be_styled(self):
        with pytest.raises(TypeError, match="Header"):
            Table([Cell("A"), "B"], [["1", "2"]])

    def test_footer_refs_prefixed_by_extend(self):
        src = Report("S")
        src.table(["A"], [["1"]], caption="C", label="t", footer=[["see ", ref("t")]])
        r = Report("R", date="")
        r.extend(src, label_prefix="x-")
        assert "see Table 1" in r.to_markdown()


class TestDataStyles:
    def records(self):
        return [{"name": "a", "v": -2}, {"name": "b", "v": 3}, {"name": "c", "v": None}]

    def test_styles_see_raw_values(self):
        r = Report("T")
        r.table_from_records(
            self.records(),
            formats={"v": "{:+d}"},
            styles={"v": lambda v: {"color": "red"} if v < 0 else {"bold": True}},
        )
        t = r.children[0]
        assert t.rows[0][1] == ["-2"] and t.style_at(0, 1) == CellStyle(color="red")
        assert t.style_at(1, 1) == CellStyle(bold=True)
        assert t.style_at(2, 1) == CellStyle()  # missing values aren't styled

    def test_none_means_unstyled(self):
        t = Table.from_records(self.records(), styles={"v": lambda v: None})
        assert t.cell_styles == {}

    def test_options_pass_through(self):
        t = Table.from_records(self.records(), widths=[1, 2], striped=True, footer=["Sum", "1"])
        assert t.striped and t.footer == [["Sum"], ["1"]] and t.widths == pytest.approx([1 / 3, 2 / 3])

    def test_csv(self):
        t = Table.from_csv(io.StringIO("a,b\n1,-5\n"), styles={"b": lambda v: {"color": "red"}})
        assert t.style_at(0, 1) == CellStyle(color="red")

    def test_unknown_column(self):
        with pytest.raises(ValueError, match="styles"):
            Table.from_records(self.records(), styles={"nope": lambda v: None})

    def test_bad_return(self):
        with pytest.raises(TypeError, match="dict of Cell options"):
            Table.from_records(self.records(), styles={"v": lambda v: "red"})

    def test_bad_option(self):
        with pytest.raises(TypeError):
            Table.from_records(self.records(), styles={"v": lambda v: {"colour": "red"}})

    def test_bad_color(self):
        with pytest.raises(ValueError, match="Invalid color"):
            Table.from_records(self.records(), styles={"v": lambda v: {"color": "pink"}})


class TestMarkdown:
    def test_bold_and_footer(self):
        md = styled().to_markdown()
        assert (
            "| EMEA | +8% | Steady |\n"
            "| Americas | **-4%** | Behind |\n"
            "| Other | 0% | Hex |\n"
            "| **Total** | **+3%** |  |\n"
        ) in md

    def test_bold_cell_with_bold_content_not_doubled(self):
        r = Report("T", date="")
        r.table(["A"], [[Cell(["x ", bold("y")], bold=True)]])
        assert "| x **y** |" in r.to_markdown()

    def test_pipes_escaped_in_bold_cells(self):
        r = Report("T", date="")
        r.table(["A"], [[Cell("a|b", bold=True)]], footer=["c|d"])
        md = r.to_markdown()
        assert "| **a\\|b** |" in md and "| **c\\|d** |" in md


class TestHtml:
    def html(self) -> str:
        return styled().to_html(full_document=False)

    def test_table_attributes(self):
        html = self.html()
        assert '<table class="striped">' in html
        assert (
            '<colgroup><col style="width:33.33%"><col style="width:16.67%">'
            '<col style="width:50%"></colgroup>'
        ) in html

    def test_cells(self):
        html = self.html()
        assert '<td class="cell-green" style="text-align:right">+8%</td>' in html
        assert '<td class="cell-bold cell-red" style="text-align:right">-4%</td>' in html
        assert '<td class="cell-bg-amber" style="text-align:left">Behind</td>' in html
        assert '<td style="text-align:left;color:#7c3aed;background:#eeeeff">Hex</td>' in html

    def test_footer(self):
        html = self.html()
        assert html.index("</tbody>") < html.index("<tfoot>") < html.index("</table>")
        assert '<tfoot>\n<tr><td style="text-align:left">Total</td>' in html

    def test_plain_table_unchanged(self):
        r = Report("T", date="")
        r.table(["A"], [["1"]])
        assert "<table>\n<thead>" in r.to_html(full_document=False)

    @pytest.mark.parametrize("theme", ["light", "dark"])
    def test_css_vars_per_theme(self, theme):
        css = theme_css(theme)
        assert "table.striped tbody tr:nth-child(even) { background: var(--stripe); }" in css
        assert ".cell-red { color: var(--cell-red); }" in css
        assert ".cell-bg-amber { background: var(--cell-bg-amber); }" in css
        expected = "#b91c1c" if theme == "light" else "#f87171"
        assert f"--cell-red: {expected};" in css

    def test_print_uses_light_cell_colors(self):
        css = theme_css("dark")
        assert "--cell-red: #b91c1c;" in css[css.index("@media print"):]


class TestLatex:
    def tex(self) -> str:
        return styled().to_latex(full_document=False)

    def test_column_spec(self):
        tex = self.tex()
        assert (
            "\\begin{longtable}{"
            ">{\\raggedright\\arraybackslash}p{\\dimexpr 0.3333\\linewidth-2\\tabcolsep\\relax}"
            ">{\\raggedleft\\arraybackslash}p{\\dimexpr 0.1667\\linewidth-2\\tabcolsep\\relax}"
            ">{\\raggedright\\arraybackslash}p{\\dimexpr 0.5000\\linewidth-2\\tabcolsep\\relax}}"
        ) in tex

    def test_rows(self):
        tex = self.tex()
        assert "EMEA & \\textcolor[HTML]{15803D}{+8\\%} & Steady \\\\\n" in tex
        assert (
            "\\rowcolor[HTML]{F5F6F8}Americas & \\textcolor[HTML]{B91C1C}{\\textbf{-4\\%}} & "
            "\\cellcolor[HTML]{FEF3C7}Behind \\\\\n"
        ) in tex
        assert "Other & 0\\% & \\cellcolor[HTML]{EEEEFF}\\textcolor[HTML]{7C3AED}{Hex} \\\\\n" in tex
        assert "\\midrule\n\\textbf{Total} & \\textcolor[HTML]{15803D}{\\textbf{+3\\%}} &  \\\\\n\\bottomrule" in tex

    def test_plain_table_unchanged(self):
        r = Report("T", date="")
        r.table(["A", "B"], [["1", "2"]])
        assert "\\begin{longtable}{ll}\n\\toprule\nA & B \\\\\n\\midrule\n\\endhead\n1 & 2 \\\\\n\\bottomrule" in r.to_latex(full_document=False)

    def test_preamble(self):
        tex = Report("T").to_latex()
        assert "\\usepackage{array}\n\\usepackage{colortbl}" in tex


@requires_pdf
class TestPdf:
    def read(self, r: Report, fonts=()):
        return pypdf.PdfReader(io.BytesIO(r.to_pdf(fonts=fonts))).pages[0]

    @pytest.mark.parametrize("fonts", [None, ()])
    def test_renders(self, fonts):
        text = self.read(styled(), fonts).extract_text()
        for row in ("EMEA +8% Steady", "Americas -4% Behind", "Total +3%"):
            assert row in text

    def test_colors_and_fills_drawn(self):
        import re

        content = self.read(styled()).get_contents().get_data().decode("latin-1")
        used = {
            tuple(round(float(v) * 255) for v in m.groups())
            for m in re.finditer(r"([\d.]+) ([\d.]+) ([\d.]+) rg", content)
        }
        assert to_rgb("green") in used  # +8% text
        assert to_rgb("red") in used  # -4% text
        assert to_rgb("amber", background=True) in used  # "Behind" fill
        assert (238, 238, 255) in used  # hex background
        assert (248, 249, 251) in used  # stripe

    def test_bold_cells_use_bold_font(self):
        page = self.read(styled())
        runs = []

        def visit(text, cm, tm, font_dict, size):
            if text.strip() and font_dict:
                runs.append((text.strip(), str(font_dict.get("/BaseFont"))))

        page.extract_text(visitor_text=visit)
        fonts = {text: font for text, font in runs}
        assert fonts.get("-4%") == "/Helvetica-Bold"
        assert fonts.get("Total") == "/Helvetica-Bold"
        assert fonts.get("EMEA") == "/Helvetica"

    def test_widths_change_layout(self):
        def x_of(report, needle):
            xs = []

            def visit(text, cm, tm, font_dict, size):
                if needle in text:
                    xs.append(tm[4])

            self.read(report).extract_text(visitor_text=visit)
            return xs[0]

        narrow = Report("T", date="")
        narrow.table(["A", "B"], [["a", "b"]], widths=[1, 4])
        wide = Report("T", date="")
        wide.table(["A", "B"], [["a", "b"]], widths=[4, 1])
        assert x_of(narrow, "b") < x_of(wide, "b")
