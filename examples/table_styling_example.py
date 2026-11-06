"""Demo: table styling — column widths, striped rows, totals footers and
coloured cells, by hand and from data.

Run from anywhere:

    python examples/table_styling_example.py

Outputs are written to ``examples/output/``.
"""

from pathlib import Path

from reportsmith import Cell, Report, bold

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)

report = Report(
    "Regional Scorecard",
    author="Finance Team",
    date="2026-11-04",
    subtitle="Column widths, stripes, totals and coloured cells",
)

with report.section("Scorecard") as s:
    s.paragraph("Growth is green when on target and red when behind; notes flag risks.")
    s.table(
        ["Region", "Revenue", "Growth", "Status"],
        [
            ["EMEA", "$1.42M", Cell("+8.1%", color="green"), "On track"],
            ["Americas", "$1.10M", Cell("-3.6%", color="red", bold=True), Cell("Behind plan", background="amber")],
            ["APAC", "$0.61M", Cell("+21.4%", color="green"), Cell("Ahead", background="green")],
            ["Middle East", "$0.18M", "+0.4%", Cell("New market", color="blue")],
        ],
        caption="Q3 regional scorecard",
        align=["left", "right", "right", "left"],
        widths=[3, 2, 2, 3],
        striped=True,
        footer=["Total", "$3.31M", Cell("+5.9%", color="green"), ""],
    )

monthly = [
    {"month": "Jan", "orders": 1210, "change": 0.042, "returns": 0.031},
    {"month": "Feb", "orders": 1175, "change": -0.029, "returns": 0.027},
    {"month": "Mar", "orders": 1390, "change": 0.183, "returns": 0.052},
    {"month": "Apr", "orders": 1402, "change": 0.009, "returns": 0.024},
    {"month": "May", "orders": 1288, "change": -0.081, "returns": 0.019},
    {"month": "Jun", "orders": 1517, "change": 0.178, "returns": 0.022},
]

with report.section("Monthly Orders") as s:
    s.paragraph(
        ["Built with ", bold("styles="), ": each rule gets the raw value and returns cell options."]
    )
    s.table_from_records(
        monthly,
        headers={"month": "Month", "orders": "Orders", "change": "Change", "returns": "Return rate"},
        formats={"orders": "{:,}", "change": "{:+.1%}", "returns": "{:.1%}"},
        styles={
            "change": lambda v: {"color": "green"} if v > 0 else {"color": "red"},
            "returns": lambda v: {"background": "red", "bold": True} if v > 0.05 else None,
        },
        striped=True,
        footer=["H1", f"{sum(m['orders'] for m in monthly):,}", "", ""],
        caption="Orders by month, with return rates over 5% flagged",
    )

for name in ("table_styling_report.md", "table_styling_report.html", "table_styling_report.tex", "table_styling_report.pdf", "table_styling_report.docx"):
    try:
        print(f"Wrote {report.save(OUT / name)}")
    except ImportError:
        print("Skipped PDF export (install with: pip install reportsmith[pdf])")
