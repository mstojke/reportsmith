# Sphinx configuration for the reportsmith documentation.
# Build with:  python -m sphinx -b html docs docs/_build/html

project = "reportsmith"
author = "Michal Stojke"
release = "0.1.0"

# myst_parser lets Sphinx read the Markdown user guide alongside the rst files.
extensions = ["myst_parser"]

# Auto-generate GitHub-style anchors for headings so the user guide's
# in-page #links work in Sphinx as well as on GitHub.
myst_heading_anchors = 3

source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
exclude_patterns = ["_build"]

html_theme = "sphinx_rtd_theme"
html_title = "reportsmith documentation"
