"""Tests for translated built-in labels."""

import io

import pytest

from reportsmith import Report, footnote, math, ref
from reportsmith.labels import ENGLISH, TRANSLATIONS, labels_for, language_labels

try:
    import fpdf
except ImportError:
    fpdf = None
try:
    import pypdf
except ImportError:
    pypdf = None

requires_pdf = pytest.mark.skipif(fpdf is None or pypdf is None, reason="fpdf2 and pypdf needed")


def report(language="pl", **kwargs) -> Report:
    r = Report("Raport", author="Zespół", date="2026-11-05", language=language, **kwargs)
    r.toc()
    with r.section("Wyniki", label="wyniki") as s:
        s.paragraph(["Zobacz ", ref("tab"), ", ", ref("eq"), " i ", ref("wyniki"), ".", footnote("Przypis.")])
        s.table(["A"], [["1"]], caption="Dane", label="tab")
        s.equation("x = 1", label="eq")
        s.callout("warning", "Uwaga na dane.")
        s.callout("tip", "Własny tytuł.", title="Rada")
    return r


class TestTables:
    def test_every_language_has_every_key(self):
        for language, labels in TRANSLATIONS.items():
            assert set(labels) == set(ENGLISH), language
            assert all(isinstance(v, str) and v for v in labels.values()), language

    @pytest.mark.parametrize("tag, figure", [
        ("pl", "Rysunek"), ("de-CH", "Abbildung"), ("pt_BR", "Figura"), ("FR", "Figure"),
        ("en-GB", "Figure"), ("ja", "Figure"), ("", "Figure"),
    ])
    def test_language_tags(self, tag, figure):
        assert language_labels(tag)["figure"] == figure

    def test_overrides(self):
        r = Report("T", language="de", labels={"figure": "Abb."})
        labels = labels_for(r)
        assert labels["figure"] == "Abb." and labels["table"] == "Tabelle"

    def test_unknown_key(self):
        with pytest.raises(ValueError, match="Unknown label 'fig'"):
            Report("T", labels={"fig": "Fig."})

    def test_non_string_value(self):
        with pytest.raises(TypeError, match="must be a string"):
            Report("T", labels={"figure": 1})  # type: ignore[dict-item]

    def test_overrides_are_copied(self):
        overrides = {"figure": "Fig."}
        r = Report("T", labels=overrides)
        overrides["figure"] = "changed"
        assert r.labels == {"figure": "Fig."}


class TestMarkdown:
    def test_polish(self):
        md = report().to_markdown()
        assert "**Autor:** Zespół  \n**Data:** 2026-11-05" in md
        assert "**Spis treści**" in md
        assert "Zobacz Tabela 1, Równanie 1 i Wyniki." in md
        assert "*Tabela 1: Dane*" in md

    def test_english_unchanged(self):
        md = report(language="en").to_markdown()
        assert "**Author:** Zespół" in md and "**Contents**" in md and "Table 1" in md

    def test_explicit_toc_title_wins(self):
        r = Report("T", language="pl")
        r.toc(title="Contents")
        r.section("A")
        assert "**Contents**" in r.to_markdown()
        r = Report("T", language="pl")
        r.toc(title="")
        r.section("A")
        assert "Spis" not in r.to_markdown()


class TestHtml:
    def test_polish(self):
        html = report().to_html()
        assert "<strong>Autor:</strong> Zespół" in html and "<strong>Data:</strong>" in html
        assert '<nav class="toc" aria-label="Spis treści">' in html
        assert '<div class="toc-title">Spis treści</div>' in html
        assert '<span class="caption-label">Tabela 1:</span> Dane' in html
        assert 'class="ref">Równanie 1</a>' in html
        assert '<p class="callout-title">Ostrzeżenie</p>' in html
        assert '<p class="callout-title">Rada</p>' in html
        assert 'aria-label="Powrót do odwołania 1"' in html
        assert '<html lang="pl">' in html

    def test_override_escaped(self):
        html = Report("T", labels={"author": "<A>"}, author="X").to_html()
        assert "<strong>&lt;A&gt;:</strong>" in html


class TestLatex:
    def test_polish(self):
        tex = report().to_latex()
        assert "\\renewcommand{\\figurename}{Rysunek}" in tex
        assert "\\renewcommand{\\tablename}{Tabela}" in tex
        assert "\\renewcommand{\\contentsname}{Spis treści}" in tex
        assert "{\\renewcommand{\\contentsname}{Spis treści}\\setcounter{tocdepth}" in tex
        assert "\\hyperref[tab:tab]{Tabela~\\ref*{tab:tab}}" in tex
        assert "\\hyperref[eq:eq]{Równanie~\\ref*{eq:eq}}" in tex
        assert "\\begin{rscallout}{rswarning}{Ostrzeżenie}" in tex

    def test_names_escaped(self):
        tex = Report("T", labels={"figure": "Fig_1 & co"}).to_latex()
        assert "\\renewcommand{\\figurename}{Fig\\_1 \\& co}" in tex

    def test_remote_image_placeholder(self):
        r = Report("T", language="de")
        r.image("https://example.com/a.png", alt="Logo")
        assert "{[Bild: Logo]}" in r.to_latex(full_document=False)

    def test_fragment_has_no_name_commands(self):
        assert "figurename" not in report().to_latex(full_document=False)


@requires_pdf
class TestPdf:
    def text(self, r: Report) -> str:
        reader = pypdf.PdfReader(io.BytesIO(r.to_pdf()))
        return "\n".join(p.extract_text() for p in reader.pages)

    def test_polish(self):
        text = self.text(report())
        assert "Spis treści" in text
        assert "Tabela 1: Dane" in text
        assert "Zobacz Tabela 1, Równanie 1 i Wyniki." in text
        assert "Ostrzeżenie" in text and "Rada" in text
        assert "Przypisy" in text and "Notes" not in text

    def test_bookmark_for_notes(self):
        reader = pypdf.PdfReader(io.BytesIO(report().to_pdf()))
        titles = [item.title for item in reader.outline if not isinstance(item, list)]
        assert "Przypisy" in titles

    def test_missing_figure_placeholder(self, tmp_path):
        r = Report("T", language="de")
        r.figure(tmp_path / "missing.png", alt="Plan")
        assert "[Abbildung: Plan]" in self.text(r)


def test_math_and_labels_together():
    r = Report("T", language="fr")
    r.equation(r"E = mc^2", label="e")
    r.paragraph([ref("e"), " ", math("x")])
    assert "Équation 1 $x$" in r.to_markdown()
