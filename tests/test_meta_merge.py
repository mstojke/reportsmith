"""Tests for report metadata, HTML themes, syntax highlighting and merging."""

import io
import sys

import pytest

from reportsmith import (
    Callout,
    Figure,
    Heading,
    Report,
    Section,
    Table,
    TableOfContents,
    bold,
    ref,
)
from reportsmith.renderers.html import DEFAULT_CSS, theme_css

try:
    import pygments
except ImportError:
    pygments = None
try:
    import fpdf
except ImportError:
    fpdf = None
try:
    import pypdf
except ImportError:
    pypdf = None

requires_pygments = pytest.mark.skipif(pygments is None, reason="Pygments not installed")
requires_pdf = pytest.mark.skipif(fpdf is None or pypdf is None, reason="fpdf2 and pypdf needed")

CODE = 'def greet(name):\n    return "hi " + name  # comment'


def meta_report() -> Report:
    return Report(
        "Q3 & Co",
        author="Ann",
        date="2026-10-22",
        subtitle="Sub",
        description='About "q" & <t>',
        keywords=["python", "reports"],
        language="pl",
    )


class TestMetadata:
    def test_defaults(self):
        r = Report("T")
        assert (r.description, r.keywords, r.language) == ("", [], "en")

    def test_keywords_must_be_a_sequence(self):
        with pytest.raises(TypeError, match="keywords"):
            Report("T", keywords="a, b")

    def test_html_head(self):
        html = meta_report().to_html()
        assert '<html lang="pl">' in html
        assert '<meta name="author" content="Ann">' in html
        assert '<meta name="description" content="About &quot;q&quot; &amp; &lt;t&gt;">' in html
        assert '<meta name="keywords" content="python, reports">' in html
        assert '<meta name="generator" content="reportsmith ' in html

    def test_html_omits_empty_fields(self):
        html = Report("T", date="").to_html()
        assert 'name="author"' not in html and 'name="description"' not in html
        assert 'name="keywords"' not in html and '<html lang="en">' in html

    def test_markdown_front_matter(self):
        md = meta_report().to_markdown(front_matter=True)
        assert md.startswith(
            "---\n"
            'title: "Q3 & Co"\n'
            'subtitle: "Sub"\n'
            'author: "Ann"\n'
            'date: "2026-10-22"\n'
            'description: "About \\"q\\" & <t>"\n'
            'keywords: ["python", "reports"]\n'
            'lang: "pl"\n'
            "---\n\n# Q3 & Co"
        )

    def test_markdown_front_matter_off_by_default(self, tmp_path):
        assert meta_report().to_markdown().startswith("# Q3 & Co")
        saved = meta_report().save_markdown(tmp_path / "r.md", front_matter=True)
        assert saved.read_text(encoding="utf-8").startswith("---\ntitle:")

    def test_latex_pdf_fields(self):
        tex = meta_report().to_latex()
        assert (
            "\\hypersetup{pdftitle={Q3 \\& Co}, pdfauthor={Ann}, "
            'pdfsubject={About "q" \\& <t>}, pdfkeywords={python, reports}, pdflang={pl}}'
        ) in tex

    def test_latex_minimal_fields(self):
        tex = Report("T", date="").to_latex()
        assert "\\hypersetup{pdftitle={T}, pdfauthor={}, pdflang={en}}" in tex

    @requires_pdf
    def test_pdf_document_properties(self):
        info = pypdf.PdfReader(io.BytesIO(meta_report().to_pdf(fonts=()))).metadata
        assert info["/Title"] == "Q3 & Co"
        assert info["/Author"] == "Ann"
        assert info["/Subject"] == 'About "q" & <t>'
        assert info["/Keywords"] == "python, reports"
        assert info["/Creator"].startswith("reportsmith ")


class TestThemes:
    def test_default_is_auto(self):
        assert DEFAULT_CSS == theme_css("auto")
        assert "@media (prefers-color-scheme: dark)" in DEFAULT_CSS
        assert Report("T").to_html().count("prefers-color-scheme") == 1

    def test_light_and_dark(self):
        light, dark = theme_css("light"), theme_css("dark")
        assert "prefers-color-scheme" not in light and "prefers-color-scheme" not in dark
        assert light.startswith(":root {\n  --text: #1f2933;")
        assert dark.startswith(":root {\n  --text: #e5e7eb;")
        html = Report("T").to_html(theme="dark")
        assert "--bg: #111827;" in html

    def test_callout_colours_follow_theme(self):
        assert "--warning: #fbbf24;" in theme_css("dark")
        assert ".callout-warning { --callout: var(--warning); }" in theme_css("light")

    def test_invalid_theme(self):
        with pytest.raises(ValueError, match="theme"):
            Report("T").to_html(theme="sepia")

    @pytest.mark.parametrize("theme", ["auto", "light", "dark"])
    def test_print_stylesheet_forces_light_colours(self, theme):
        css = theme_css(theme)
        printed = css[css.index("@media print {"):]
        assert "--bg: #ffffff;" in printed
        assert "break-inside: avoid" in printed
        assert 'a[href^="http"]::after' in printed

    def test_custom_css_replaces_theme(self):
        html = Report("T").to_html(css="body{color:red}", theme="dark")
        assert "body{color:red}" in html and "--bg" not in html

    def test_save_html_passes_theme(self, tmp_path):
        html = Report("T").save_html(tmp_path / "r.html", theme="light").read_text(encoding="utf-8")
        assert "prefers-color-scheme" not in html


