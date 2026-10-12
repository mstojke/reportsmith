"""Demo: build a sample report and export it to Markdown and HTML."""

from reportsmith import ListElement, Report, bold, code, italic, link

report = Report(
    "Q3 2026 Engineering Report",
    author="Michal Stojke",
    subtitle="Platform team quarterly summary",
)

with report.section("Executive Summary") as s:
    s.paragraph(
        [
            "The platform team shipped ",
            bold("14 features"),
            " this quarter while reducing infrastructure spend by ",
            bold("18%"),
            ". Details below; raw dashboards are available ",
            link("here", "https://example.com/dashboards"),
            ".",
        ]
    )
    s.quote("Best quarter for platform reliability since 2024.")

with report.section("Key Metrics") as s:
    s.table(
        ["Metric", "Q2", "Q3", "Change"],
        [
            ["Uptime", "99.92%", "99.98%", "+0.06 pp"],
            ["p95 latency", "410 ms", "290 ms", "-29%"],
            ["Monthly cost", "$48k", "$39k", "-18%"],
        ],
        caption="Quarter-over-quarter platform metrics",
        align=["left", "right", "right", "right"],
    )

with report.section("Highlights") as s:
    s.bullet_list(
        [
            [bold("New deploy pipeline"), " — rollouts now take 4 minutes"],
            ["Migrated the job queue to ", code("redis-streams")],
            ListElement(["Zero-downtime cutover", "Old queue decommissioned"]),
            [italic("Docs overhaul"), " for internal APIs"],
        ]
    )

    with s.section("Deploy pipeline") as sub:
        sub.paragraph("The new pipeline is configured with a single manifest:")
        sub.code(
            'pipeline:\n  stages: [build, test, canary, rollout]\n  canary_traffic: "5%"',
            language="yaml",
        )

report.horizontal_rule()
report.paragraph([italic("Generated with the "), code("reportsmith"), italic(" library.")])

md_path = report.save_markdown("example_report.md")
html_path = report.save_html("example_report.html")
tex_path = report.save_latex("example_report.tex")
print(f"Wrote {md_path}, {html_path} and {tex_path}")

try:
    pdf_path = report.save_pdf("example_report.pdf")
    print(f"Wrote {pdf_path}")
except ImportError:
    print("Skipped PDF export (install with: pip install reportsmith[pdf])")
