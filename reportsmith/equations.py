"""Math support: TeX to Unicode text, and display equations as images.

Math is written in TeX (``math(r"E = mc^2")``, ``equation(r"\\frac{a}{b}")``).
LaTeX, Markdown (``$...$``) and HTML (MathJax) keep the TeX source. Where
TeX can't be typeset — PDF text, plain-text uses such as bookmarks — it is
approximated in Unicode by :func:`tex_to_unicode`. PDF display equations are
typeset with matplotlib's mathtext when it is installed
(:func:`render_equation`).
"""

from __future__ import annotations

import io
import re
import unicodedata
from typing import Optional

_SYMBOLS = {
    # Greek
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ϵ", "varepsilon": "ε",
    "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ",
    "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π", "varpi": "ϖ", "rho": "ρ",
    "varrho": "ϱ", "sigma": "σ", "varsigma": "ς", "tau": "τ", "upsilon": "υ", "phi": "ϕ",
    "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π",
    "Sigma": "Σ", "Upsilon": "Υ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
    # Operators and relations
    "times": "×", "cdot": "·", "div": "÷", "pm": "±", "mp": "∓", "ast": "∗", "star": "⋆",
    "circ": "∘", "bullet": "•", "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "ne": "≠",
    "neq": "≠", "ll": "≪", "gg": "≫", "approx": "≈", "simeq": "≃", "sim": "∼", "cong": "≅",
    "equiv": "≡", "propto": "∝", "in": "∈", "notin": "∉", "ni": "∋", "subset": "⊂",
    "supset": "⊃", "subseteq": "⊆", "supseteq": "⊇", "cup": "∪", "cap": "∩",
    "setminus": "∖", "emptyset": "∅", "varnothing": "∅", "forall": "∀", "exists": "∃",
    "neg": "¬", "lnot": "¬", "wedge": "∧", "land": "∧", "vee": "∨", "lor": "∨",
    "oplus": "⊕", "otimes": "⊗", "perp": "⊥", "parallel": "∥", "mid": "∣",
    # Arrows
    "to": "→", "rightarrow": "→", "leftarrow": "←", "gets": "←", "leftrightarrow": "↔",
    "Rightarrow": "⇒", "Leftarrow": "⇐", "Leftrightarrow": "⇔", "implies": "⇒", "iff": "⇔",
    "mapsto": "↦", "uparrow": "↑", "downarrow": "↓",
    # Big operators and misc
    "sum": "∑", "prod": "∏", "coprod": "∐", "int": "∫", "iint": "∬", "iiint": "∭",
    "oint": "∮", "partial": "∂", "nabla": "∇", "infty": "∞", "hbar": "ℏ", "ell": "ℓ",
    "Re": "ℜ", "Im": "ℑ", "aleph": "ℵ", "angle": "∠", "triangle": "△", "degree": "°",
    "prime": "′", "dots": "…", "ldots": "…", "cdots": "⋯", "vdots": "⋮", "ddots": "⋱",
    "langle": "⟨", "rangle": "⟩", "lfloor": "⌊", "rfloor": "⌋", "lceil": "⌈", "rceil": "⌉",
    "lbrace": "{", "rbrace": "}", "vert": "|", "Vert": "‖", "backslash": "\\",
    "%": "%", "$": "$", "&": "&", "#": "#", "_": "_", "{": "{", "}": "}", "|": "‖",
    # Spacing
    ",": " ", ";": " ", ":": " ", "!": "", " ": " ", "quad": "  ", "qquad": "    ",
    # Delimiter sizing: dropped, the delimiter itself stays
    "left": "", "right": "", "big": "", "Big": "", "bigg": "", "Bigg": "",
    "bigl": "", "bigr": "", "Bigl": "", "Bigr": "", "displaystyle": "", "textstyle": "",
    "limits": "", "nolimits": "",
}
_FUNCTIONS = {
    "sin", "cos", "tan", "cot", "sec", "csc", "arcsin", "arccos", "arctan", "sinh", "cosh",
    "tanh", "log", "ln", "lg", "exp", "max", "min", "sup", "inf", "lim", "limsup", "liminf",
    "det", "dim", "ker", "deg", "gcd", "arg", "Pr", "mod", "bmod",
}
# Commands whose single argument is shown as is.
_TEXT_COMMANDS = {
    "text", "textrm", "textit", "textbf", "mathrm", "mathit", "mathbf", "mathsf", "mathtt",
    "mathcal", "mathbb", "mathfrak", "boldsymbol", "operatorname", "mbox", "hat", "bar",
    "tilde", "vec", "dot", "ddot", "overline", "underline", "widehat", "widetilde",
}
_ACCENTS = {"hat": "\u0302", "bar": "\u0304", "tilde": "\u0303", "vec": "\u20d7",
            "dot": "\u0307", "ddot": "\u0308", "overline": "\u0305"}
