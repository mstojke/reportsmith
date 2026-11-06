"""Tests for multi-line PDF math and offline (embedded) MathJax."""

import io
from pathlib import Path

import pytest

from reportsmith import Report, math
from reportsmith.equations import _segments, _split_top, render_equation
from reportsmith.renderers import html as html_module
from reportsmith.renderers.html import MATHJAX_URL, cache_dir, fetch_mathjax, mathjax_inline_tags

try:
    import matplotlib
except ImportError:
    matplotlib = None
try:
    import fpdf
    import pypdf
except ImportError:
    fpdf = pypdf = None

requires_matplotlib = pytest.mark.skipif(matplotlib is None, reason="matplotlib needed")


class TestSplitting:
    def test_split_top_ignores_nested(self):
        assert _split_top(r"a & {b & c} & d", "&") == ["a ", r" {b & c} ", " d"]
        assert _split_top(r"a \& b & c", "&") == [r"a \& b ", " c"]
        rows = _split_top(r"a \\ \begin{matrix} b \\ c \end{matrix} \\ d", "\\\\")
        assert len(rows) == 3 and "matrix" in rows[1]

    def test_segments(self):
        segments = _segments(r"A = \left( \begin{matrix} 1 \end{matrix} \right) + B")
        assert [s[0] for s in segments] == ["tex", "env", "tex"]
        assert segments[1][1] == "matrix" and segments[1][4:] == ("(", ")")
        assert _segments(r"\begin{array}{lr} a & b \end{array}")[0][2] == "lr"
        assert _segments(r"\begin{align*} x \end{align*}")[0][1] == "align"


@requires_matplotlib
class TestRender:
    def size(self, tex):
        result = render_equation(tex, size=12, dpi=100)
        assert result is not None, tex
        return result[1], result[2]

    @pytest.mark.parametrize("tex", [
        r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}",
        r"f(x) = \begin{cases} x & x > 0 \\ 0 & \text{else} \end{cases}",
        r"\begin{aligned} a &= b \\ c &= d \end{aligned}",
        r"\begin{array}{lr} \alpha & 10 \\ \beta & 200 \end{array}",
        r"\begin{vmatrix} 1 & 0 \\ 0 & 1 \end{vmatrix}",
        r"\left[ \begin{matrix} 1 & 0 \\ 0 & 1 \end{matrix} \right]",
        r"x = 1 \\ y = 2",
    ])
    def test_environments_render(self, tex):
        width, height = self.size(tex)
        assert width > 0 and height > 0

    def test_rows_stack(self):
        one = self.size(r"\begin{matrix} a \end{matrix}")[1]
        three = self.size(r"\begin{matrix} a \\ b \\ c \end{matrix}")[1]
        assert three > 2.5 * one

    def test_delimiters_add_width(self):
        bare = self.size(r"\begin{matrix} a & b \end{matrix}")[0]
        assert self.size(r"\begin{pmatrix} a & b \end{pmatrix}")[0] > bare

    @pytest.mark.parametrize("tex", [r"x \le 0", r"x \ge 0", r"a \implies b", r"a \iff b", r"\tfrac{1}{2}",
                                     r"\lvert x \rvert", r"p \land q \lor \lnot r", r"x \gets 1"])
    def test_tex_aliases_mathtext_lacks(self, tex):
        assert render_equation(tex) is not None

    def test_single_line_unchanged(self):
        assert self.size(r"\frac{a}{b}")[1] > self.size("a")[1]

    @pytest.mark.skipif(fpdf is None, reason="fpdf2 needed")
    def test_pdf_shows_a_picture_not_text(self):
        r = Report("T")
        r.equation(r"\begin{cases} 1 & x > 0 \\ 0 & x \le 0 \end{cases}")
        reader = pypdf.PdfReader(io.BytesIO(r.to_pdf()))
        assert len(reader.pages[0].images) == 1


class TestOfflineMathJax:
    def report(self) -> Report:
        return Report("T").paragraph([math("x^2")])

    def test_local_path_is_embedded(self, tmp_path):
        js = tmp_path / "tex-svg.js"
        js.write_text("var MATHJAX_FAKE = '</script>';", encoding="utf-8")
        html = self.report().to_html(mathjax=js)
        assert "var MATHJAX_FAKE = '<\\/script>';" in html
        assert MATHJAX_URL not in html and "src=" not in html.split("<style>")[0] + html.split("</style>")[1].split("</head>")[0]
        assert "window.MathJax = {tex:" in html

    def test_embed_uses_fetch(self, monkeypatch):
        monkeypatch.setattr(html_module, "fetch_mathjax", lambda url=html_module.MATHJAX_SVG_URL: "/*fake*/")
        html = self.report().to_html(mathjax="embed")
        assert "<script>/*fake*/</script>" in html

    def test_not_embedded_without_math(self, tmp_path):
        js = tmp_path / "tex-svg.js"
        js.write_text("FAKE", encoding="utf-8")
        assert "FAKE" not in Report("T").to_html(mathjax=js)

    def test_save_html_embeds(self, tmp_path):
        js = tmp_path / "tex-svg.js"
        js.write_text("FAKE", encoding="utf-8")
        out = self.report().save_html(tmp_path / "r.html", mathjax=js)
        assert "<script>FAKE</script>" in out.read_text(encoding="utf-8")

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError, match="mathjax"):
            self.report().to_html(mathjax="  ")

    def test_inline_tags_escape_script_end(self):
        assert "</script>x" not in mathjax_inline_tags("'</script>x'")

    def test_cache_dir_override(self, monkeypatch, tmp_path):
        monkeypatch.setenv("REPORTSMITH_CACHE", str(tmp_path))
        assert cache_dir() == tmp_path

    def test_fetch_downloads_once(self, monkeypatch, tmp_path):
        monkeypatch.setenv("REPORTSMITH_CACHE", str(tmp_path))
        calls = []

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def urlopen(url, timeout):
            calls.append(url)
            return Response(b"/*mathjax*/")

        import urllib.request

        monkeypatch.setattr(urllib.request, "urlopen", urlopen)
        assert fetch_mathjax() == "/*mathjax*/"
        assert fetch_mathjax() == "/*mathjax*/"
        assert len(calls) == 1
        cached = list(Path(tmp_path).iterdir())
        assert len(cached) == 1 and cached[0].name == "mathjax-mathjax-3.2.2-es5-tex-svg.js"

    def test_fetch_failure_explains(self, monkeypatch, tmp_path):
        monkeypatch.setenv("REPORTSMITH_CACHE", str(tmp_path))
        import urllib.request

        def urlopen(url, timeout):
            raise OSError("offline")

        monkeypatch.setattr(urllib.request, "urlopen", urlopen)
        with pytest.raises(RuntimeError, match="local copy"):
            fetch_mathjax()
