"""Tests for the TeX to OMML (Word equation) converter."""

import re
from xml.dom import minidom

import pytest

from reportsmith.omml import M_NS, tex_to_omml

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def omml(tex: str) -> str:
    xml = tex_to_omml(tex)
    minidom.parseString(f'<root xmlns:m="{M_NS}" xmlns:w="{W_NS}">{xml}</root>')  # well-formed
    assert xml.startswith("<m:oMath>") and xml.endswith("</m:oMath>")
    return xml


def text(xml: str) -> str:
    return "".join(re.findall(r"<m:t[^>]*>([^<]*)</m:t>", xml))


class TestStructures:
    def test_runs_merge_and_minus(self):
        xml = omml("a+b-c")
        assert xml.count("<m:r>") == 1 and text(xml) == "a+b−c"

    def test_fraction(self):
        assert "<m:f><m:num>" in omml(r"\frac{a}{b}") and "</m:den></m:f>" in omml(r"\dfrac12")

    def test_scripts_bind_to_last_character(self):
        xml = omml("ab^2")
        assert re.search(r"<m:t[^>]*>a</m:t></m:r><m:sSup><m:e>.*?>b<", xml)
        assert "<m:sSubSup>" in omml("x_i^2")
        assert "<m:sSub>" in omml("x_{ij}")

    def test_roots(self):
        assert '<m:degHide m:val="1"/>' in omml(r"\sqrt{x}")
        xml = omml(r"\sqrt[3]{x}")
        assert "degHide" not in xml and re.search(r"<m:deg>.*?>3<.*?</m:deg>", xml)

    @pytest.mark.parametrize("tex, char, loc", [
        (r"\sum_{i=1}^{n} x_i", "∑", "undOvr"), (r"\int_0^1 f", "∫", "subSup"), (r"\prod_k a_k", "∏", "undOvr"),
    ])
    def test_big_operators(self, tex, char, loc):
        xml = omml(tex)
        assert f'<m:chr m:val="{char}"/><m:limLoc m:val="{loc}"/>' in xml

    def test_operator_operand_stops_at_relation(self):
        xml = omml(r"\sum_i x_i = 1")
        assert re.search(r"<m:e>.*>x<.*</m:e></m:nary>.*>=1<", xml)

    def test_missing_limits_hidden(self):
        xml = omml(r"\int f")
        assert '<m:subHide m:val="1"/>' in xml and '<m:supHide m:val="1"/>' in xml

    def test_functions(self):
        xml = omml(r"\sin x")
        assert "<m:func><m:fName>" in xml and '<m:sty m:val="p"/>' in xml
        xml = omml(r"\lim_{x \to 0} f(x)")
        assert "<m:func><m:fName><m:limLow><m:e>" in xml and "→" in text(xml)

    def test_delimiters(self):
        xml = omml(r"\left( a \right]")
        assert '<m:begChr m:val="("/><m:endChr m:val="]"/>' in xml
        assert '<m:begChr m:val="{"/><m:endChr m:val=""/>' in omml(r"\left\{ x \right.")
        assert '<m:begChr m:val="⟨"/>' in omml(r"\left\langle x \right\rangle")

    def test_accents_and_bars(self):
        assert '<m:chr m:val="̂"/>' in omml(r"\hat{x}")
        assert '<m:pos m:val="top"/>' in omml(r"\overline{AB}")

    def test_text_and_fonts(self):
        xml = omml(r"x_{\text{max}}")
        assert "<m:nor/>" in xml and ">max<" in xml
        assert '<m:scr m:val="double-struck"/>' in omml(r"\mathbb{R}")
        assert '<m:sty m:val="b"/>' in omml(r"\mathbf{v}")

    def test_binomial(self):
        xml = omml(r"\binom{n}{k}")
        assert '<m:type m:val="noBar"/>' in xml and '<m:begChr m:val="("/>' in xml

    def test_symbols_and_spaces(self):
        assert text(omml(r"\alpha \le \pi")) == "α≤π"
        assert " " in text(omml(r"a \quad b"))

    def test_unknown_command_kept(self):
        xml = omml(r"\foo x")
        assert ">foo<" in xml


class TestEnvironments:
    def test_pmatrix(self):
        xml = omml(r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}")
        assert '<m:begChr m:val="("/>' in xml
        assert xml.count("<m:mr>") == 2 and xml.count('<m:mcJc m:val="center"/>') == 2

    def test_cases(self):
        xml = omml(r"\begin{cases} 1 & x > 0 \\ 0 & \text{otherwise} \end{cases}")
        assert '<m:begChr m:val="{"/><m:endChr m:val=""/>' in xml
        assert xml.count('<m:mcJc m:val="left"/>') == 2

    def test_aligned(self):
        xml = omml(r"\begin{aligned} a &= b \\ c &= d \end{aligned}")
        assert '<m:mcJc m:val="right"/>' in xml and '<m:mcJc m:val="left"/>' in xml
        assert '<m:cGpRule m:val="3"/><m:cGp m:val="60"/>' in xml

    def test_array_spec(self):
        xml = omml(r"\begin{array}{lr} a & b \end{array}")
        assert re.findall(r'<m:mcJc m:val="(\w+)"/>', xml) == ["left", "right"]

    def test_ragged_rows_padded(self):
        xml = omml(r"\begin{matrix} a & b \\ c \end{matrix}")
        rows = re.findall(r"<m:mr>(.*?)</m:mr>", xml)
        assert [r.count("<m:e>") for r in rows] == [2, 2]

    def test_trailing_row_break_ignored(self):
        assert omml(r"\begin{matrix} a \\ b \\ \end{matrix}").count("<m:mr>") == 2

    def test_gathered_and_bare_breaks(self):
        assert omml(r"\begin{gathered} a \\ b \end{gathered}").count("<m:e>") == 2
        assert "<m:eqArr>" in omml(r"\begin{gathered} a \end{gathered}")

    def test_bracketed_environment(self):
        xml = omml(r"\left[ \begin{matrix} 1 \end{matrix} \right]")
        assert '<m:begChr m:val="["/><m:endChr m:val="]"/>' in xml


@pytest.mark.parametrize("tex", ["", "}", "{", r"\frac{a}", "^2", r"\left(", r"\begin{pmatrix} a", "a & b"])
def test_malformed_input_still_valid(tex):
    omml(tex)
