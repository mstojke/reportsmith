"""Tests for definition lists, task lists, page breaks and Report.save()."""

import io

import pytest

from reportsmith import DefinitionList, PageBreak, Report, TaskList, bold, code

try:
    import fpdf
except ImportError:
    fpdf = None
try:
    import pypdf
except ImportError:
    pypdf = None

requires_pdf = pytest.mark.skipif(fpdf is None or pypdf is None, reason="fpdf2 and pypdf needed")


def report() -> Report:
    return Report("T", date="")


def build() -> Report:
    r = report()
    r.definition_list([("API", ["Application ", bold("programming"), " interface"]), ("a]b", "y")])
    r.task_list([(True, "Write docs"), (False, ["Ship ", code("v1")])])
    r.page_break()
    r.paragraph("After the break.")
    return r


class TestElements:
    def test_definition_pairs_and_mapping(self):
        assert DefinitionList([("a", "b")]).items == [(["a"], ["b"])]
        assert DefinitionList({"x": "y", "z": "w"}).items == [(["x"], ["y"]), (["z"], ["w"])]

    def test_task_items(self):
        assert TaskList([(True, "a"), (False, ["b"])]).items == [(True, ["a"]), (False, ["b"])]

    @pytest.mark.parametrize("items", [["ab"], [("a",)], [("a", "b", "c")]])
    def test_bad_definitions(self, items):
        with pytest.raises(ValueError, match="Definition 0"):
            DefinitionList(items)

    @pytest.mark.parametrize("items", [["x"], [("yes", "x")], [(1, "x")], [(True,)]])
    def test_bad_tasks(self, items):
        with pytest.raises(ValueError, match="Task 0"):
            TaskList(items)

    def test_builders_chain(self):
        r = report()
        assert r.definition_list({}).task_list([]).page_break() is r
        assert [type(c) for c in r.children] == [DefinitionList, TaskList, PageBreak]

    def test_available_in_sections_and_callouts(self):
        r = report()
        with r.section("S") as s:
            s.task_list([(True, "x")])
            with s.callout() as c:
                c.definition_list({"k": "v"}).page_break()
        assert "- [x] x" in r.to_markdown()


class TestMarkdown:
    def test_output(self):
        md = build().to_markdown()
        assert (
            "- **API**: Application **programming** interface\n- **a]b**: y\n\n"
            "- [x] Write docs\n- [ ] Ship `v1`\n\n"
            '<div style="break-after: page"></div>\n\nAfter the break.'
        ) in md

    def test_bold_term_not_double_bolded(self):
        r = report()
        r.definition_list([([bold("Key"), " term"], "v")])
        assert "- **Key** term: v" in r.to_markdown()

    def test_empty_lists_omitted(self):
        r = report()
        r.definition_list([]).task_list([])
        assert r.to_markdown() == "# T\n"


class TestHtml:
    def test_output(self):
        html = build().to_html(full_document=False)
        assert (
            "<dl>\n<dt>API</dt>\n<dd>Application <strong>programming</strong> interface</dd>\n"
            "<dt>a]b</dt>\n<dd>y</dd>\n</dl>\n"
        ) in html
        assert (
            '<ul class="task-list">\n'
            '<li><input type="checkbox" disabled checked> Write docs</li>\n'
            '<li><input type="checkbox" disabled> Ship <code>v1</code></li>\n</ul>\n'
        ) in html
        assert '<div class="page-break"></div>\n<p>After the break.</p>' in html

    def test_escaping(self):
        r = report()
        r.definition_list({"<t>": "<d>"}).task_list([(False, "<x>")])
        html = r.to_html(full_document=False)
        assert "<dt>&lt;t&gt;</dt>" in html and "<dd>&lt;d&gt;</dd>" in html
        assert "disabled> &lt;x&gt;</li>" in html

    def test_css(self):
        css = report().to_html()
        assert "ul.task-list" in css and "@media print { .page-break" in css

    def test_empty_lists_omitted(self):
        r = report()
        r.definition_list([]).task_list([])
        assert "<dl>" not in r.to_html() and "task-list\">" not in r.to_html()


