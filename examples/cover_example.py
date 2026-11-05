"""Demo: a cover page with a logo, organization name and confidentiality note.

Run from anywhere:

    python examples/cover_example.py

Outputs are written to ``examples/output/``. The logo is drawn with
matplotlib when it is installed (``pip install matplotlib``); without it,
the cover has no logo. Print the HTML file in Chrome or Edge to see the
cover on a page of its own.
"""

from pathlib import Path

from reportsmith import Cover, Report

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)


def make_logo():
    """A simple logo drawn with matplotlib, or None without it."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    fig, ax = plt.subplots(figsize=(3, 1.2))
    ax.add_patch(plt.Circle((0.6, 0.5), 0.42, color="#1d4ed8"))
    ax.add_patch(plt.Circle((0.6, 0.5), 0.22, color="white"))
    ax.text(1.25, 0.5, "Northwind", va="center", fontsize=22, fontweight="bold", color="#1f2933")
    ax.set_xlim(0, 4.2)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig


report = Report(
    "Market Entry Assessment",
    subtitle="Expanding the logistics network into the Nordics",
    author="Strategy Office",
    date="November 2026",
    footer=("{title}", "", "Page {page} of {pages}"),
    cover=Cover(
        logo=make_logo(),
        logo_width=0.4,
        organization="Northwind Logistics",
        note="Confidential — prepared for the executive board",
    ),
)
report.toc(depth=1)

with report.section("Summary") as s:
    s.paragraph(
        "The Nordic market is mature but underserved in same-day freight. "
        "We recommend a phased entry, starting with a hub in Gothenburg."
    )

with report.section("Market") as s:
    s.table(
        ["Country", "Freight market", "Growth"],
        [["Sweden", "€8.1bn", "3.2%"], ["Norway", "€5.4bn", "2.7%"], ["Denmark", "€4.9bn", "2.9%"],
         ["Finland", "€3.8bn", "2.1%"]],
        caption="Freight market size and annual growth",
        align=["left", "right", "right"],
    )

with report.section("Recommendation") as s:
    s.numbered_list([
        "Open a Gothenburg hub in Q2 2027",
        "Add Oslo and Copenhagen depots in 2028",
        "Review the entry against targets after 18 months",
    ])

for name in ("cover_report.md", "cover_report.html", "cover_report.tex", "cover_report.pdf"):
    try:
        path = report.save(OUT / name)
    except ImportError:
        print(f"Skipped {name} (install with: pip install reportsmith[pdf])")
    else:
        print(f"Wrote {path}")
