"""TeX math to Office Math Markup (OMML), the equation format of Word.

:func:`tex_to_omml` turns TeX math into an ``<m:oMath>`` element that Word
shows as an editable equation: fractions, roots, scripts, big operators with
limits, delimiters, accents, functions, text, and the ``matrix`` /
``pmatrix`` / ``bmatrix`` / ``cases`` / ``aligned`` / ``gathered`` /
``array`` environments. Unknown commands are kept as text, so any input
gives a valid equation.
"""

from __future__ import annotations

import re
from typing import Optional
from xml.sax.saxutils import escape

from .equations import _FUNCTIONS, _SYMBOLS

M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

_TOKEN = re.compile(r"\\([A-Za-z]+|.)|([{}^_&\[\]])|(\s+)|(.)", re.S)
_NARY = {"sum": "∑", "prod": "∏", "coprod": "∐", "int": "∫", "iint": "∬", "iiint": "∭",
         "oint": "∮", "bigcup": "⋃", "bigcap": "⋂", "bigoplus": "⨁", "bigotimes": "⨂"}
_INTEGRALS = {"∫", "∬", "∭", "∮"}
_LIMIT_FUNCTIONS = {"lim", "limsup", "liminf", "max", "min", "sup", "inf", "det", "gcd", "Pr", "arg"}
_ACCENTS = {"hat": "\u0302", "widehat": "\u0302", "tilde": "\u0303", "widetilde": "\u0303",
            "bar": "\u0305", "vec": "\u20d7", "dot": "\u0307", "ddot": "\u0308", "check": "\u030c",
            "breve": "\u0306", "acute": "\u0301", "grave": "\u0300"}
_SCRIPTS = {"mathbb": "double-struck", "mathcal": "script", "mathscr": "script",
            "mathfrak": "fraktur", "mathsf": "sans-serif", "mathtt": "monospace"}
_STYLES = {"mathrm": "p", "mathbf": "b", "boldsymbol": "bi", "mathit": "i", "operatorname": "p"}
_TEXT = {"text", "textrm", "textit", "textbf", "mbox", "textsf", "texttt"}
_DELIMS = {"(": "(", ")": ")", "[": "[", "]": "]", "|": "|", ".": "", "<": "⟨", ">": "⟩",
           "\\{": "{", "\\}": "}", "lbrace": "{", "rbrace": "}", "langle": "⟨", "rangle": "⟩",
           "lvert": "|", "rvert": "|", "vert": "|", "lVert": "‖", "rVert": "‖", "Vert": "‖",
           "lfloor": "⌊", "rfloor": "⌋", "lceil": "⌈", "rceil": "⌉", "\\|": "‖"}
_MATRICES = {"matrix": ("", ""), "pmatrix": ("(", ")"), "bmatrix": ("[", "]"), "Bmatrix": ("{", "}"),
             "vmatrix": ("|", "|"), "Vmatrix": ("‖", "‖"), "smallmatrix": ("", "")}
_RELATIONS = set("=<>≤≥≠≈≡∼≃≅∝→←↔⇒⇐⇔∈∉⊂⊃⊆⊇")
_SPACES = {",": "\u2009", ":": "\u205f", ";": "\u2004", " ": " ", "quad": "\u2003", "qquad": "\u2003\u2003",
           "!": ""}
_FONT = '<w:rPr><w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/></w:rPr>'


def _run(text: str, sty: str = "", scr: str = "", normal: bool = False) -> str:
    props = ""
    if scr:
        props += f'<m:scr m:val="{scr}"/>'
    if sty:
        props += f'<m:sty m:val="{sty}"/>'
    if normal:
        props += "<m:nor/>"
    rpr = f"<m:rPr>{props}</m:rPr>" if props else ""
    font = "" if normal else _FONT
    return f'<m:r>{rpr}{font}<m:t xml:space="preserve">{escape(text)}</m:t></m:r>'


class _Atom:
    """One parsed item: finished OMML, or a big operator / limit function
    that still takes scripts (and, for operators, an operand)."""

    def __init__(self, xml: str = "", kind: str = "xml", char: str = "", text: str = "",
                 sty: str = "", scr: str = ""):
        self.xml = xml
        self.kind = kind  # "xml", "text" (mergeable run), "nary", "limfunc"
        self.char = char
        self.text = text
        self.sty = sty
        self.scr = scr
        self.sub: Optional[str] = None
        self.sup: Optional[str] = None


