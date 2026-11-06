"""Tests for inline math and display equations."""

import io

import pytest

from reportsmith import Equation, Report, Section, math, ref
from reportsmith.equations import render_equation, tex_to_ascii, tex_to_unicode, to_latin1
from reportsmith.renderers.html import MATHJAX_URL, has_math, mathjax_tags
from reportsmith.toc import plain_text

try:
    import fpdf
except ImportError:
    fpdf = None
try:
    import pypdf
except ImportError:
    pypdf = None
try:
    import matplotlib
except ImportError:
    matplotlib = None

requires_pdf = pytest.mark.skipif(fpdf is None or pypdf is None, reason="fpdf2 and pypdf needed")
requires_matplotlib = pytest.mark.skipif(matplotlib is None, reason="matplotlib needed")


def sample() -> Report:
    r = Report("T", date="")
    with r.section(["Energy ", math("E = mc^2")]) as s:
        s.paragraph(["See ", ref("gauss"), " where ", math(r"\alpha < 1"), "."])
        s.equation(r"\int_0^\infty e^{-x^2}\,dx = \frac{\sqrt{\pi}}{2}", label="gauss")
        s.equation(r"a^2 + b^2 = c^2")
        s.equation(r"\rho = \frac{\lambda}{\mu}", label="rho")
    return r


class TestElements:
    def test_math_span(self):
        span = math("  x^2 ")
        assert span.style == "math" and span.text == "x^2"

    @pytest.mark.parametrize("tex", ["", "   "])
    def test_empty_rejected(self, tex):
        with pytest.raises(ValueError):
            math(tex)
        with pytest.raises(ValueError):
            Equation(tex)

    def test_equation_label_format(self):
        assert Equation("x", label="eq-1").label == "eq-1"
        with pytest.raises(ValueError, match="Invalid label"):
            Equation("x", label="bad label")

    def test_builder_chains(self):
        r = Report("T")
        assert r.equation("x = 1") is r
        assert isinstance(r.children[0], Equation)

    def test_numbering_only_labelled(self):
        from reportsmith.numbering import Numbering

        r = sample()
        n = Numbering(r)
        eqs = [el for el in r.children[0].children if isinstance(el, Equation)]
        assert [n.equation_number(e) for e in eqs] == [1, 0, 2]
        assert n.ref_text("rho") == "Equation 2"

    def test_duplicate_label(self):
        r = Report("T")
        r.equation("x", label="a").equation("y", label="a")
        with pytest.raises(ValueError, match="Duplicate label"):
            r.to_markdown()

    def test_extend_prefixes_equation_labels(self):
        part = Section("Part")
        part.equation("x", label="e")
        part.paragraph([ref("e")])
        r = Report("T")
        r.extend([part], label_prefix="p1-")
        assert r.children[0].children[0].label == "p1-e"
        assert "\\label{eq:p1-e}" in r.to_latex()

    def test_plain_text_uses_unicode(self):
        assert plain_text(["Energy ", math("E = mc^2")]) == "Energy E = mc²"


class TestUnicode:
    @pytest.mark.parametrize(
        "tex, text",
        [
            ("E = mc^2", "E = mc²"),
            (r"\alpha^2 \le \frac{x}{2}", "α² ≤ x/2"),
            (r"\frac{a+b}{c}", "(a+b)/c"),
            (r"\sum_{i=1}^{n} x_i", "∑ᵢ₌₁ⁿ xᵢ"),
            (r"\sqrt{a^2+b^2}", "√(a²+b²)"),
            (r"\sqrt[3]{x}", "∛x"),
            (r"\mathbb{R}^n", "ℝⁿ"),
            (r"x_{\text{max}}", "x_(max)"),
            (r"\sin\theta", "sin θ"),
            (r"\sin(x)", "sin(x)"),
            (r"\left( a \right)", "( a )"),
            (r"\unknown x", "unknown x"),
            (r"a \\ b", "a; b"),
            ("f'(x)", "f′(x)"),
        ],
    )
    def test_conversion(self, tex, text):
        assert tex_to_unicode(tex) == text

    def test_latin1(self):
        assert to_latin1(tex_to_unicode(r"\alpha + \beta \le \pi")) == "alpha + beta <= pi"
        assert to_latin1(tex_to_unicode(r"\pi r^2")) == "pi r²"
        assert to_latin1(tex_to_unicode(r"\bar{x}_i")) == "x_i"
        assert to_latin1(tex_to_unicode(r"x \in \mathbb{R}")) == "x in R"
        to_latin1("x \u2603").encode("latin-1")  # anything else becomes "?"

    def test_ascii(self):
        assert tex_to_ascii(r"\frac{\alpha}{2}") == "fracalpha2"
        assert tex_to_ascii("E = mc^2") == "E = mc^2"


class TestMarkdown:
    def test_inline_and_display(self):
        md = sample().to_markdown()
        assert "## Energy $E = mc^2$" in md
        assert "See Equation 1 where $\\alpha < 1$." in md
        assert "$$\n\\int_0^\\infty e^{-x^2}\\,dx = \\frac{\\sqrt{\\pi}}{2} \\tag{1}\n$$" in md
        assert "$$\na^2 + b^2 = c^2\n$$" in md
        assert "\\tag{2}\n$$" in md


