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
    isn't installed or mathtext can't parse the TeX (it supports a large
    subset of TeX math, but not environments such as ``align``).
    """
    try:
        from matplotlib import rc_context
        from matplotlib.font_manager import FontProperties
        from matplotlib.mathtext import math_to_image
    except ImportError:
        return None
    source = " ".join(tex.split())  # mathtext needs one line
    # Display style: full-size fractions, as in a TeX display equation.
    source = re.sub(r"\\frac(?![A-Za-z])", r"\\dfrac", source)
    buffer = io.BytesIO()
    try:
        with rc_context({"mathtext.fontset": "cm"}):
            math_to_image(f"${source}$", buffer, prop=FontProperties(size=size), dpi=dpi, format="png")
    except Exception:  # mathtext raises ValueError (and others) on TeX it can't parse
        return None
    data = buffer.getvalue()
    width_px, height_px = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    return data, width_px * 72 / dpi, height_px * 72 / dpi
