"""Tests for callouts and the strike/sub/sup/footnote inline styles."""

import io

import pytest

try:
    import fpdf
except ImportError:
    fpdf = None

from reportsmith import (
    Callout,
    Inline,
    Report,
    Section,
    TableOfContents,
    bold,
    footnote,
    strike,
    sub,
    sup,
)


def report() -> Report:
    return Report("T", date="")


def md(build) -> str:
    r = report()
    build(r)
    return r.to_markdown()


def html(build) -> str:
    r = report()
    build(r)
    return r.to_html(full_document=False)


def tex(build) -> str:
    r = report()
    build(r)
    return r.to_latex(full_document=False)


class TestInlineHelpers:
    @pytest.mark.parametrize(
        "fn, style", [(strike, "strike"), (sub, "sub"), (sup, "sup"), (footnote, "footnote")]
    )
    def test_helpers(self, fn, style):
        assert fn("x") == Inline(style, "x")


class TestStrikeSubSup:
    PARTS = ["H", sub("2"), "O, m", sup("2"), ", ", strike("old")]

    def test_markdown(self):
        assert "H<sub>2</sub>O, m<sup>2</sup>, ~~old~~" in md(lambda r: r.paragraph(self.PARTS))

    def test_markdown_escapes_html_in_sub(self):
        assert "<sup>a&lt;b</sup>" in md(lambda r: r.paragraph([sup("a<b")]))

    def test_html(self):
        out = html(lambda r: r.paragraph(self.PARTS + [sup("<x>")]))
        assert "<p>H<sub>2</sub>O, m<sup>2</sup>, <del>old</del><sup>&lt;x&gt;</sup></p>" in out

    def test_latex(self):
        out = tex(lambda r: r.paragraph(self.PARTS + [strike("50%")]))
        assert "H\\textsubscript{2}O, m\\textsuperscript{2}, \\sout{old}\\sout{50\\%}" in out

    def test_latex_preamble_loads_ulem(self):
        assert "\\usepackage[normalem]{ulem}" in report().to_latex()


class TestFootnotesMarkdown:
    def test_numbered_in_order_with_definitions_at_end(self):
        def build(r):
            r.paragraph(["A", footnote("First.")])
            with r.section("S") as s:
                s.paragraph(["B", footnote("Second.")])
        out = md(build)
        assert "A[^1]" in out and "B[^2]" in out
        assert out.endswith("[^1]: First.\n[^2]: Second.\n")

    def test_multiline_note_indented(self):
        out = md(lambda r: r.paragraph(["A", footnote("line 1\nline 2")]))
        assert "[^1]: line 1\n    line 2\n" in out

    def test_no_footnotes_no_block(self):
        assert "[^" not in md(lambda r: r.paragraph("plain"))

    def test_rendering_twice_restarts_numbering(self):
        r = report()
        r.paragraph(["A", footnote("x")])
        assert r.to_markdown() == r.to_markdown()

    def test_footnote_in_table_cell(self):
        out = md(lambda r: r.table(["A"], [[["v", footnote("Cell.")]]]))
        assert "| v[^1] |" in out and "[^1]: Cell." in out


class TestFootnotesHtml:
    def test_refs_and_list(self):
        out = html(lambda r: r.paragraph(["A", footnote("Note <1>"), "B", footnote("Two")]))
        assert '<sup class="footnote-ref"><a href="#fn-1" id="fnref-1">1</a></sup>' in out
        assert '<a href="#fn-2" id="fnref-2">2</a>' in out
        assert '<section class="footnotes">' in out
        assert '<li id="fn-1">Note &lt;1&gt; <a href="#fnref-1" class="footnote-back"' in out
        assert out.index("</p>") < out.index('<section class="footnotes">')

    def test_no_section_without_footnotes(self):
        assert "footnotes" not in html(lambda r: r.paragraph("x"))

    def test_toc_and_anchor_skip_footnotes(self):
        def build(r):
            r.toc()
            r.section(["Intro", footnote("About the intro.")])
        out = html(build)
        assert '<h2 id="intro">Intro<sup class="footnote-ref">' in out
        assert '<li><a href="#intro">Intro</a></li>' in out
        assert out.count('class="footnote-ref"') == 1