class _Parser:
    def __init__(self, tex: str):
        self.tokens = list(_TOKEN.finditer(tex))
        self.i = 0

    def peek(self) -> Optional[re.Match]:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def take(self) -> Optional[re.Match]:
        tok = self.peek()
        self.i += 1
        return tok

    def skip_space(self) -> None:
        while (tok := self.peek()) is not None and tok.group(3):
            self.i += 1

    # -- groups --------------------------------------------------------------

    def argument(self) -> str:
        """One argument: a braced group or a single token, as OMML."""
        self.skip_space()
        tok = self.peek()
        if tok is None:
            return ""
        if tok.group(2) == "{":
            self.i += 1
            return self.sequence(stop={"}"})
        self.i += 1
        return self.finish([self.atom(tok)])

    def raw_argument(self) -> str:
        """A braced argument as plain source text (for \\text, env names)."""
        self.skip_space()
        tok = self.take()
        if tok is None:
            return ""
        if tok.group(2) != "{":
            return tok.group(0)
        depth, out = 1, []
        while (tok := self.take()) is not None:
            if tok.group(2) == "{":
                depth += 1
            elif tok.group(2) == "}":
                depth -= 1
                if depth == 0:
                    break
            out.append(tok.group(0))
        return "".join(out)

    def optional(self) -> str:
        tok = self.peek()
        if tok is None or tok.group(2) != "[":
            return ""
        self.i += 1
        return self.sequence(stop={"]"})

    def sequence(self, stop: set[str]) -> str:
        """Atoms up to a stop token (consumed), as OMML."""
        atoms: list[_Atom] = []
        while (tok := self.peek()) is not None:
            word = tok.group(2) or ("\\" + tok.group(1) if tok.group(1) else "")
            if word in stop or tok.group(0) in stop:
                if tok.group(2) in ("}", "]"):
                    self.i += 1
                break
            self.i += 1
            if tok.group(3):
                continue  # TeX ignores spaces in math
            if tok.group(2) in ("^", "_"):
                self.script(atoms, superscript=tok.group(2) == "^")
                continue
            if tok.group(1) == "right":
                self.i -= 1
                break
            atoms.append(self.atom(tok))
        return self.finish(atoms)

    def script(self, atoms: list[_Atom], superscript: bool) -> None:
        arg = self.argument()
        if not atoms:
            atoms.append(_Atom(""))
        base = atoms[-1]
        if superscript:
            base.sup = arg
        else:
            base.sub = arg

    # -- atoms ---------------------------------------------------------------

    def atom(self, tok: re.Match) -> _Atom:
        command, special, _space, char = tok.groups()
        if char is not None:
            return _Atom(kind="text", text="′" if char == "'" else ("−" if char == "-" else char))
        if special == "{":
            return _Atom(self.sequence(stop={"}"}))
        if special in ("[", "]"):
            return _Atom(kind="text", text=special)
        if special in ("}", "&"):
            return _Atom("")
        return self.command(command)

    def command(self, name: str) -> _Atom:
        if name in ("frac", "dfrac", "tfrac", "cfrac"):
            num, den = self.argument(), self.argument()
            return _Atom(f"<m:f><m:num>{num}</m:num><m:den>{den}</m:den></m:f>")
        if name in ("binom", "dbinom", "tbinom"):
            n, k = self.argument(), self.argument()
            frac = f'<m:f><m:fPr><m:type m:val="noBar"/></m:fPr><m:num>{n}</m:num><m:den>{k}</m:den></m:f>'
            return _Atom(_delimited("(", ")", frac))
        if name == "sqrt":
            degree = self.optional()
            body = self.argument()
            hide = "" if degree else '<m:radPr><m:degHide m:val="1"/></m:radPr>'
            return _Atom(f"<m:rad>{hide}<m:deg>{degree}</m:deg><m:e>{body}</m:e></m:rad>")
        if name in _NARY:
            return _Atom(kind="nary", char=_NARY[name])
        if name in _LIMIT_FUNCTIONS:
            return _Atom(kind="limfunc", text=name)
        if name in _FUNCTIONS:
            return _Atom(kind="func", text=name)
        if name in _ACCENTS:
            body = self.argument()
            return _Atom(f'<m:acc><m:accPr><m:chr m:val="{_ACCENTS[name]}"/></m:accPr><m:e>{body}</m:e></m:acc>')
        if name in ("overline", "underline"):
            pos = "top" if name == "overline" else "bot"
            body = self.argument()
            return _Atom(f'<m:bar><m:barPr><m:pos m:val="{pos}"/></m:barPr><m:e>{body}</m:e></m:bar>')
        if name in ("overbrace", "underbrace"):
            body = self.argument()
            chr_, pos = ("⏞", "top") if name == "overbrace" else ("⏟", "bot")
            return _Atom(f'<m:groupChr><m:groupChrPr><m:chr m:val="{chr_}"/><m:pos m:val="{pos}"/>'
                         f'</m:groupChrPr><m:e>{body}</m:e></m:groupChr>')
        if name in _SCRIPTS:
            return _Atom(_restyle(self.argument(), scr=_SCRIPTS[name]))
        if name in _STYLES:
            return _Atom(_restyle(self.argument(), sty=_STYLES[name]))
        if name in _TEXT:
            return _Atom(_run(self.raw_argument(), normal=True))
        if name == "left":
            return self.left()
        if name == "begin":
            return self.environment(self.raw_argument())
        if name in _SPACES:
            return _Atom(kind="text", text=_SPACES[name]) if _SPACES[name] else _Atom("")
        if name in ("displaystyle", "textstyle", "limits", "nolimits", "big", "Big", "bigg", "Bigg",
                    "bigl", "bigr", "Bigl", "Bigr", "biggl", "biggr", "nonumber", "notag"):
            return _Atom("")
        if name == "\\":
            return _Atom(kind="text", text=" ")  # a line break outside an environment
        if name in _SYMBOLS:
            return _Atom(kind="text", text=_SYMBOLS[name])
        return _Atom(kind="text", text=name, sty="p")  # unknown command: keep its name

    def delimiter(self) -> str:
        self.skip_space()
        tok = self.take()
        if tok is None:
            return ""
        key = tok.group(1) if tok.group(1) and len(tok.group(1)) > 1 else tok.group(0)
        return _DELIMS.get(key, tok.group(0))

    def left(self) -> _Atom:
        opening = self.delimiter()
        body = self.sequence(stop={"\\right"})
        closing = ""
        tok = self.peek()
        if tok is not None and tok.group(1) == "right":
            self.i += 1
            closing = self.delimiter()
        return _Atom(_delimited(opening, closing, body))

    def environment(self, name: str) -> _Atom:
        spec = self.raw_argument() if name in ("array", "alignedat") else ""
        rows = self.rows(name)
        base = name.rstrip("*")
        if base in _MATRICES:
            columns = max(len(r) for r in rows)
            opening, closing = _MATRICES[base]
            return _Atom(_delimited(opening, closing, _matrix(rows, ["center"] * columns))
                         if opening else _matrix(rows, ["center"] * columns))
        if base in ("cases", "dcases"):
            return _Atom(_delimited("{", "", _matrix(rows, ["left", "left"])))
        if base in ("aligned", "align", "split", "alignedat", "flalign", "eqnarray"):
            columns = max(len(r) for r in rows)
            aligns = ["right" if c % 2 == 0 else "left" for c in range(columns)]
            return _Atom(_matrix(rows, aligns, gap=False))
        if base == "array":
            aligns = [{"l": "left", "c": "center", "r": "right"}[c] for c in spec if c in "lcr"]
            columns = max(len(r) for r in rows)
            aligns += ["center"] * (columns - len(aligns))
            return _Atom(_matrix(rows, aligns[:columns]))
        # gathered, gather, multline, unknown: centred lines
        lines = "".join(f"<m:e>{''.join(row)}</m:e>" for row in rows)
        return _Atom(f"<m:eqArr>{lines}</m:eqArr>")

    def rows(self, name: str) -> list[list[str]]:
        """Cells of an environment body, as OMML, up to ``\\end{name}``."""
        rows: list[list[str]] = [[]]
        while True:
            cell = self.sequence(stop={"&", "\\\\", "\\end"})
            rows[-1].append(cell)
            tok = self.take()
            if tok is None:
                break
            if tok.group(2) == "&":
                continue
            if tok.group(1) == "\\":
                rows.append([])
                continue
            if tok.group(1) == "end":
                self.raw_argument()
                break
        if len(rows) > 1 and rows[-1] == [""]:
            rows.pop()  # a trailing \\
        return rows

    # -- finishing -----------------------------------------------------------

    def finish(self, atoms: list[_Atom]) -> str:
        """Serialize atoms: attach scripts, give operators their operand,
        merge adjacent plain text into one run."""
        out: list[str] = []
        pending: list[_Atom] = []  # mergeable text atoms

        def flush() -> None:
            while pending:
                first = pending.pop(0)
                text = first.text
                while pending and (pending[0].sty, pending[0].scr) == (first.sty, first.scr):
                    text += pending.pop(0).text
                out.append(_run(text, sty=first.sty, scr=first.scr))

        i = 0
        while i < len(atoms):
            atom = atoms[i]
            i += 1
            if atom.kind == "nary":
                # The operand runs to the next relation, or the end of the group.
                j = i
                while j < len(atoms) and not (atoms[j].kind == "text" and atoms[j].text in _RELATIONS):
                    j += 1
                operand = self.finish(atoms[i:j])
                i = j
                flush()
                out.append(_nary(atom.char, atom.sub, atom.sup, operand))
                continue
            if atom.kind in ("limfunc", "func"):
                flush()
                name = _run(atom.text, sty="p")
                if atom.kind == "limfunc" and atom.sub is not None:
                    name = f"<m:limLow><m:e>{name}</m:e><m:lim>{atom.sub}</m:lim></m:limLow>"
                elif atom.sub is not None or atom.sup is not None:
                    name = _scripted(name, atom.sub, atom.sup)
                if atom.kind == "limfunc" and atom.sub is not None and atom.sup is not None:
                    name = f"<m:sSup><m:e>{name}</m:e><m:sup>{atom.sup}</m:sup></m:sSup>"
                # Word spaces a function name from its argument: the next atom.
                if i < len(atoms) and not (atoms[i].kind == "text" and atoms[i].text in _RELATIONS):
                    argument = self.finish(atoms[i:i + 1])
                    i += 1
                    out.append(f"<m:func><m:fName>{name}</m:fName><m:e>{argument}</m:e></m:func>")
                else:
                    out.append(name)
                continue
            if atom.sub is None and atom.sup is None:
                if atom.kind == "text":
                    pending.append(atom)
                else:
                    flush()
                    out.append(atom.xml)
                continue
            # A scripted atom: the script binds to its last character only.
            if atom.kind == "text" and len(atom.text) > 1 and not atom.sty:
                pending.append(_Atom(kind="text", text=atom.text[:-1], sty=atom.sty, scr=atom.scr))
                base = _run(atom.text[-1], sty=atom.sty, scr=atom.scr)
            else:
                base = _run(atom.text, sty=atom.sty, scr=atom.scr) if atom.kind == "text" else atom.xml
            flush()
            out.append(_scripted(base, atom.sub, atom.sup))
        flush()
        return "".join(out)