class TestHighlighting:
    def report(self) -> Report:
        r = Report("T", date="")
        r.code(CODE, language="python")
        r.code("plain", language="no-such-language")
        r.code("<b>raw</b>")
        return r

    def test_off_by_default(self):
        html = self.report().to_html(full_document=False)
        assert '<span class="' not in html
        assert "def greet(name):" in html

    @requires_pygments
    def test_html(self):
        html = self.report().to_html(highlight=True)
        assert '<pre><code class="language-python"><span class="k">def</span>' in html
        assert "pre code .k {" in html  # token colours added to the stylesheet
        assert "<pre><code class=\"language-no-such-language\">plain</code></pre>" in html
        assert "<pre><code>&lt;b&gt;raw&lt;/b&gt;</code></pre>" in html

    @requires_pygments
    def test_html_css_per_theme(self):
        auto = Report("T").to_html(highlight=True)
        assert "@media screen and (prefers-color-scheme: dark) {\npre code ." in auto
        light = Report("T").to_html(highlight=True, theme="light")
        assert "prefers-color-scheme" not in light and "pre code .k {" in light
        dark = Report("T").to_html(highlight=True, theme="dark")
        assert "@media screen {\npre code ." in dark and "@media print {\npre code ." in dark
        assert "pre { line-height" not in auto  # Pygments' page-wide rules are dropped
        assert "pre code .err" not in auto

    @requires_pygments
    def test_html_custom_css_still_gets_token_colours(self):
        html = Report("T").to_html(css="body{}", highlight=True)
        assert html.count("pre code .k {") == 2  # light, plus dark under the media query

    @requires_pygments
    def test_latex(self):
        tex = self.report().to_latex(highlight=True)
        assert "\\def\\PY@" in tex  # style definitions in the preamble
        assert "\\begin{Verbatim}[commandchars=\\\\\\{\\},frame=single, framesep=2mm, fontsize=\\small]" in tex
        assert "\\PY{k}{def}" in tex
        assert tex.count("\\begin{Verbatim}") == 3  # unknown language and none stay plain

    def test_latex_off_has_no_style_defs(self):
        assert "\\PY@" not in self.report().to_latex()

    @requires_pygments
    @requires_pdf
    @pytest.mark.parametrize("fonts", [None, ()])
    def test_pdf(self, fonts):
        r = self.report()
        r.code("x = 1\n\n" + "y = " + " + ".join(["value"] * 40), language="python")
        plain = r.to_pdf(fonts=fonts)
        coloured = r.to_pdf(fonts=fonts, highlight=True)
        text = pypdf.PdfReader(io.BytesIO(coloured)).pages[0].extract_text()
        assert "def greet(name):" in text and "# comment" in text
        assert "plain" in text and "<b>raw</b>" in text

        def colour_ops(data):
            return pypdf.PdfReader(io.BytesIO(data)).pages[0].get_contents().get_data().count(b" rg")

        assert colour_ops(coloured) > colour_ops(plain)

    @pytest.mark.parametrize(
        "call",
        [
            lambda r: r.to_html(highlight=True),
            lambda r: r.to_latex(highlight=True),
            lambda r: r.to_pdf(highlight=True),
        ],
    )
    def test_missing_pygments(self, monkeypatch, call):
        for mod in list(sys.modules):
            if mod == "pygments" or mod.startswith("pygments."):
                monkeypatch.delitem(sys.modules, mod)
        monkeypatch.setitem(sys.modules, "pygments", None)
        if fpdf is None and call.__code__.co_names[-1] == "to_pdf":
            pytest.skip("fpdf2 not installed")
        with pytest.raises(ImportError, match=r"reportsmith\[highlight\]"):
            call(self.report())