_MATHBB = {"R": "ℝ", "N": "ℕ", "Z": "ℤ", "Q": "ℚ", "C": "ℂ", "P": "ℙ", "E": "𝔼"}

_SUPER = str.maketrans("0123456789+-=()ni", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ")
_SUB = str.maketrans("0123456789+-=()aeoxijk", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓᵢⱼₖ")
_SUPER_CHARS = set("0123456789+-=()ni")
_SUB_CHARS = set("0123456789+-=()aeoxijk")

#: Unicode super/subscript characters spelled out, for fonts that lack them.
SCRIPT_FALLBACK = {
    **{sup: f"^{c}" for c, sup in zip("0123456789+-=()ni", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ")},
    **{sub: f"_{c}" for c, sub in zip("0123456789+-=()aeoxijk", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓᵢⱼₖ")},
}
_ASCII = {"≤": "<=", "≥": ">=", "≠": "!=", "≈": "~", "∼": "~", "→": "->", "←": "<-",
          "↔": "<->", "⇒": "=>", "⇐": "<=", "⇔": "<=>", "′": "'", "…": "...", "⋯": "...",
          "∗": "*", "∣": "|", "‖": "||", "⟨": "<", "⟩": ">"}
# Other symbols fall back to their TeX names ("π" -> "pi").
_NAMES = {char: name for name, char in reversed(list(_SYMBOLS.items())) if len(name) > 1 and len(char) == 1}

_TOKEN = re.compile(r"\\([A-Za-z]+|.)|([{}^_])|(\s+)|(.)", re.S)


class _Parser:
    def __init__(self, tex: str):
        self.tokens = [m for m in _TOKEN.finditer(tex)]
        self.i = 0

    def peek(self) -> Optional[re.Match]:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def next(self) -> Optional[re.Match]:
        tok = self.peek()
        self.i += 1
        return tok

    def group(self) -> str:
        """One argument: a braced group, a command, or a single character."""
        while (tok := self.peek()) is not None and tok.group(3):
            self.i += 1  # skip spaces before an argument
        tok = self.next()
        if tok is None:
            return ""
        if tok.group(2) == "{":
            return self.until_close()
        return self.atom(tok)

    def optional(self) -> str:
        """An optional ``[...]`` argument, if present."""
        tok = self.peek()
        if tok is None or tok.group(0) != "[":
            return ""
        self.i += 1
        out = []
        while (tok := self.next()) is not None and tok.group(0) != "]":
            out.append(self.atom(tok))
        return "".join(out)

    def until_close(self) -> str:
        out = []
        while (tok := self.next()) is not None:
            if tok.group(2) == "}":
                break
            out.append(self.atom(tok))
        return "".join(out)

    def run(self) -> str:
        out = []
        while (tok := self.next()) is not None:
            out.append(self.atom(tok))
        return "".join(out)

    def atom(self, tok: re.Match) -> str:
        command, special, space, char = tok.groups()
        if space is not None:
            return " "
        if char is not None:
            return {"'": "′", "&": " "}.get(char, char)
        if special == "{":
            return self.until_close()
        if special == "}":
            return ""
        if special in ("^", "_"):
            return _script(self.group(), superscript=special == "^")
        return self.command(command)

    def command(self, name: str) -> str:
        if name == "frac" or name in ("dfrac", "tfrac"):
            num, den = self.group(), self.group()
            return f"{_wrap(num)}/{_wrap(den)}"
        if name == "sqrt":
            index = self.optional()
            body = self.group()
            root = {"3": "∛", "4": "∜"}.get(index, (index.translate(_SUPER) if index else "") + "√")
            return root + (body if len(body) == 1 else f"({body})")
        if name in ("binom", "tbinom", "dbinom"):
            n, k = self.group(), self.group()
            return f"C({n}, {k})"
        if name == "mathbb":
            body = self.group()
            return "".join(_MATHBB.get(c, c) for c in body)
        if name in _ACCENTS:
            body = self.group()
            return body + _ACCENTS[name] if len(body) == 1 else body
        if name in _TEXT_COMMANDS:
            return self.group()
        if name in ("begin", "end"):
            self.group()  # environment name: matrices etc. aren't approximated
            return " "
        if name == "\\":
            return "; "
        if name in _FUNCTIONS:
            following = self.peek()
            # "\sin\theta" reads "sin θ", but "\sin(x)" stays "sin(x)".
            if following is not None and (following.group(1) or (following.group(4) or "").isalpha()):
                return name + " "
            return name
        if name in _SYMBOLS:
            return _SYMBOLS[name]
        return name  # unknown command: its name is the best guess


def _wrap(text: str) -> str:
    """Parenthesize a fraction's numerator/denominator when it has operators."""
    return f"({text})" if any(c in " +-=/·×±,<>≤≥" for c in text) else text


def _script(text: str, superscript: bool) -> str:
    chars, table = (_SUPER_CHARS, _SUPER) if superscript else (_SUB_CHARS, _SUB)
    if text and all(c in chars for c in text):
        return text.translate(table)
    if superscript and text in ("′", "′′"):
        return text
    mark = "^" if superscript else "_"
    return f"{mark}{text}" if len(text) == 1 else f"{mark}({text})"


def tex_to_unicode(tex: str) -> str:
    """Approximate TeX math as Unicode text, e.g. ``r"\\alpha^2 \\le \\frac{x}{2}"``
    becomes ``"α² ≤ x/2"``. Used where math can't be typeset."""
    text = re.sub(r" {2,}", " ", _Parser(tex).run())
    return text.replace(" ;", ";").strip()


def to_latin1(text: str) -> str:
    """Spell out the characters of Unicode math text that Latin-1 lacks:
    ``"α ≤ x̄ᵢ"`` becomes ``"alpha <= x_i"``. Characters Latin-1 has (², ±,
    ×, ·) are kept. For fonts limited to Latin-1, such as the PDF core fonts."""
    out = []
    for c in text:
        if ord(c) < 256:
            out.append(c)
        elif c in SCRIPT_FALLBACK:
            out.append(SCRIPT_FALLBACK[c] if c not in "¹²³" else c)
        elif c in _ASCII:
            out.append(f" {_ASCII[c]} ")
        elif unicodedata.combining(c):
            continue  # accents (x̄, v⃗): the base letter stays
        elif c in _NAMES:
            out.append(f" {_NAMES[c]} ")
        elif c in _MATHBB.values():
            out.append(next(k for k, v in _MATHBB.items() if v == c))
        else:
            out.append("?")
    text = re.sub(r" {2,}", " ", "".join(out)).strip()
    # "( alpha )" -> "(alpha)"
    return re.sub(r"([(\[]) | ([)\]])", lambda m: m.group(1) or m.group(2), text)


def tex_to_ascii(tex: str) -> str:
    """Math as plain ASCII, with the TeX markup removed: ``r"\\alpha \\le
    \\frac{x}{2}"`` becomes ``"alpha le fracx2"``. For text that can't hold
    Unicode symbols (PDF core fonts, pdfLaTeX bookmarks)."""
    text = re.sub(r"\\([A-Za-z]+)", r"\1", tex)
    return " ".join(re.sub(r"[{}\\$]", "", text).split())


def render_equation(tex: str, size: float = 12, dpi: int = 300) -> Optional[tuple[bytes, float, float]]:
    """Typeset a display equation with matplotlib's mathtext.

    Returns ``(png_bytes, width_pt, height_pt)``, or ``None`` when matplotlib
    isn't installed or mathtext can't parse the TeX. mathtext sets one line
    of math; multi-line environments (``aligned``, ``cases``, ``matrix``,
    ``pmatrix``, ``array``, ``gathered``, ...) and ``\\\\`` line breaks are
    set cell by cell and assembled into a grid, with delimiters drawn to
    its height.
    """
    try:
        import matplotlib  # noqa: F401
        from PIL import Image  # noqa: F401 (matplotlib depends on Pillow)
    except ImportError:
        return None
    try:
        image = _layout(tex, size, dpi)
    except _Unsupported:
        return None
    if image is None:
        return None
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue(), image.width * 72 / dpi, image.height * 72 / dpi


class _Unsupported(Exception):
    """TeX that mathtext can't set."""


_BEGIN = re.compile(r"\\begin\{([A-Za-z]+\*?)\}")
_LEFT_BEFORE = re.compile(r"\\left\s*(\\[A-Za-z]+|\\.|.)\s*$")
_RIGHT_AFTER = re.compile(r"\s*\\right\s*(\\[A-Za-z]+|\\.|.)")  # used with match(text, pos)
_DELIMITERS = {"(": "(", ")": ")", "[": "[", "]": "]", "|": "|", "\\|": "‖", "\\{": "{", "\\}": "}",
               "\\lbrace": "{", "\\rbrace": "}", "\\langle": "⟨", "\\rangle": "⟩", "\\vert": "|",
               "\\Vert": "‖", "\\lvert": "|", "\\rvert": "|", ".": ""}
_ENV_DELIMITERS = {"pmatrix": ("(", ")"), "bmatrix": ("[", "]"), "Bmatrix": ("{", "}"),
                   "vmatrix": ("|", "|"), "Vmatrix": ("‖", "‖"), "cases": ("{", ""), "dcases": ("{", "")}


def _split_top(text: str, separator: str) -> list[str]:
    """Split on a separator (``&`` or ``\\\\``) outside braces and nested
    environments."""
    parts, depth, env, start, i = [], 0, 0, 0, 0
    while i < len(text):
        if text.startswith("\\begin{", i):
            env += 1
        elif text.startswith("\\end{", i):
            env -= 1
        c = text[i]
        if c == "\\" and i + 1 < len(text) and text[i + 1] in "{}&" and separator != "\\\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif depth == 0 and env == 0 and text.startswith(separator, i):
            if separator == "&" and i > 0 and text[i - 1] == "\\":
                i += 1
                continue
            parts.append(text[start:i])
            i += len(separator)
            start = i
            continue
        i += 1 if c != "\\" else 2
    parts.append(text[start:])
    return parts


def _segments(tex: str) -> list[tuple]:
    """Top-level pieces: ``("tex", source)`` and ``("env", name, spec, body,
    left, right)`` for each environment (with any ``\\left``/``\\right``
    delimiters around it)."""
    out: list[tuple] = []
    pos = 0
    while (match := _BEGIN.search(tex, pos)) is not None:
        name = match.group(1)
        # Find the matching \end{name}, allowing nested environments.
        depth, i = 1, match.end()
        while depth:
            nxt_begin = tex.find("\\begin{", i)
            nxt_end = tex.find("\\end{", i)
            if nxt_end < 0:
                raise _Unsupported(name)
            if 0 <= nxt_begin < nxt_end:
                depth, i = depth + 1, nxt_begin + 7
            else:
                depth, i = depth - 1, nxt_end + 5
        end_close = tex.index("}", i)
        body_end = i - 5
        body = tex[match.end():body_end]
        spec = ""
        if name in ("array", "alignedat") and body.startswith("{"):
            close = body.index("}")
            spec, body = body[1:close], body[close + 1:]
        before = tex[pos:match.start()]
        left = right = None
        lm = _LEFT_BEFORE.search(before)
        if lm:
            left, before = _DELIMITERS.get(lm.group(1), lm.group(1)), before[:lm.start()]
        after_start = end_close + 1
        rm = _RIGHT_AFTER.match(tex, after_start) if left is not None else None
        if rm:
            right, after_start = _DELIMITERS.get(rm.group(1), rm.group(1)), rm.end()
        if before.strip():
            out.append(("tex", before))
        out.append(("env", name.rstrip("*"), spec, body, left, right))
        pos = after_start
    if tex[pos:].strip():
        out.append(("tex", tex[pos:]))
    return out


_MATHTEXT_NAMES = {"le": "leq", "ge": "geq", "gets": "leftarrow", "implies": "Rightarrow",
                   "iff": "Leftrightarrow", "land": "wedge", "lor": "vee", "lnot": "neg", "tfrac": "frac",
                   "lvert": "vert", "rvert": "vert"}
_MATHTEXT_ALIASES = re.compile(r"\\(" + "|".join(_MATHTEXT_NAMES) + r")(?![A-Za-z])")


def _mathtext(source: str, size: float, dpi: int):
    """One line of math as a Pillow RGBA image (None for empty source)."""
    from matplotlib import rc_context
    from matplotlib.font_manager import FontProperties
    from matplotlib.mathtext import math_to_image
    from PIL import Image

    source = " ".join(source.split())
    if not source:
        return None
    # TeX spellings mathtext doesn't know, as ones it does.
    source = _MATHTEXT_ALIASES.sub(lambda m: "\\" + _MATHTEXT_NAMES[m.group(1)], source)
    # Display style: full-size fractions, as in a TeX display equation.
    source = re.sub(r"\\frac(?![A-Za-z])", r"\\dfrac", source)
    buffer = io.BytesIO()
    try:
        with rc_context({"mathtext.fontset": "cm"}):
            math_to_image(f"${source}$", buffer, prop=FontProperties(size=size), dpi=dpi, format="png")
    except Exception as exc:  # mathtext raises ValueError (and others) on TeX it can't parse
        raise _Unsupported(source) from exc
    buffer.seek(0)
    return Image.open(buffer).convert("RGBA")


def _layout(tex: str, size: float, dpi: int):
    """The whole equation as one image: segments side by side, centred."""
    segments = _segments(tex)
    if len(segments) == 1 and segments[0][0] == "tex" and "\\\\" in tex:
        segments = [("env", "gathered", "", tex, None, None)]  # bare line breaks
    images = []
    for segment in segments:
        if segment[0] == "tex":
            image = _mathtext(segment[1], size, dpi)
        else:
            _, name, spec, body, left, right = segment
            image = _environment(name, spec, body, left, right, size=size, dpi=dpi)
        if image is not None:
            images.append(image)
    return _row(images, gap=round(size * dpi / 72 * 0.15))


def _row(images: list, gap: int = 0):
    from PIL import Image

    if not images:
        return None
    width = sum(i.width for i in images) + gap * (len(images) - 1)
    height = max(i.height for i in images)
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    x = 0
    for image in images:
        canvas.alpha_composite(image, (x, (height - image.height) // 2))
        x += image.width + gap
    return canvas


def _environment(name: str, spec: str, body: str, left: Optional[str], right: Optional[str],
                 size: float, dpi: int):
    from PIL import Image

    em = size * dpi / 72
    rows = _split_top(body, "\\\\")
    if len(rows) > 1 and not rows[-1].strip():
        rows.pop()  # a trailing \\
    cells = [_split_top(row, "&") for row in rows]
    columns = max(len(r) for r in cells)
    if name in ("aligned", "align", "split", "alignedat", "flalign", "eqnarray"):
        aligns = ["right" if c % 2 == 0 else "left" for c in range(columns)]
        gaps = [0 if c % 2 == 0 else round(1.5 * em) for c in range(columns)]
        # "{}" gives a leading relation ("= b") its space on both sides, as in TeX.
        cells = [[("{}" + cell if c % 2 else cell) for c, cell in enumerate(row)] for row in cells]
    elif name in ("cases", "dcases"):
        aligns, gaps = ["left"] * columns, [round(1.0 * em)] * columns
    elif name == "array":
        aligns = [{"l": "left", "c": "center", "r": "right"}[c] for c in spec if c in "lcr"]
        aligns += ["center"] * (columns - len(aligns))
        gaps = [round(0.8 * em)] * columns
    elif name.endswith("matrix"):
        aligns, gaps = ["center"] * columns, [round(0.8 * em)] * columns
    else:  # gathered, gather, multline, ...: centred lines
        aligns, gaps = ["center"] * columns, [round(0.8 * em)] * columns
    rendered = [[_mathtext(cell, size, dpi) for cell in row] for row in cells]
    widths = [max((r[c].width for r in rendered if c < len(r) and r[c] is not None), default=0)
              for c in range(columns)]
    heights = [max((i.height for i in row if i is not None), default=round(em)) for row in rendered]
    row_gap = round(0.35 * em)
    grid_w = sum(widths) + sum(gaps[:columns - 1])
    grid_h = sum(heights) + row_gap * (len(heights) - 1)
    grid = Image.new("RGBA", (max(grid_w, 1), max(grid_h, 1)), (255, 255, 255, 0))
    y = 0
    for row, height in zip(rendered, heights):
        x = 0
        for c in range(columns):
            image = row[c] if c < len(row) else None
            if image is not None:
                offset = {"left": 0, "center": (widths[c] - image.width) // 2,
                          "right": widths[c] - image.width}[aligns[c]]
                grid.alpha_composite(image, (x + offset, y + (height - image.height) // 2))
            x += widths[c] + (gaps[c] if c < columns - 1 else 0)
        y += height + row_gap
    opening, closing = _ENV_DELIMITERS.get(name, ("", ""))
    if left is not None:
        opening = left
    if right is not None:
        closing = right
    return _delimit(grid, opening, closing, em, size, dpi)


def _delimit(grid, opening: str, closing: str, em: float, size: float, dpi: int):
    """Draw delimiters (``( [ { | ‖ ⟨``) to the grid's full height."""
    from PIL import Image, ImageDraw

    if not opening and not closing:
        return grid
    pad = round(0.15 * em)
    height = grid.height + 2 * pad
    width_d = round(0.45 * em)
    line = max(1, round(0.06 * em))
    left_w = width_d if opening else 0
    right_w = width_d if closing else 0
    canvas = Image.new("RGBA", (grid.width + left_w + right_w, height), (255, 255, 255, 0))
    canvas.alpha_composite(grid, (left_w, pad))
    draw = ImageDraw.Draw(canvas)
    ink = (0, 0, 0, 255)

    def draw_delimiter(char: str, x0: int, mirror: bool) -> None:
        x1 = x0 + width_d
        # "outer" is the side away from the content; "inner" faces it.
        outer, inner = (x0 + line, x1 - line) if not mirror else (x1 - line, x0 + line)
        if char in ("(", ")"):
            span = 2 * abs(inner - outer)  # the ellipse whose side is the bracket
            box = [outer, 0, outer + span, height - 1] if not mirror else [outer - span, 0, outer, height - 1]
            start, end = (115, 245) if not mirror else (-65, 65)
            draw.arc(box, start, end, fill=ink, width=line)
        elif char in ("[", "]"):
            draw.line([(inner, 0), (outer, 0), (outer, height - 1), (inner, height - 1)], fill=ink, width=line)
        elif char == "|":
            mid = (x0 + x1) // 2
            draw.line([(mid, 0), (mid, height - 1)], fill=ink, width=line)
        elif char == "‖":
            mid = (x0 + x1) // 2
            for dx in (-line * 2, line * 2):
                draw.line([(mid + dx, 0), (mid + dx, height - 1)], fill=ink, width=line)
        elif char in ("⟨", "⟩"):
            draw.line([(inner, 0), (outer, height // 2), (inner, height - 1)], fill=ink, width=line)
        elif char in ("{", "}"):
            glyph = _mathtext(r"\{" if char == "{" else r"\}", size, dpi)
            if glyph is not None:
                glyph = glyph.resize((max(1, x1 - x0 - line), height))
                canvas.alpha_composite(glyph, (x0, 0))

    if opening:
        draw_delimiter(opening, 0, mirror=False)
    if closing:
        draw_delimiter(closing, canvas.width - width_d, mirror=True)
    return canvas
