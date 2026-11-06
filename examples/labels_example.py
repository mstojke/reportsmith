"""Demo: built-in labels in the report's language (here Polish).

Run from anywhere:

    python examples/labels_example.py

Outputs are written to ``examples/output/``. ``language="pl"`` turns
"Figure", "Table", "Contents", "Note", "Author" and the rest into Polish;
``labels=`` overrides single labels, here calling sections "Rozdział".
"""

from pathlib import Path

from reportsmith import Report, footnote, ref

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)

report = Report(
    "Raport kwartalny",
    subtitle="Sprzedaż w III kwartale 2026",
    author="Dział analiz",
    date="2026-11-05",
    language="pl",
    labels={"section": "Rozdział"},
    section_numbers=True,
    footer=("{title}", "", "{page} / {pages}"),
)
report.toc(depth=2)

with report.section("Podsumowanie", label="podsumowanie") as s:
    s.paragraph([
        "Przychody wzrosły o 12% (", ref("przychody"), "), a marża zgodnie z ", ref("marza"),
        " wyniosła 31%.", footnote("Dane wstępne, przed audytem."),
    ])
    s.callout("note", "Wyniki obejmują wszystkie trzy regiony.")

with report.section("Wyniki") as s:
    s.table(
        ["Region", "Przychody", "Zmiana"],
        [["Europa", "4,2 mln zł", "+9%"], ["Ameryka", "3,1 mln zł", "+15%"], ["Azja", "2,4 mln zł", "+14%"]],
        caption="Przychody według regionów",
        label="przychody",
        align=["left", "right", "right"],
    )
    s.equation(r"m = \frac{P - K}{P}", label="marza")
    s.callout("warning", ["Szczegóły w ", ref("podsumowanie"), "."])

for name in ("labels_report.md", "labels_report.html", "labels_report.tex", "labels_report.pdf", "labels_report.docx"):
    try:
        path = report.save(OUT / name)
    except ImportError:
        print(f"Skipped {name} (install with: pip install reportsmith[pdf])")
    else:
        print(f"Wrote {path}")
