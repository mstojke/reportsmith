"""Optional syntax highlighting for code blocks, via Pygments.

Pygments is imported lazily and only when a renderer is asked to highlight
(``highlight=True``), so reportsmith keeps working without it. A code block
whose language Pygments doesn't know is rendered as plain text.
"""

from __future__ import annotations

from typing import Any, Optional

#: Pygments styles: light matches the default page colours, dark the dark theme.
LIGHT_STYLE = "default"
DARK_STYLE = "github-dark"

# CSS selector the highlighted spans are scoped to.
_SCOPE = "pre code"


def require_pygments() -> None:
    try:
        import pygments  # noqa: F401
    except ImportError:
        raise ImportError(
            "Syntax highlighting requires the optional dependency Pygments. "
            "Install it with: pip install reportsmith[highlight]"
        ) from None


def lexer_for(language: str) -> Optional[Any]:
    """The Pygments lexer for a language name, or None if unknown/empty."""
    if not language:
        return None
    from pygments.lexers import get_lexer_by_name
    from pygments.util import ClassNotFound

    try:
        return get_lexer_by_name(language)
    except ClassNotFound:
        return None


def html_spans(source: str, language: str) -> Optional[str]:
    """Escaped HTML of ``source`` with ``<span class="...">`` tokens, or None."""
    lexer = lexer_for(language)
    if lexer is None:
        return None
    from pygments import highlight
    from pygments.formatters import HtmlFormatter

    html = highlight(source, lexer, HtmlFormatter(nowrap=True))
    # Pygments adds a trailing newline; keep the block's own ending instead.
    return html[:-1] if html.endswith("\n") and not source.endswith("\n") else html


def _css_rules(style: str) -> str:
    from pygments.formatters import HtmlFormatter
    from pygments.styles import get_all_styles

    if style not in set(get_all_styles()):
        style = "monokai"  # older Pygments without github-dark
    css = HtmlFormatter(style=style, nobackground=True).get_style_defs(_SCOPE)
    # Keep only token rules scoped to code blocks (Pygments also emits
    # page-wide `pre`/line-number rules) and drop the red "error" box.
    keep = [
        line for line in css.splitlines()
        if line.startswith(_SCOPE + " .") and not line.startswith(_SCOPE + " .err ")
    ]
    return "\n".join(keep) + "\n"


def html_css(theme: str) -> str:
    """Token colours for a page theme: ``"auto"``, ``"light"`` or ``"dark"``.

    Print always uses the light colours, matching the print stylesheet.
    """
    light, dark = _css_rules(LIGHT_STYLE), _css_rules(DARK_STYLE)
    if theme == "light":
        return light
    if theme == "dark":
        return f"@media screen {{\n{dark}}}\n@media print {{\n{light}}}\n"
    return f"{light}@media screen and (prefers-color-scheme: dark) {{\n{dark}}}\n"


def latex_block(source: str, language: str, verbatim_options: str) -> Optional[str]:
    """A highlighted ``Verbatim`` environment for LaTeX, or None."""
    lexer = lexer_for(language)
    if lexer is None:
        return None
    from pygments import highlight
    from pygments.formatters import LatexFormatter

    return highlight(source, lexer, LatexFormatter(style=LIGHT_STYLE, verboptions=verbatim_options))


def latex_style_defs() -> str:
    """The ``\\PY`` macro definitions highlighted LaTeX blocks need."""
    from pygments.formatters import LatexFormatter

    return LatexFormatter(style=LIGHT_STYLE).get_style_defs()


def pdf_tokens(source: str, language: str) -> Optional[list[tuple[str, Optional[tuple[int, int, int]], str]]]:
    """``(text, rgb or None, font style)`` runs for PDF output, or None."""
    lexer = lexer_for(language)
    if lexer is None:
        return None
    from pygments import lex
    from pygments.styles import get_style_by_name

    style = get_style_by_name(LIGHT_STYLE)
    runs = []
    for token_type, text in lex(source, lexer):
        info = style.style_for_token(token_type)
        color = info["color"]
        rgb = (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)) if color else None
        font_style = ("B" if info["bold"] else "") + ("I" if info["italic"] else "")
        runs.append((text, rgb, font_style))
    if runs and runs[-1][0].endswith("\n") and not source.endswith("\n"):
        # The lexer adds a final newline the source didn't have.
        text, rgb, font_style = runs[-1]
        runs[-1] = (text[:-1], rgb, font_style)
    return runs