def _scripted(base: str, sub: Optional[str], sup: Optional[str]) -> str:
    if sub is not None and sup is not None:
        return f"<m:sSubSup><m:e>{base}</m:e><m:sub>{sub}</m:sub><m:sup>{sup}</m:sup></m:sSubSup>"
    if sup is not None:
        return f"<m:sSup><m:e>{base}</m:e><m:sup>{sup}</m:sup></m:sSup>"
    return f"<m:sSub><m:e>{base}</m:e><m:sub>{sub}</m:sub></m:sSub>"


def _nary(char: str, sub: Optional[str], sup: Optional[str], operand: str) -> str:
    loc = "subSup" if char in _INTEGRALS else "undOvr"
    props = f'<m:chr m:val="{char}"/><m:limLoc m:val="{loc}"/>'
    if sub is None:
        props += '<m:subHide m:val="1"/>'
    if sup is None:
        props += '<m:supHide m:val="1"/>'
    return (f"<m:nary><m:naryPr>{props}</m:naryPr><m:sub>{sub or ''}</m:sub>"
            f"<m:sup>{sup or ''}</m:sup><m:e>{operand}</m:e></m:nary>")


def _delimited(opening: str, closing: str, body: str) -> str:
    return (f'<m:d><m:dPr><m:begChr m:val="{escape(opening, {chr(34): "&quot;"})}"/>'
            f'<m:endChr m:val="{escape(closing, {chr(34): "&quot;"})}"/></m:dPr><m:e>{body}</m:e></m:d>')