class TestHtml:
    def test_markup(self):
        html = sample().to_html()
        assert '<h2>Energy <span class="math">\\(E = mc^2\\)</span></h2>' in html
        assert '<span class="math">\\(\\alpha &lt; 1\\)</span>' in html
        assert '<a href="#eq-gauss" class="ref">Equation 1</a>' in html
        assert '<div class="equation" id="eq-gauss">\\[\\int_0^\\infty' in html
        assert "\\tag{1}\\]</div>" in html
        assert '<div class="equation">\\[a^2 + b^2 = c^2\\]</div>' in html

    def test_mathjax_only_when_needed(self):
        assert MATHJAX_URL in sample().to_html()
        assert "MathJax" not in Report("T").to_html()
        assert "MathJax" not in sample().to_html(full_document=False)

    def test_mathjax_off_or_custom(self):
        assert "MathJax" not in sample().to_html(mathjax=False)
        html = sample().to_html(mathjax="/static/mathjax/tex-chtml.js")
        assert '<script defer src="/static/mathjax/tex-chtml.js"></script>' in html
        assert MATHJAX_URL not in html

    def test_mathjax_config_ignores_dollars(self):
        tags = mathjax_tags()
        assert "inlineMath: [['\\\\(', '\\\\)']]" in tags
        assert "displayMath: [['\\\\[', '\\\\]']]" in tags
        assert "$" not in tags

    def test_save_html_passes_option(self, tmp_path):
        path = sample().save_html(tmp_path / "r.html", mathjax=False)
        assert "MathJax" not in path.read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        "build",
        [
            lambda r: r.paragraph([math("x")]),
            lambda r: r.bullet_list([["a ", math("x")]]),
            lambda r: r.table(["h"], [[[math("x")]]]),
            lambda r: r.definition_list([("t", [math("x")])]),
            lambda r: r.task_list([(True, [math("x")])]),
            lambda r: r.callout("note", [math("x")]),
            lambda r: r.equation("x"),
        ],
    )
    def test_has_math_finds_it_anywhere(self, build):
        r = Report("T")
        build(r)
        assert has_math(r)

    def test_no_math(self):
        r = Report("T")
        r.paragraph("Costs $5 and $6.")
        assert not has_math(r)


class TestLatex:
    def test_markup(self):
        tex = sample().to_latex()
        assert "\\usepackage{amsmath}" in tex
        assert "\\section{Energy \\texorpdfstring{\\(E = mc^2\\)}{E = mc\\textasciicircum{}2}}" in tex
        assert "\\hyperref[eq:gauss]{Equation~\\ref*{eq:gauss}}" in tex
        assert "\\begin{equation}\\label{eq:gauss}\n\\int_0^\\infty" in tex
        assert "\\[\na^2 + b^2 = c^2\n\\]" in tex

    def test_tex_is_not_escaped(self):
        tex = Report("T").paragraph([math(r"a_1 \& b")]).to_latex(full_document=False)
        assert "\\(a_1 \\& b\\)" in tex


class TestRenderEquation:
    @requires_matplotlib
    def test_png_and_size(self):
        result = render_equation(r"\frac{a}{b}", size=12, dpi=100)
        assert result is not None
        data, w, h = result
        assert data.startswith(b"\x89PNG") and w > 0 and h > 0

    @requires_matplotlib
    def test_unparsable_returns_none(self):
        assert render_equation(r"\notacommand{x}") is None
        assert render_equation(r"\begin{pmatrix} \notacommand & 1 \end{pmatrix}") is None
        assert render_equation(r"\begin{pmatrix} a & b") is None  # no \end

    def test_without_matplotlib(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name.startswith("matplotlib"):
                raise ImportError(name)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked)
        assert render_equation("x") is None


@requires_pdf
class TestPdf:
    def text(self, r: Report, fonts=None) -> str:
        reader = pypdf.PdfReader(io.BytesIO(r.to_pdf(fonts=fonts)))
        return "\n".join(p.extract_text() for p in reader.pages)

    def test_inline_unicode(self):
        text = self.text(sample())
        assert "Energy E = mc²" in text and "α < 1" in text
        assert "Equation 1" in text

    def test_core_fonts_spell_out(self):
        text = self.text(sample(), fonts=())
        assert "alpha < 1" in text

    @requires_matplotlib
    def test_display_equations_are_images_with_numbers(self):
        r = sample()
        reader = pypdf.PdfReader(io.BytesIO(r.to_pdf()))
        page = reader.pages[0]
        assert len(page.images) == 3
        text = page.extract_text()
        assert "(1)" in text and "(2)" in text and "(3)" not in text

    def test_fallback_text_without_matplotlib(self, monkeypatch):
        import reportsmith.renderers.pdf as pdf_module

        monkeypatch.setattr(pdf_module, "render_equation", lambda *a, **k: None)
        reader = pypdf.PdfReader(io.BytesIO(sample().to_pdf()))
        text = reader.pages[0].extract_text()
        assert len(reader.pages[0].images) == 0
        assert "a² + b² = c²" in text and "(1)" in text

    def test_math_in_table_cell(self):
        r = Report("T")
        r.table(["Symbol"], [[[math(r"\lambda")]], [[math("x^2")]]])
        text = self.text(r)
        assert "λ" in text and "x²" in text

    @requires_matplotlib
    def test_ref_links_to_equation(self):
        reader = pypdf.PdfReader(io.BytesIO(sample().to_pdf()))
        annots = [a.get_object() for a in reader.pages[0].get("/Annots", [])]
        assert any(a.get("/Subtype") == "/Link" for a in annots)