class TestLatex:
    def test_output(self):
        tex = build().to_latex(full_document=False)
        assert (
            "\\begin{description}\n"
            "\\item[{API}] Application \\textbf{programming} interface\n"
            "\\item[{a{]}b}] y\n"
            "\\end{description}\n\n"
            "\\begin{itemize}\n"
            "\\item[$\\boxtimes$] Write docs\n"
            "\\item[$\\square$] Ship \\texttt{v1}\n"
            "\\end{itemize}\n\n"
            "\\clearpage\n\nAfter the break."
        ) in tex

    def test_preamble_loads_amssymb(self):
        assert "\\usepackage{amssymb}" in report().to_latex()

    def test_empty_lists_omitted(self):
        r = report()
        r.definition_list([]).task_list([])
        assert r.to_latex(full_document=False) == ""


@requires_pdf
class TestPdf:
    def read(self, r: Report, **kwargs):
        return pypdf.PdfReader(io.BytesIO(r.to_pdf(**kwargs)))

    @pytest.mark.parametrize("fonts", [None, ()])
    def test_renders(self, fonts):
        reader = self.read(build(), fonts=fonts)
        assert len(reader.pages) == 2
        first = reader.pages[0].extract_text()
        assert "API" in first and "Application programming interface" in first
        assert "Write docs" in first and "Ship v1" in first
        assert "After the break." in reader.pages[1].extract_text()

    def test_task_boxes_are_drawn(self):
        r = report()
        r.task_list([(True, "a"), (False, "b")])
        content = self.read(r, fonts=()).pages[0].get_contents().get_data()
        assert content.count(b" re S") >= 2  # one stroked rectangle per task

    def test_page_break_at_top_of_page_adds_no_blank_page(self):
        r = report()
        r.paragraph("one").page_break().page_break().paragraph("two")
        assert len(self.read(r, fonts=()).pages) == 2

    def test_many_tasks_flow_across_pages(self):
        r = report()
        r.task_list([(i % 2 == 0, f"Task {i}") for i in range(80)])
        reader = self.read(r, fonts=())
        assert len(reader.pages) >= 2
        assert "Task 79" in reader.pages[-1].extract_text()


class TestSave:
    @pytest.mark.parametrize(
        "name, start",
        [("r.md", b"# T"), ("r.markdown", b"# T"), ("r.html", b"<!DOCTYPE html>"),
         ("r.HTM", b"<!DOCTYPE html>"), ("r.tex", b"\\documentclass")],
    )
    def test_formats_by_extension(self, tmp_path, name, start):
        path = build().save(tmp_path / name)
        assert path == tmp_path / name
        assert path.read_bytes().startswith(start)

    @pytest.mark.skipif(fpdf is None, reason="fpdf2 not installed")
    def test_pdf(self, tmp_path):
        assert build().save(str(tmp_path / "r.pdf"), fonts=()).read_bytes().startswith(b"%PDF")

    def test_options_passed_through(self, tmp_path):
        html = build().save(tmp_path / "r.html", full_document=False).read_text(encoding="utf-8")
        assert html.startswith("<h1>T</h1>")
        tex = build().save(tmp_path / "r.tex", numbered=True).read_text(encoding="utf-8")
        assert "secnumdepth" not in tex

    def test_figure_assets_follow_save(self, tmp_path):
        r = report()
        r.figure(b"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'/>", caption="S")
        r.save(tmp_path / "doc.md")
        assert (tmp_path / "doc_files" / "figure-1.svg").exists()

    @pytest.mark.parametrize("name", ["r.docx", "noext", "r.txt"])
    def test_unknown_extension(self, tmp_path, name):
        with pytest.raises(ValueError, match="extension"):
            build().save(tmp_path / name)

    def test_unknown_option(self, tmp_path):
        with pytest.raises(TypeError):
            build().save(tmp_path / "r.md", css="x")