def _matrix(rows: list[list[str]], aligns: list[str], gap: bool = True) -> str:
    """A matrix; ``gap=False`` sets the columns only a relation's space apart
    (for aligned equations, where the relation starts the right-hand column)."""
    columns = len(aligns)
    mcs = "".join(
        f'<m:mc><m:mcPr><m:count m:val="1"/><m:mcJc m:val="{a}"/></m:mcPr></m:mc>' for a in aligns
    )
    body = "".join(
        "<m:mr>" + "".join(f"<m:e>{cell}</m:e>" for cell in row + [""] * (columns - len(row))) + "</m:mr>"
        for row in rows
    )
    # Without a gap, the columns are a TeX thick space (~3 pt) apart, as around "=".
    spacing = "" if gap else '<m:cGpRule m:val="3"/><m:cGp m:val="60"/>'
    return f"<m:m><m:mPr>{spacing}<m:mcs>{mcs}</m:mcs></m:mPr>{body}</m:m>"


_RUN_PROPS = re.compile(r"<m:r>(<m:rPr>.*?</m:rPr>)?")


def _restyle(xml: str, sty: str = "", scr: str = "") -> str:
    """Apply a math style (upright, bold) or script (double-struck, ...) to
    every run in already-built OMML."""
    props = (f'<m:scr m:val="{scr}"/>' if scr else "") + (f'<m:sty m:val="{sty}"/>' if sty else "")
    return _RUN_PROPS.sub(f"<m:r><m:rPr>{props}</m:rPr>", xml)


def tex_to_omml(tex: str) -> str:
    """TeX math as an ``<m:oMath>`` element (namespace prefix ``m``)."""
    parser = _Parser(tex)
    body = parser.sequence(stop=set())
    return f"<m:oMath>{body}</m:oMath>"
