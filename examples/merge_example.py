"""Demo: merging reports, reusable sections, metadata, themes and highlighting.

Run from anywhere (syntax highlighting needs Pygments):

    python examples/merge_example.py

Outputs are written to ``examples/output/``.
"""

from pathlib import Path

from reportsmith import Report, Section, bold, ref

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)


def quarterly(name: str, revenue: str, growth: str) -> Report:
    """A stand-alone quarterly report, as a team might publish it on its own."""
    q = Report(f"{name} Sales Report", date="")
    q.toc()  # skipped when merged: the annual report has its own
    with q.section("Results") as s:
        s.paragraph(["Revenue was ", bold(revenue), f" ({growth}); see ", ref("sales"), "."])
        s.table(
            ["Region", "Revenue"],
            [["EMEA", "$1.4M"], ["Americas", "$1.1M"], ["APAC", "$0.6M"]],
            caption=f"{name} revenue by region",
            label="sales",  # every quarter uses the same label...
            align=["left", "right"],
        )
    with q.section("Data Pipeline") as s:
        s.code(
            "SELECT region, SUM(amount) AS revenue\n"
            "FROM orders\n"
            f"WHERE quarter = '{name}'\n"
            "GROUP BY region;",
            language="sql",
        )
    return q


# A reusable section, built once and added where it is needed.
methodology = Section("Methodology")
methodology.paragraph("Revenue is recognised on delivery; figures are unaudited.")
methodology.heading("Data sources")  # moves with the section
methodology.code('orders = load("warehouse/orders", since="2026-01-01")', language="python")

annual = Report(
    "2026 Sales Review",
    author="Finance Team",
    date="2026-10-22",
    subtitle="Merged from the quarterly reports",
    description="Quarterly sales results for 2026, merged into one report",
    keywords=["sales", "quarterly", "2026"],
    language="en",
)
annual.toc(depth=2)
annual.paragraph(["Q2 grew fastest (", ref("q2-sales"), ")."])
annual.add(methodology)  # becomes a top-level section (h2)

for name, revenue, growth in [("Q1", "$3.1M", "+6%"), ("Q2", "$3.6M", "+16%")]:
    with annual.section(name) as s:
        # ...so the prefix keeps labels and refs unique: "q1-sales", "q2-sales".
        s.extend(quarterly(name, revenue, growth), label_prefix=f"{name.lower()}-")

try:
    import pygments  # noqa: F401

    highlight = True
except ImportError:
    highlight = False
    print("Pygments not installed: code blocks stay plain (pip install reportsmith[highlight])")

written = [
    annual.save(OUT / "merge_report.md", front_matter=True),
    annual.save(OUT / "merge_report.html", highlight=highlight),
    annual.save(OUT / "merge_report_dark.html", theme="dark", highlight=highlight),
    annual.save(OUT / "merge_report.tex", highlight=highlight),
]
try:
    written.append(annual.save(OUT / "merge_report.pdf", highlight=highlight))
except ImportError:
    print("Skipped PDF export (install with: pip install reportsmith[pdf])")

for path in written:
    print(f"Wrote {path}")