class TestFootnotesLatex:
    def test_footnote_command_escaped(self):
        out = tex(lambda r: r.paragraph(["A", footnote("100% sure")]))
        assert "A\\footnote{100\\% sure}" in out

    def test_heading_gets_short_title(self):
        def build(r):
            r.section(["Intro ", bold("now"), footnote("n")])
            r.heading(["Plain"], level=3)
        out = tex(build)
        assert "\\section[{Intro \\textbf{now}}]{Intro \\textbf{now}\\footnote{n}}" in out
        assert "\\subsection{Plain}" in out


class TestFootnotesMarkdownToc:
    def test_toc_entry_and_anchor_skip_footnote(self):
        def build(r):
            r.toc()
            r.section(["Intro", footnote("x")])
        out = md(build)
        assert "- [Intro](#intro)" in out
        assert "## Intro[^1]" in out


class TestCalloutElement:
    def test_defaults(self):
        c = Callout()
        assert (c.kind, c.title, c.display_title, c.children) == ("note", "", "Note", [])

    def test_content_becomes_paragraph(self):
        c = Callout("tip", ["Use ", bold("this")], title="Pro tip")
        assert c.display_title == "Pro tip"
        assert c.children[0].parts == ["Use ", bold("this")]

    def test_invalid_kind(self):
        with pytest.raises(ValueError, match="'danger'"):
            Callout("danger")

    def test_builder_returns_callout_usable_as_context(self):
        r = report()
        with r.callout("warning", "First.") as c:
            assert c.paragraph("Second.") is c
        assert r.children == [c]
        assert len(c.children) == 2

    def test_on_sections(self):
        r = report()
        with r.section("S") as s:
            c = s.callout("important")
        assert s.children == [c]

    def test_heading_level_follows_parent(self):
        r = report()
        with r.section("S") as s:
            s.callout().heading("H")
        assert s.children[0].children[0].level == 3

    def test_rejects_sections_and_toc(self):
        c = report().callout()
        with pytest.raises(TypeError):
            c.section("No")
        with pytest.raises(TypeError):
            c.toc()
        with pytest.raises(TypeError):
            c.add(Section("No"))
        with pytest.raises(TypeError):
            c.add(TableOfContents())

    def test_headings_inside_not_in_toc(self):
        def build(r):
            r.toc()
            r.callout().heading("Hidden")
            r.section("Shown")
        out = md(build)
        assert "[Shown](#shown)" in out
        assert "[Hidden]" not in out


class TestCalloutMarkdown:
    def test_github_alert(self):
        assert "> [!WARNING]\n> Careful.\n" in md(lambda r: r.callout("warning", "Careful."))

    def test_title_and_blocks(self):
        def build(r):
            with r.callout("tip", title="Pro tip") as c:
                c.paragraph("One.")
                c.bullet_list(["a"])
                c.code("x = 1", language="python")
        assert (
            "> [!TIP]\n> **Pro tip**\n>\n> One.\n>\n> - a\n>\n> ```python\n> x = 1\n> ```\n"
        ) in md(build)

    def test_empty(self):
        assert md(lambda r: r.callout("caution")).endswith("> [!CAUTION]\n")

    def test_nested(self):
        def build(r):
            with r.callout() as outer:
                outer.callout("tip", "Inner.")
        assert "> [!NOTE]\n> > [!TIP]\n> > Inner.\n" in md(build)


