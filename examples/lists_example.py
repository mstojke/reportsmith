"""Demo: definition lists, task lists, page breaks and report.save().

Run from anywhere:

    python examples/lists_example.py

Outputs are written to ``examples/output/``.
"""

from pathlib import Path

from reportsmith import Report, bold, code, link

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)

report = Report(
    "Release 1.0 Readiness",
    author="Platform Team",
    subtitle="Definition lists, task lists and page breaks",
    date="2026-10-22",
)

with report.section("Status") as s:
    s.paragraph(["Four of six launch tasks are done; ", bold("two remain"), " before the release."])
    s.task_list(
        [
            (True, "Freeze the public API"),
            (True, ["Publish the docs to ", link("Read the Docs", "https://reportsmith.readthedocs.io")]),
            (True, "Run the full CI matrix on Python 3.9-3.14"),
            (True, "Write the migration guide"),
            (False, ["Tag ", code("v1.0.0"), " and publish to PyPI"]),
            (False, "Announce the release"),
        ]
    )

report.page_break()  # the glossary starts on its own page in PDF and LaTeX

with report.section("Glossary") as s:
    s.definition_list(
        [
            ("API freeze", "No breaking changes to public names or signatures until the release."),
            ("CI matrix", ["Test runs on every supported Python version, plus ", code("ruff"), " and ", code("mypy"), "."]),
            ("Migration guide", "Steps for moving existing reports from 0.x to 1.0."),
        ]
    )
    s.definition_list({"RC": "Release candidate", "GA": "General availability"})

# save() picks the format from each file's extension.
for name in ("lists_report.md", "lists_report.html", "lists_report.tex", "lists_report.pdf"):
    try:
        print(f"Wrote {report.save(OUT / name)}")
    except ImportError:
        print("Skipped PDF export (install with: pip install reportsmith[pdf])")
