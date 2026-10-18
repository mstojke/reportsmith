"""Demo: callouts, strikethrough, sub/superscript and footnotes.

Run from anywhere:

    python examples/callouts_example.py

Outputs are written to ``examples/output/``.
"""

from pathlib import Path

from reportsmith import Report, bold, code, footnote, strike, sub, sup

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)

report = Report(
    "Lab Facility Upgrade",
    author="Facilities Team",
    subtitle="Callouts and inline styles demo",
    date="2026-12-15",
)

report.callout(
    "note",
    ["This report covers the ", bold("Building C"), " upgrade only.",
     footnote("Buildings A and B are covered in last year's report.")],
)

with report.section("Results") as s:
    s.paragraph(
        [
            "Ventilation now holds CO", sub("2"), " below 800 ppm in every lab, "
            "across 1,240 m", sup("2"), " of floor space.",
            footnote("Measured hourly over four weeks in November."),
        ]
    )
    s.paragraph(
        ["The final cost was ", strike("$1.4M"), " ", bold("$1.25M"),
         ", below the approved budget."]
    )
    s.callout("tip", ["Live sensor readings are on the ", code("facilities"), " dashboard."])

    s.table(
        ["Metric", "Before", "After"],
        [
            [["CO", sub("2"), " (ppm)"], "1,150", "760"],
            [["Energy (kWh/m", sup("2"), ")"], "212", ["174", footnote("Weather-adjusted.")]],
        ],
        caption="Before and after the upgrade",
        align=["left", "right", "right"],
    )

with report.section("Next Steps") as s:
    with s.callout("important", title="Decisions needed by 31 January") as c:
        c.numbered_list(["Approve the Building D survey", "Choose the filter supplier"])

    with s.callout("warning") as c:
        c.paragraph("Labs C2 and C3 close for filter replacement in week 6:")
        c.bullet_list(["Move experiments to C1 beforehand", "Expect noise during the day"])

    s.callout("caution", "Never prop open fire doors to improve airflow.", title="Safety")

written = [
    report.save_markdown(OUT / "callouts_report.md"),
    report.save_html(OUT / "callouts_report.html"),
    report.save_latex(OUT / "callouts_report.tex"),
]
try:
    written.append(report.save_pdf(OUT / "callouts_report.pdf"))
except ImportError:
    print("Skipped PDF export (install with: pip install reportsmith[pdf])")

for path in written:
    print(f"Wrote {path}")
