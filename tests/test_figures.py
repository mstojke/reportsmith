"""Tests for figures, caption numbering and cross-references."""

import io
import re
import struct
import zlib

import pytest

from reportsmith import Figure, Image, Report, Table, ref
from reportsmith.numbering import Numbering

try:
    import fpdf
except ImportError:
    fpdf = None
try:
    import pypdf
except ImportError:
    pypdf = None

requires_pdf = pytest.mark.skipif(fpdf is None or pypdf is None, reason="fpdf2 and pypdf needed")


def tiny_png(width: int = 2, height: int = 2) -> bytes:
    """A valid RGB PNG, built without any imaging library."""
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


PNG = tiny_png()
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4" viewBox="0 0 4 4"><rect width="4" height="4"/></svg>'


class FakePlot:
    """Stands in for a matplotlib figure: anything with savefig() works."""

    def __init__(self):
        self.calls = []

    def savefig(self, buffer, format, dpi, bbox_inches):
        self.calls.append((format, dpi, bbox_inches))
        buffer.write(PNG if format == "png" else b"%PDF-1.4 fake")


def report() -> Report:
    return Report("T", date="")


class TestFigureElement:
    def test_path_source(self, tmp_path):
        f = Figure(tmp_path / "Chart.JPG", caption="C")
        assert (f.kind, f.format, f.alt) == ("path", "jpeg", "C")

    @pytest.mark.parametrize(
        "data, fmt",
        [(PNG, "png"), (b"\xff\xd8\xff\xe0rest", "jpeg"), (b"GIF89a....", "gif"),
         (SVG, "svg"), (b'<?xml version="1.0"?>\n' + SVG, "svg")],
    )
    def test_bytes_formats_sniffed(self, data, fmt):
        f = Figure(data)
        assert (f.kind, f.format) == ("bytes", fmt)
        assert f.image_data() == (data, fmt)

    def test_plot_source(self):
        plot = FakePlot()
        f = Figure(plot, dpi=150)
        assert f.kind == "plot"
        data, fmt = f.image_data("pdf")
        assert (data, fmt) == (b"%PDF-1.4 fake", "pdf")
        assert plot.calls == [("pdf", 150, "tight")]

    def test_path_image_data_reads_file(self, tmp_path):
        path = tmp_path / "a.png"
        path.write_bytes(PNG)
        assert Figure(str(path)).image_data() == (PNG, "png")

    def test_explicit_alt(self):
        assert Figure(PNG, caption="Cap", alt="Alt").alt == "Alt"

    @pytest.mark.parametrize(
        "kwargs, error",
        [
            ({"source": 42}, TypeError),
            ({"source": b"not an image"}, ValueError),
            ({"source": "https://example.com/a.png"}, ValueError),
            ({"source": PNG, "width": 0}, ValueError),
            ({"source": PNG, "width": 1.5}, ValueError),
            ({"source": PNG, "label": "x"}, ValueError),  # label without caption
            ({"source": PNG, "caption": "C", "label": "has space"}, ValueError),
            ({"source": PNG, "caption": "C", "label": "-leading"}, ValueError),
        ],
    )
    def test_validation(self, kwargs, error):
        with pytest.raises(error):
            Figure(**kwargs)

    def test_label_characters(self):
        assert Figure(PNG, caption="C", label="sec2:fig_1.a-b").label == "sec2:fig_1.a-b"

    def test_builder_chains(self):
        r = report()
        assert r.figure(PNG, caption="C") is r
        assert isinstance(r.children[0], Figure)

    def test_table_label(self):
        assert Table(["A"], [["1"]], caption="C", label="t").label == "t"
        with pytest.raises(ValueError, match="needs a caption"):
            Table(["A"], [["1"]], label="t")

    def test_table_label_from_data(self):
        r = report()
        r.table_from_records([{"a": 1}], caption="C", label="rec")
        assert r.children[0].label == "rec"
        assert Table.from_records([{"a": 1}], caption="C", label="x").label == "x"


class TestNumbering:
    def build(self) -> Report:
        r = report()
        r.figure(PNG, caption="F1", label="f1")
        r.table(["A"], [["1"]])  # no caption: not numbered
        with r.section("S") as s:
            s.table(["A"], [["1"]], caption="T1", label="t1")
            with s.callout() as c:
                c.figure(PNG, caption="F2")
        r.figure(PNG)  # no caption: not numbered
        r.table(["A"], [["1"]], caption="T2")
        return r

    def test_separate_counters_in_document_order(self):
        r = self.build()
        n = Numbering(r)
        callout_figure = r.children[2].children[1].children[0]
        assert n.caption_label(r.children[0]) == "Figure 1"
        assert n.caption_label(callout_figure) == "Figure 2"
        assert n.caption_label(r.children[2].children[0]) == "Table 1"
        assert n.caption_label(r.children[4]) == "Table 2"
        assert n.caption_label(r.children[1]) == ""
        assert n.caption_label(r.children[3]) == ""

    def test_resolve_and_text(self):
        n = Numbering(self.build())
        assert n.resolve("t1") == ("table", 1)
        assert n.ref_text("f1") == "Figure 1"
        assert n.ref_text("f1", "the chart") == "the chart"

    def test_duplicate_label(self):
        r = report()
        r.figure(PNG, caption="A", label="x")
        r.table(["A"], [["1"]], caption="B", label="x")
        with pytest.raises(ValueError, match="Duplicate label 'x'"):
            r.to_markdown()

    @pytest.mark.parametrize("method", ["to_markdown", "to_html", "to_latex"])
    def test_unknown_ref(self, method):
        r = report()
        r.paragraph(["See ", ref("nope")])
        with pytest.raises(ValueError, match="'nope'"):
            getattr(r, method)()