class TestAdd:
    def test_standalone_section_is_relevelled(self):
        intro = Section("Intro")
        intro.heading("Auto")
        intro.heading("Fixed", level=5)
        with intro.section("Sub") as sub:
            sub.heading("Deep")
        r = Report("T", date="")
        r.add(intro)
        assert intro._level == 2
        auto, fixed, sub = intro.children
        assert (auto.level, fixed.level, sub._level, sub.children[0].level) == (3, 5, 3, 4)

    def test_add_into_nested_section(self):
        r = Report("T", date="")
        with r.section("A") as a:
            a.add(Section("B"))
        assert "### B" in r.to_markdown()

    def test_callout_relevelled(self):
        c = Callout()
        c.heading("H")
        r = Report("T", date="")
        with r.section("S") as s:
            s.add(c)
        assert (c._level, c.children[0].level) == (2, 3)

    def test_levels_capped(self):
        r = Report("T", date="")
        s = r
        for i in range(7):
            s = s.section(f"L{i}")
        s.add(Section("Deepest"))
        assert s.children[-1]._level == 6

    def test_add_report_rejected(self):
        with pytest.raises(TypeError, match="extend"):
            Report("A").add(Report("B"))


class TestExtend:
    def quarter(self, name: str) -> Report:
        q = Report(f"{name} Report", date="")
        q.toc()
        q.paragraph(["Top: ", ref("sales"), " and ", ref("chart", "the chart")])
        with q.section("Sales") as s:
            s.toc()  # nested TOCs are dropped too
            s.heading(["Heading ", ref("sales")])
            s.table(["A", "Ref"], [["1", ["see ", ref("chart")]]], caption=f"{name}", label="sales")
            s.figure(b"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'/>", caption="C", label="chart")
            s.bullet_list(["x", ["item ", ref("sales")]])
            s.definition_list([(["term ", ref("sales")], ["def ", ref("chart")])])
            s.task_list([(True, ["task ", ref("sales")])])
            with s.section(["Section ", ref("chart")]) as sub:
                sub.quote(["quote ", ref("sales")])
        return q

    def test_merges_under_sections_with_prefixes(self):
        annual = Report("Annual", date="")
        annual.toc(depth=2)
        for name in ("Q1", "Q2"):
            with annual.section(name) as s:
                s.extend(self.quarter(name), label_prefix=f"{name.lower()}-")
        md = annual.to_markdown()
        assert md.count("**Contents**") == 1  # merged TOCs skipped
        assert "### Sales" in md  # one level deeper than in the quarter
        assert "*Table 1: Q1*" in md and "*Table 2: Q2*" in md
        q2 = md[md.index("## Q2"):]
        for text in ("Top: Table 2 and the chart", "#### Heading Table 2", "see Figure 2",
                     "- item Table 2", "**term Table 2**: def Figure 2", "- [x] task Table 2",
                     "#### Section Figure 2", "> quote Table 2"):
            assert text in q2

    def test_labels_prefixed(self):
        r = Report("T", date="")
        r.extend(self.quarter("Q1"), label_prefix="q1:")
        labels = sorted(
            el.label for el in r.children[1].children if isinstance(el, (Table, Figure))
        )
        assert labels == ["q1:chart", "q1:sales"]

    def test_duplicate_labels_without_prefix(self):
        r = Report("T", date="")
        r.extend(self.quarter("Q1")).extend(self.quarter("Q2"))
        with pytest.raises(ValueError, match="label_prefix"):
            r.to_markdown()

    def test_source_unchanged_and_reusable(self):
        q = self.quarter("Q1")
        before = q.to_markdown()
        r = Report("T", date="")
        r.extend(q, label_prefix="a-").extend(q, label_prefix="b-")
        assert q.to_markdown() == before
        md = r.to_markdown()
        # Merged at report level, the quarter's sections keep their depth.
        assert md.count("\n## Sales\n") == 2 and "#### " not in md
        assert "*Table 1: Q1*" in md and "*Table 2: Q1*" in md

    def test_figure_source_shared_not_copied(self):
        plot = object.__new__(type("Plot", (), {"savefig": lambda *a, **k: None}))
        src = Report("S")
        src.figure(plot, caption="P")
        r = Report("T")
        r.extend(src)
        assert r.children[0].source is plot

    def test_extend_from_element_list(self):
        r = Report("T", date="")
        toc = TableOfContents()
        r.extend([Section("A"), toc])
        assert isinstance(r.children[0], Section) and r.children[0]._level == 2
        assert isinstance(r.children[1], TableOfContents)  # only container sources skip TOCs

    def test_extend_section_source(self):
        s = Section("S")
        s.paragraph([bold("x")])
        s.heading("H")
        r = Report("T", date="")
        with r.section("Outer") as outer:
            outer.extend(s)
        assert r.children[0].children[1].level == 3

    def test_callout_rejects_sections(self):
        c = Report("T").callout()
        with pytest.raises(TypeError):
            c.extend(self.quarter("Q1"))

    def test_invalid_prefix(self):
        with pytest.raises(ValueError):
            Report("T").extend(self.quarter("Q1"), label_prefix="bad prefix ")

    def test_chaining(self):
        r = Report("T")
        assert r.extend([]) is r

    def test_heading_auto_flag(self):
        r = Report("T")
        r.heading("auto").heading("fixed", level=4)
        assert [h._auto_level for h in r.children] == [True, False]
        assert Heading("x")._auto_level is False
