"""Tests for the LaTeX renderer."""

import pytest

from reportsmith import Inline, LatexRenderer, ListElement, Report, bold, code, italic, link
from reportsmith.elements import Element
from reportsmith.renderers.latex import escape_latex


def full_report() -> Report:
    r = Report("LaTeX Test", author="Alice", subtitle="All elements", date="2026-10-12")
    with r.section("Section") as s:
        s.paragraph(["Plain, ", bold("bold"), ", ", italic("italic"), ", ", code("mono"), ", ", link("a link", "https://example.com"), "."])
        s.quote("A wise quote.")
        s.code("print('hello')", language="python")
        s.bullet_list(["one", ListElement(["nested"], ordered=True), "two"])
        s.table(["A", "B"], [["1", "2"]], caption="Cap", align=["left", "right"])
        s.image("chart.png", alt="Chart")
        s.horizontal_rule()
        with s.section("Nested") as inner:
            inner.paragraph("Deep content.")
    return r


def fragment(build) -> str:
    r = Report("T", date="")
    build(r)
    return r.to_latex(full_document=False)


class TestDocument:
    def test_full_document_structure(self):
        tex = full_report().to_latex()
        assert tex.startswith("\\documentclass[11pt,a4paper]{article}\n")
        assert "\\title{LaTeX Test\\\\[0.3em]\\large All elements}" in tex
        assert "\\author{Alice}" in tex
        assert "\\date{2026-10-12}" in tex
        assert "\\begin{document}\n\\maketitle\n" in tex
        assert tex.endswith("\\end{document}\n")

    def test_environments_balanced(self):
        tex = full_report().to_latex()
        for env in ["document", "quote", "Verbatim", "itemize", "enumerate", "longtable", "figure"]:
            assert tex.count(f"\\begin{{{env}}}") == tex.count(f"\\end{{{env}}}") == 1, env

    def test_braces_balanced(self):
        tex = full_report().to_latex().replace("\\{", "").replace("\\}", "")
        assert tex.count("{") == tex.count("}")

    def test_empty_date_suppresses_today(self):
        assert "\\date{}" in Report("T", date="").to_latex()

    def test_pdf_metadata(self):
        tex = Report("A & B", author="Jo").to_latex()
        assert "pdftitle={A \\& B}, pdfauthor={Jo}" in tex

    def test_unnumbered_by_default(self):
        assert "\\setcounter{secnumdepth}{0}" in Report("T").to_latex()
        assert "secnumdepth" not in Report("T").to_latex(numbered=True)

    def test_class_and_preamble_options(self):
        tex = Report("T").to_latex(
            document_class="report", class_options="", preamble="\\usepackage{amsmath}"
        )
        assert tex.startswith("\\documentclass{report}\n")
        assert (
            tex.index("\\usepackage{hyperref}")
            < tex.index("\\usepackage{amsmath}")
            < tex.index("\\begin{document}")
        )

    def test_fragment_has_body_only(self):
        assert fragment(lambda r: r.paragraph("Hello")) == "Hello\n\n"

    def test_renderer_direct_use(self):
        r = Report("T", date="")
        r.paragraph("x")
        assert LatexRenderer(full_document=False).render(r) == "x\n\n"

    def test_save_latex(self, tmp_path):
        path = full_report().save_latex(tmp_path / "r.tex", numbered=True)
        assert path.read_text(encoding="utf-8") == full_report().to_latex(numbered=True)