class TestMarkdown:
    def test_table_caption_numbered(self):
        r = report()
        r.table(["A"], [["1"]], caption="Sales")
        assert "*Table 1: Sales*" in r.to_markdown()

    def test_path_figure(self, tmp_path):
        r = report()
        r.figure(tmp_path / "chart.png", caption="Revenue")
        assert f"![Revenue]({(tmp_path / 'chart.png').as_posix()})\n\n*Figure 1: Revenue*" in r.to_markdown()

    def test_uncaptioned_figure(self):
        r = report()
        r.figure("chart.png", alt="A chart")
        assert r.to_markdown().endswith("![A chart](chart.png)\n")

    def test_plot_embedded_as_data_uri(self):
        r = report()
        r.figure(FakePlot(), caption="P")
        assert "![P](data:image/png;base64," in r.to_markdown()

    def test_assets_dir(self, tmp_path):
        r = report()
        r.figure(FakePlot(), caption="P").figure(SVG)
        md = r.to_markdown(assets_dir=tmp_path / "img")
        assert f"]({(tmp_path / 'img').as_posix()}/figure-1.png)" in md
        assert (tmp_path / "img" / "figure-1.png").read_bytes() == PNG
        assert (tmp_path / "img" / "figure-2.svg").read_bytes() == SVG

    def test_save_markdown_writes_relative_assets(self, tmp_path):
        r = report()
        r.figure(FakePlot(), caption="P")
        path = r.save_markdown(tmp_path / "out.md")
        assert "](out_files/figure-1.png)" in path.read_text(encoding="utf-8")
        assert (tmp_path / "out_files" / "figure-1.png").exists()

    def test_save_markdown_without_generated_figures_creates_no_folder(self, tmp_path):
        r = report()
        r.figure("chart.png")
        r.save_markdown(tmp_path / "out.md")
        assert not (tmp_path / "out_files").exists()

    def test_refs_are_plain_text(self):
        r = report()
        r.paragraph(["See ", ref("t"), " and ", ref("t", "that table"), "."])
        r.table(["A"], [["1"]], caption="C", label="t")
        assert "See Table 1 and that table." in r.to_markdown()


class TestHtml:
    def html(self, build) -> str:
        r = report()
        build(r)
        return r.to_html(full_document=False)

    def test_table_caption_and_id(self):
        out = self.html(lambda r: r.table(["A"], [["1"]], caption="<Sales>", label="sales"))
        assert '<table id="tbl-sales">' in out
        assert '<caption><span class="caption-label">Table 1:</span> &lt;Sales&gt;</caption>' in out

    def test_table_without_label_has_no_id(self):
        assert "<table>\n" in self.html(lambda r: r.table(["A"], [["1"]], caption="C"))

    def test_figure_markup(self):
        out = self.html(lambda r: r.figure("a b.png", caption="Cap", label="f", width=0.5))
        assert out.endswith(
            '<figure id="fig-f">\n'
            '<img src="a b.png" alt="Cap" style="width:50%">\n'
            '<figcaption><span class="caption-label">Figure 1:</span> Cap</figcaption>\n'
            "</figure>\n"
        )

    def test_bytes_and_plot_embedded(self):
        out = self.html(lambda r: r.figure(SVG).figure(FakePlot()))
        assert 'src="data:image/svg+xml;base64,' in out
        assert 'src="data:image/png;base64,' in out

    def test_ref_links(self):
        def build(r):
            r.paragraph([ref("f"), ", ", ref("t", "<this>")])
            r.figure(PNG, caption="F", label="f")
            r.table(["A"], [["1"]], caption="T", label="t")
        out = self.html(build)
        assert '<a href="#fig-f" class="ref">Figure 1</a>' in out
        assert '<a href="#tbl-t" class="ref">&lt;this&gt;</a>' in out

    def test_css(self):
        css = report().to_html()
        assert "figcaption" in css and ".caption-label" in css