class TestCalloutHtml:
    def test_structure(self):
        out = html(lambda r: r.callout("important", "Body.", title="<Read>"))
        assert out.endswith(
            '<div class="callout callout-important">\n'
            '<p class="callout-title">&lt;Read&gt;</p>\n'
            "<p>Body.</p>\n"
            "</div>\n"
        )

    def test_default_css_styles_every_kind(self):
        css = report().to_html()
        for kind in ("note", "tip", "important", "warning", "caution"):
            assert f".callout-{kind}" in css


class TestCalloutLatex:
    def test_environment(self):
        out = tex(lambda r: r.callout("warning", "Body.", title="50% off"))
        assert "\\begin{rscallout}{rswarning}{50\\% off}\nBody.\n\\end{rscallout}" in out

    def test_default_title(self):
        assert "\\begin{rscallout}{rsnote}{Note}" in tex(lambda r: r.callout())

    def test_preamble_defines_environment_and_colours(self):
        out = report().to_latex()
        assert "\\newtcolorbox{rscallout}" in out
        for kind in ("note", "tip", "important", "warning", "caution"):
            assert f"\\definecolor{{rs{kind}}}" in out


@pytest.mark.skipif(fpdf is None, reason="fpdf2 not installed")
class TestPdf:
    def full(self) -> Report:
        r = report()
        with r.section(["Water", footnote("Heading note.")]) as s:
            s.paragraph(["H", sub("2"), "O ", sup("2"), strike("x"), footnote("Body note.")])
            s.table(["A"], [[["v", footnote("Cell note.")]]])
            for kind in ("note", "tip", "important", "warning", "caution"):
                s.callout(kind, f"A {kind}.")
            with s.callout("warning", title="Long") as c:
                for i in range(60):
                    c.paragraph(f"Line {i}")
                    if i == 30:
                        c.callout("tip", "Nested.")
        return r

    @pytest.mark.parametrize("fonts", [None, ()])
    def test_renders(self, fonts):
        assert self.full().to_pdf(fonts=fonts).startswith(b"%PDF-")

    def test_endnotes(self):
        pypdf = pytest.importorskip("pypdf")
        reader = pypdf.PdfReader(io.BytesIO(self.full().to_pdf()))
        text = "\n".join(p.extract_text() for p in reader.pages)
        notes = text[text.rindex("Notes"):]
        assert "1. Heading note." in notes
        assert "2. Body note." in notes
        assert "3. Cell note." in notes
        assert "v³" in text  # superscript marker in the table cell
        assert [o.title for o in reader.outline][-1] == "Notes"

    def test_cell_sub_sup_digits(self, caplog):
        pypdf = pytest.importorskip("pypdf")
        r = report()
        r.table(["A"], [[["CO", sub("2"), " m", sup("2"), " x", sup("n")]]])
        text = pypdf.PdfReader(io.BytesIO(r.to_pdf())).pages[0].extract_text()
        # Subscript digits are used only when the font has them.
        assert "CO₂ m² xn" in text or "CO2 m² xn" in text
        assert "missing the following glyphs" not in caplog.text

    def test_cell_sub_sup_core_fonts(self):
        pypdf = pytest.importorskip("pypdf")
        r = report()
        r.table(["A"], [[["CO", sub("2"), " m", sup("2")]]])
        text = pypdf.PdfReader(io.BytesIO(r.to_pdf(fonts=()))).pages[0].extract_text()
        assert "CO2 m2" in text

    def test_core_font_cell_marker(self):
        pypdf = pytest.importorskip("pypdf")
        r = report()
        r.table(["A"], [[["v", footnote("n")]]])
        reader = pypdf.PdfReader(io.BytesIO(r.to_pdf(fonts=())))
        assert "v[1]" in reader.pages[0].extract_text()

    def test_no_notes_without_footnotes(self):
        pypdf = pytest.importorskip("pypdf")
        r = report()
        r.callout("note", "x")
        reader = pypdf.PdfReader(io.BytesIO(r.to_pdf()))
        assert "Notes" not in reader.pages[0].extract_text()