class TestElements:
    def test_section_levels(self):
        def build(r):
            r.section("L2").section("L3").section("L4").section("L5").section("L6").section("capped")

        tex = fragment(build)
        for cmd in ["section{L2}", "subsection{L3}", "subsubsection{L4}", "paragraph{L5}", "subparagraph{L6}", "subparagraph{capped}"]:
            assert f"\\{cmd}" in tex

    @pytest.mark.parametrize("level,cmd", [(1, "section"), (2, "section"), (3, "subsection"), (6, "subparagraph")])
    def test_heading_levels(self, level, cmd):
        assert fragment(lambda r: r.heading("H", level=level)) == f"\\{cmd}{{H}}\n\n"

    def test_inline_spans(self):
        tex = fragment(lambda r: r.paragraph([bold("b"), italic("i"), code("c"), link("l", "https://x.org")]))
        assert tex == "\\textbf{b}\\emph{i}\\texttt{c}\\href{https://x.org}{l}\n\n"

    def test_inline_span_text_escaped(self):
        assert fragment(lambda r: r.paragraph(code("a_b{}"))) == "\\texttt{a\\_b\\{\\}}\n\n"

    def test_unknown_inline_style_is_plain_text(self):
        assert fragment(lambda r: r.paragraph([Inline("weird", "a_b")])) == "a\\_b\n\n"

    def test_link_href_escaped(self):
        tex = fragment(lambda r: r.paragraph(link("x", "https://e.com/a%20b#frag{}\\")))
        assert "\\href{https://e.com/a\\%20b\\#frag\\%7B\\%7D\\%5C}{x}" in tex

    def test_quote(self):
        assert fragment(lambda r: r.quote("q")) == "\\begin{quote}\nq\n\\end{quote}\n\n"

    def test_code_block_escapes_only_command_chars(self):
        tex = fragment(lambda r: r.code("a_b & {c} \\x %"))
        assert "\na_b & \\{c\\} \\textbackslash{}x %\n" in tex
        assert "commandchars=\\\\\\{\\}" in tex

    def test_code_block_cannot_close_early(self):
        tex = fragment(lambda r: r.code("\\end{Verbatim}\nafter"))
        assert tex.count("\\end{Verbatim}") == 1
        assert "\\textbackslash{}end\\{Verbatim\\}" in tex

    def test_nested_lists(self):
        tex = fragment(lambda r: r.bullet_list(["a", ListElement(["b"], ordered=True), "c"]))
        assert tex == (
            "\\begin{itemize}\n\\item{} a\n"
            "\\begin{enumerate}\n\\item{} b\n\\end{enumerate}\n"
            "\\item{} c\n\\end{itemize}\n\n"
        )

    def test_leading_nested_list_gets_item(self):
        tex = fragment(lambda r: r.bullet_list([ListElement(["x"])]))
        assert tex.startswith("\\begin{itemize}\n\\item\n\\begin{itemize}")

    def test_empty_lists_are_omitted(self):
        # An environment with no \item is a LaTeX error.
        assert fragment(lambda r: r.bullet_list([])) == ""
        assert fragment(lambda r: r.bullet_list(["a", ListElement([])])).count("\\begin{itemize}") == 1

    def test_item_starting_with_bracket(self):
        assert "\\item{} {[}x{]} done" in fragment(lambda r: r.bullet_list(["[x] done"]))

    def test_table(self):
        tex = fragment(lambda r: r.table(["A", "B", "C"], [["1", "2", "3"]], caption="Cap & co", align=["left", "center", "right"]))
        assert tex == (
            "\\begin{longtable}{lcr}\n\\toprule\nA & B & C \\\\\n"
            "\\midrule\n\\endhead\n1 & 2 & 3 \\\\\n\\bottomrule\n"
            "\\caption{Cap \\& co} \\\\\n\\end{longtable}\n\n"
        )

    def test_table_without_caption(self):
        assert "\\caption" not in fragment(lambda r: r.table(["A"], [["1"]]))

    def test_table_multiline_cell(self):
        tex = fragment(lambda r: r.table(["A"], [["x\ny"]], align=["right"]))
        assert "\\begin{tabular}[t]{@{}r@{}}x \\\\ y\\end{tabular}" in tex

    def test_table_cell_specials_escaped(self):
        tex = fragment(lambda r: r.table(["a & b"], [["50%"]]))
        assert "a \\& b \\\\" in tex and "50\\% \\\\" in tex

    def test_zero_column_table_omitted(self):
        assert fragment(lambda r: r.table([], [])) == ""

    def test_image_with_title_caption(self):
        tex = fragment(lambda r: r.image("img/chart.png", alt="Alt", title="Q3_rev"))
        assert "\\includegraphics{img/chart.png}" in tex
        assert "\\caption*{Q3\\_rev}" in tex

    def test_image_alt_as_caption_and_none(self):
        assert "\\caption*{Alt}" in fragment(lambda r: r.image("a.png", alt="Alt"))
        assert "\\caption" not in fragment(lambda r: r.image("a.png"))

    def test_remote_image_becomes_link(self):
        tex = fragment(lambda r: r.image("https://e.com/a.png", alt="Chart"))
        assert tex == "\\href{https://e.com/a.png}{[Image: Chart]}\n\n"

    def test_horizontal_rule(self):
        assert "\\rule{\\linewidth}{0.4pt}" in fragment(lambda r: r.horizontal_rule())

    @pytest.mark.parametrize("fmt,shown", [("latex", True), ("both", False), ("html", False), ("markdown", False)])
    def test_raw(self, fmt, shown):
        assert ("\\newpage" in fragment(lambda r: r.raw("\\newpage", format=fmt))) is shown

    def test_raw_latex_skipped_in_other_formats(self):
        r = Report("T", date="")
        r.raw("\\newpage", format="latex")
        assert "newpage" not in r.to_markdown()
        assert "newpage" not in r.to_html()

    def test_unknown_element_raises(self):
        class Custom(Element):
            pass

        r = Report("T", date="")
        r.add(Custom())
        with pytest.raises(TypeError, match="Custom"):
            r.to_latex()


class TestEscaping:
    def test_all_specials(self):
        assert escape_latex("\\ & % $ # _ { } ~ ^ [ ]") == (
            "\\textbackslash{} \\& \\% \\$ \\# \\_ \\{ \\} "
            "\\textasciitilde{} \\textasciicircum{} {[} {]}"
        )

    def test_single_pass(self):
        # The replacement for "\" must not itself be re-escaped.
        assert escape_latex("\\{") == "\\textbackslash{}\\{"

    def test_metadata_escaped(self):
        tex = Report("100% $ure", author="A_B", subtitle="#1", date="~now").to_latex()
        assert "\\title{100\\% \\$ure\\\\[0.3em]\\large \\#1}" in tex
        assert "\\author{A\\_B}" in tex
        assert "\\date{\\textasciitilde{}now}" in tex

    def test_unicode_passthrough(self):
        assert "\\title{Zażółć}" in Report("Zażółć", date="").to_latex()
