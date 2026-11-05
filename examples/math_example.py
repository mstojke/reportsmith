"""Demo: inline math, numbered display equations and references to them.

Run from anywhere:

    python examples/math_example.py

Outputs are written to ``examples/output/``. Math is written in TeX: LaTeX
typesets it natively, Markdown uses ``$...$`` (rendered by GitHub), and the
HTML page loads MathJax. The PDF typesets display equations with
matplotlib's mathtext when matplotlib is installed, and approximates inline
math in Unicode ("E = mc²").
"""

from pathlib import Path

from reportsmith import Report, math, ref

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)

report = Report("Queueing Model for the Support Desk", author="Operations Research", date="2026-11-05")

with report.section("Model") as s:
    s.paragraph([
        "Tickets arrive at rate ", math(r"\lambda"), " per hour and an agent resolves them at rate ",
        math(r"\mu"), ". With ", math("c"), " agents the utilization is ", ref("utilization"),
        ", and the queue is stable only when ", math(r"\rho < 1"), ".",
    ])
    s.equation(r"\rho = \frac{\lambda}{c\,\mu}", label="utilization")
    s.paragraph([
        "For a single agent (", math("c = 1"), "), the mean number of tickets in the system and the "
        "mean time a ticket spends there follow from Little's law, ", math(r"L = \lambda W"), ":",
    ])
    s.equation(r"L = \frac{\rho}{1 - \rho}, \qquad W = \frac{1}{\mu - \lambda}", label="mm1")

with report.section("Today's numbers") as s:
    s.table(
        ["Quantity", "Symbol", "Value"],
        [
            ["Arrival rate", [math(r"\lambda")], "18 / h"],
            ["Service rate", [math(r"\mu")], "6 / h"],
            ["Agents", [math("c")], "4"],
            ["Utilization", [math(r"\rho")], "0.75"],
        ],
        caption="Inputs to the model",
        align=["left", "center", "right"],
    )
    s.paragraph([
        "At ", math(r"\rho = 0.75"), " the desk has headroom, but ", ref("mm1"),
        " shows how sharply waiting grows as ", math(r"\rho \to 1"), ".",
    ])

with report.section("Variability") as s:
    s.paragraph("The standard deviation of the daily ticket count over n days:")
    s.equation(r"\sigma = \sqrt{\frac{1}{n} \sum_{i=1}^{n} \left(x_i - \bar{x}\right)^2}")

for name in ("math_report.md", "math_report.html", "math_report.tex", "math_report.pdf"):
    try:
        path = report.save(OUT / name)
    except ImportError:
        print(f"Skipped {name} (install with: pip install reportsmith[pdf])")
    else:
        print(f"Wrote {path}")
