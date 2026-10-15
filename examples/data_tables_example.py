"""Demo: tables built straight from data — dicts, a CSV file and a DataFrame.

Run from anywhere:

    python examples/data_tables_example.py

Outputs are written to ``examples/output/``. The DataFrame section is
skipped when pandas is not installed.
"""

from pathlib import Path

from reportsmith import Report, bold

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
OUT.mkdir(exist_ok=True)

report = Report(
    "Store Performance Review",
    author="Retail Analytics",
    subtitle="Tables built from records, CSV and pandas",
    date="2026-12-15",
)
report.toc(depth=1)

# -- From a list of dicts -------------------------------------------------
regions = [
    {"region": "EMEA", "revenue": 436_771.25, "growth": 0.084, "stores": 3},
    {"region": "Americas", "revenue": 278_866.1, "growth": 0.121, "stores": 2},
    {"region": "APAC", "revenue": None, "growth": None, "stores": 0, "note": "opening Q2"},
]

with report.section("Regional Summary") as s:
    s.paragraph("Built with table_from_records(): dict keys become the columns.")
    s.table_from_records(
        regions,
        headers={"region": "Region", "revenue": "Revenue", "growth": "YoY growth",
                 "stores": "Stores", "note": "Note"},
        formats={
            "revenue": "${:,.0f}",
            "growth": "{:+.1%}",
            "region": bold,  # callables may return inline formatting
        },
        missing="—",
        caption="Revenue and growth by region",
    )

# -- From a CSV file ------------------------------------------------------
with report.section("Store Details") as s:
    s.paragraph(
        "Built with table_from_csv(). Store IDs and ZIP codes keep their "
        "leading zeros; numeric columns are parsed and right-aligned."
    )
    s.table_from_csv(
        HERE / "data" / "stores.csv",
        ["store_id", "city", "zip", "revenue", "orders", "return_rate"],
        headers=["Store", "City", "ZIP", "Revenue", "Orders", "Returns"],
        formats={"revenue": "${:,.2f}", "orders": "{:,}", "return_rate": "{:.1%}"},
        missing="n/a",
        caption="Per-store results (from examples/data/stores.csv)",
    )

# -- From a pandas DataFrame ----------------------------------------------
try:
    import pandas as pd
except ImportError:
    pd = None

if pd is not None:
    stores = pd.read_csv(HERE / "data" / "stores.csv", dtype={"store_id": str, "zip": str})
    stores["revenue_per_order"] = stores["revenue"] / stores["orders"]
    top = stores.nlargest(3, "revenue").set_index("city")

    with report.section("Top Stores") as s:
        s.paragraph("Built with table_from_dataframe(), using the index as the first column.")
        s.table_from_dataframe(
            top,
            ["revenue", "orders", "revenue_per_order"],
            index=True,
            headers={"city": "City", "revenue": "Revenue", "orders": "Orders",
                     "revenue_per_order": "Revenue / order"},
            formats={"revenue": "${:,.0f}", "orders": "{:,}", "revenue_per_order": "${:.2f}"},
            caption="Three highest-revenue stores",
        )

written = [
    report.save_markdown(OUT / "data_tables_report.md"),
    report.save_html(OUT / "data_tables_report.html"),
    report.save_latex(OUT / "data_tables_report.tex"),
]
try:
    written.append(report.save_pdf(OUT / "data_tables_report.pdf"))
except ImportError:
    print("Skipped PDF export (install with: pip install reportsmith[pdf])")

for path in written:
    print(f"Wrote {path}")
