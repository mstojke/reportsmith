"""Demo: running headers and footers, page numbers and section numbering.

Run from anywhere:

    python examples/pages_example.py

Outputs are written to ``examples/output/``. Open the HTML file and print it
(or "Save as PDF") in Chrome or Edge to see the header and footer there.
"""

from pathlib import Path

from reportsmith import Report, ref

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)

report = Report(
    "Annual Operations Review",
    author="Operations Team",
    date="2026-11-03",
    header=("{title}", "", "{date}"),  # left, centre, right; not on page 1
    footer=("{author}", "Page {page} of {pages}", "Internal"),
    section_numbers=True,  # "1", "1.1", "1.1.1"
)
report.toc(depth=2)
report.paragraph(
    ["This review follows the plan in ", ref("plan"), "; results are in ", ref("results"), "."]
)

with report.section("Plan", label="plan") as s:
    s.paragraph("Goals agreed at the start of the year.")
    with s.section("Targets") as t:
        t.bullet_list(["Grow revenue 15%", "Cut costs 5%", "Open two offices"])
    with s.section("Risks") as t:
        t.paragraph("Hiring speed and currency movements.")

with report.section("Results", label="results") as s:
    for region in ("EMEA", "Americas", "APAC"):
        with s.section(region) as r:
            for i in range(6):
                r.paragraph(
                    f"{region} update {i + 1}: revenue, costs and hiring all tracked against "
                    "the targets set in the plan, with notes on what changed during the quarter."
                )

with report.section("Next Year") as s:
    s.paragraph(["Targets for next year build on ", ref("results"), "."])

for name in ("pages_report.md", "pages_report.html", "pages_report.tex", "pages_report.pdf"):
    try:
        print(f"Wrote {report.save(OUT / name)}")
    except ImportError:
        print("Skipped PDF export (install with: pip install reportsmith[pdf])")