class TestLatex:
    def tex(self, build, **kwargs) -> str:
        r = report()
        build(r)
        return r.to_latex(full_document=False, **kwargs)

    def test_path_figure(self):
        out = self.tex(lambda r: r.figure("chart.png", caption="50% up", label="c", width=0.8))
        assert out == (
            "\\begin{figure}[htbp]\n\\centering\n"
            "\\includegraphics[width=0.8\\linewidth]{chart.png}\n"
            "\\caption{50\\% up}\\label{fig:c}\n"
            "\\end{figure}\n\n"
        )

    def test_uncaptioned_figure(self):
        out = self.tex(lambda r: r.figure("chart.png"))
        assert "\\includegraphics{chart.png}\n\\end{figure}" in out

    def test_plot_needs_assets(self):
        with pytest.raises(ValueError, match="save_latex"):
            self.tex(lambda r: r.figure(FakePlot()))

    def test_svg_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="SVG"):
            self.tex(lambda r: r.figure(SVG), assets_dir=tmp_path)

    def test_plot_written_as_pdf(self, tmp_path):
        out = self.tex(lambda r: r.figure(FakePlot()).figure(PNG), assets_dir=tmp_path / "a")
        assert f"\\includegraphics{{{(tmp_path / 'a').as_posix()}/figure-1.pdf}}" in out
        assert (tmp_path / "a" / "figure-1.pdf").read_bytes() == b"%PDF-1.4 fake"
        assert (tmp_path / "a" / "figure-2.png").read_bytes() == PNG

    def test_save_latex_relative_assets(self, tmp_path):
        r = report()
        r.figure(FakePlot(), caption="P")
        tex = r.save_latex(tmp_path / "doc.tex").read_text(encoding="utf-8")
        assert "\\includegraphics{doc_files/figure-1.pdf}" in tex
        assert (tmp_path / "doc_files" / "figure-1.pdf").exists()

    def test_table_label(self):
        out = self.tex(lambda r: r.table(["A"], [["1"]], caption="C", label="t"))
        assert "\\caption{C}\\label{tab:t} \\\\" in out

    def test_refs(self):
        def build(r):
            r.paragraph([ref("t"), " ", ref("f", "100% this")])
            r.table(["A"], [["1"]], caption="C", label="t")
            r.figure("x.png", caption="F", label="f")
        out = self.tex(build)
        assert "\\hyperref[tab:t]{Table~\\ref*{tab:t}} \\hyperref[fig:f]{100\\% this}" in out

    def test_plain_image_caption_unnumbered(self):
        out = self.tex(lambda r: r.image("x.png", alt="Alt"))
        assert "\\caption*{Alt}" in out

    def test_preamble_loads_caption(self):
        assert "\\usepackage{caption}" in report().to_latex()


@requires_pdf
class TestPdf:
    def text(self, r: Report) -> str:
        reader = pypdf.PdfReader(io.BytesIO(r.to_pdf()))
        return "\n".join(page.extract_text() for page in reader.pages)

    def test_figures_captions_and_refs(self, tmp_path):
        png = tmp_path / "a.png"
        png.write_bytes(tiny_png(40, 20))
        r = report()
        r.paragraph(["See ", ref("t"), " and ", ref("f"), "."])
        r.figure(png, caption="From file", label="f", width=0.3)
        r.figure(tiny_png(30, 30), caption="From bytes")
        r.figure(FakePlot(), caption="From plot")
        r.table(["A"], [[["Cell ", ref("f")]]], caption="Literal **stars** -- here", label="t")
        r.figure(tmp_path / "missing.png", caption="Gone")
        text = self.text(r)
        assert "See Table 1 and Figure 1." in text
        for caption in ("Figure 1: From file", "Figure 2: From bytes", "Figure 3: From plot",
                        "Figure 4: Gone", "Table 1: Literal **stars** -- here", "Cell Figure 1"):
            assert caption in re.sub(r"\s+", " ", text)
        assert "[Figure: Gone]" in text

    def test_ref_links_are_internal(self):
        r = report()
        r.paragraph([ref("t")])
        r.table(["A"], [["1"]], caption="C", label="t")
        reader = pypdf.PdfReader(io.BytesIO(r.to_pdf()))
        links = [a.get_object() for a in reader.pages[0].get("/Annots", [])]
        assert any(link.get("/Subtype") == "/Link" and "/Dest" in link for link in links)

    def test_svg_bytes(self):
        r = report()
        r.figure(SVG, caption="Vector")
        assert "Figure 1: Vector" in self.text(r)


class TestMatplotlib:
    plt = None

    @pytest.fixture(autouse=True)
    def _matplotlib(self):
        matplotlib = pytest.importorskip("matplotlib")
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(3, 2))
        ax.plot([1, 3, 2])
        self.fig = fig
        yield
        plt.close(fig)

    def test_all_formats(self, tmp_path):
        r = report()
        r.figure(self.fig, caption="Real plot", label="p")
        r.paragraph([ref("p")])
        r.save_markdown(tmp_path / "r.md")
        r.save_latex(tmp_path / "r.tex")
        assert (tmp_path / "r_files" / "figure-1.png").read_bytes()[:4] == b"\x89PNG"
        assert (tmp_path / "r_files" / "figure-1.pdf").read_bytes()[:4] == b"%PDF"
        assert "data:image/png;base64," in r.to_html()
        if fpdf is not None:
            assert r.to_pdf().startswith(b"%PDF")


class TestImageUnchanged:
    def test_image_still_unnumbered_everywhere(self):
        r = report()
        r.image("x.png", alt="Alt", title="Title")
        r.figure("y.png", caption="Numbered")
        assert "*Figure 1: Numbered*" in r.to_markdown()
        assert isinstance(r.children[0], Image)
