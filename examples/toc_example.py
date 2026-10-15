"""Demo: a multi-level report with a table of contents, exported to every format.

Run from anywhere:

    python examples/toc_example.py

Outputs are written to ``examples/output/``.
"""

from pathlib import Path

from reportsmith import Report, bold, code, italic, link

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)

report = Report(
    "2026 Annual Operations Review",
    author="Operations Team",
    subtitle="Performance, regional results and plans for 2027",
    date="2026-12-15",
)

# The TOC covers the whole report wherever it is placed; depth=3 lists
# top-level sections, their subsections and one level below that.
report.toc(title="Contents", depth=3)

with report.section("Executive Summary") as s:
    s.paragraph(
        [
            "Revenue grew ",
            bold("21%"),
            " year over year while operating costs fell ",
            bold("6%"),
            ". This review covers results by region, the main initiatives "
            "behind them, and priorities for 2027.",
        ]
    )
    s.quote("Our strongest year since the company was founded.")

with report.section("Financial Results") as s:
    s.table(
        ["Metric", "2025", "2026", "Change"],
        [
            ["Revenue", "$41.2M", "$49.9M", "+21%"],
            ["Operating cost", "$30.4M", "$28.6M", "-6%"],
            ["Operating margin", "26%", "43%", "+17 pp"],
        ],
        caption="Year-over-year financial summary",
        align=["left", "right", "right", "right"],
    )

    with s.section("Revenue by Quarter") as q:
        q.table(
            ["Quarter", "Revenue", "Growth"],
            [["Q1", "$11.0M", "+15%"], ["Q2", "$12.1M", "+19%"],
             ["Q3", "$12.9M", "+23%"], ["Q4", "$13.9M", "+26%"]],
            align=["left", "right", "right"],
        )

    with s.section("Cost Breakdown") as c:
        c.bullet_list(
            [
                [bold("Infrastructure"), " — down 18% after the cloud migration"],
                [bold("Staffing"), " — flat; hiring focused on support"],
                [bold("Logistics"), " — down 4% from consolidated shipping"],
            ]
        )

with report.section("Regional Results") as s:
    s.paragraph("Every region grew; APAC grew fastest from a smaller base.")

    for region, growth, note in [
        ("EMEA", "+17%", "Strong enterprise renewals in Germany and the Nordics."),
        ("Americas", "+19%", "Mid-market segment drove most new business."),
        ("APAC", "+34%", "New offices in Singapore and Sydney opened in Q2."),
    ]:
        with s.section(region) as r:
            r.paragraph(["Revenue growth: ", bold(growth), ". ", note])
            with r.section("Outlook") as o:  # depth 3: the deepest level listed
                o.paragraph(f"{region} targets continued growth in 2027.")
                # Depth 4 (an h5): deeper than depth=3, so not in the TOC.
                o.heading("Risks")
                o.paragraph("Currency movements and hiring speed.")

with report.section("Key Initiatives") as s:
    with s.section("Cloud Migration") as m:
        m.paragraph(
            ["All production workloads moved to the new platform; see the ",
             link("migration notes", "https://example.com/migration"), "."]
        )
        m.code("migrate --env production --strategy blue-green", language="bash")
    with s.section("Customer Support Overhaul") as m:
        m.paragraph(["Median first-response time dropped from ",
                     italic("9 hours"), " to ", italic("2 hours"), "."])

with report.section("Priorities for 2027") as s:
    s.numbered_list(
        [
            "Expand APAC sales and support",
            "Launch self-service onboarding",
            ["Cut infrastructure cost a further ", bold("10%")],
        ]
    )

report.horizontal_rule()
report.paragraph([italic("Generated with "), code("reportsmith"), italic(".")])

written = [
    report.save_markdown(OUT / "toc_report.md"),
    report.save_html(OUT / "toc_report.html"),
    report.save_latex(OUT / "toc_report.tex"),  # compile twice to fill in the TOC
]
try:
    written.append(report.save_pdf(OUT / "toc_report.pdf"))
except ImportError:
    print("Skipped PDF export (install with: pip install reportsmith[pdf])")

for path in written:
    print(f"Wrote {path}")
