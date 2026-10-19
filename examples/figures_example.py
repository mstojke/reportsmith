"""Demo: figures from matplotlib, numbered captions and cross-references.

Run from anywhere (needs matplotlib):

    python examples/figures_example.py

Outputs are written to ``examples/output/``. Markdown and LaTeX get their
chart images in a ``*_files/`` folder next to them; HTML and PDF embed them.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # render without a display
import matplotlib.pyplot as plt  # noqa: E402

from reportsmith import Report, bold, italic, link, ref, strike  # noqa: E402

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)

months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
revenue = [1.8, 2.1, 2.0, 2.6, 2.9, 3.4]
regions = {"EMEA": 6.1, "Americas": 5.2, "APAC": 3.5}

trend, ax = plt.subplots(figsize=(6, 2.8))
ax.plot(months, revenue, marker="o", color="#1d4ed8")
ax.set_ylabel("Revenue ($M)")
ax.grid(alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)

split, ax = plt.subplots(figsize=(4, 2.6))
ax.bar(list(regions), list(regions.values()), color=["#1d4ed8", "#15803d", "#b45309"])
ax.set_ylabel("Revenue ($M)")
ax.spines[["top", "right"]].set_visible(False)

report = Report(
    "H1 Revenue Review",
    author="Finance Team",
    subtitle="Figures, numbered captions and cross-references",
    date="2026-10-19",
)

with report.section("Summary") as s:
    s.paragraph(
        [
            "Revenue rose every quarter, reaching $3.4M in June (",
            ref("trend"), "). EMEA remains the largest region (",
            ref("regions"), " and ", ref("split", "the regional chart"), ").",
        ]
    )

with report.section("Monthly Trend") as s:
    s.figure(trend, caption="Monthly revenue, January to June", label="trend", width=0.9)

with report.section("Regions") as s:
    s.table(
        ["Region", "Revenue", "Notes"],
        [
            [bold("EMEA"), "$6.1M", ["Strongest in ", italic("Germany")]],
            [bold("Americas"), "$5.2M", ["Target was ", strike("$5.5M"), " revised to $5.0M"]],
            [bold("APAC"), "$3.5M", ["See the ", link("APAC plan", "https://example.com/apac")]],
        ],
        caption="Revenue by region, H1",
        label="regions",
        align=["left", "right", "left"],
    )
    s.figure(split, caption="Revenue split by region", label="split", width=0.6)

plt.close("all")

written = [
    report.save_markdown(OUT / "figures_report.md"),
    report.save_html(OUT / "figures_report.html"),
    report.save_latex(OUT / "figures_report.tex"),
]
try:
    written.append(report.save_pdf(OUT / "figures_report.pdf"))
except ImportError:
    print("Skipped PDF export (install with: pip install reportsmith[pdf])")

for path in written:
    print(f"Wrote {path}")
