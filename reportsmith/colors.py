"""Named colours for table cell styling.

A colour is one of the names below or a hex value (``"#b91c1c"`` or
``"#b11"``). Names come in a text shade and a pale background shade; in
HTML they also adapt to the dark theme.
"""

from __future__ import annotations

import re
from typing import Optional

#: Text colours (light theme / print).
TEXT_COLORS = {
    "red": "#b91c1c",
    "green": "#15803d",
    "amber": "#b45309",
    "blue": "#1d4ed8",
    "gray": "#6b7280",
}
#: Background tints (light theme / print).
BACKGROUND_COLORS = {
    "red": "#fee2e2",
    "green": "#dcfce7",
    "amber": "#fef3c7",
    "blue": "#dbeafe",
    "gray": "#f3f4f6",
}
#: Dark-theme counterparts, used by the HTML stylesheet.
DARK_TEXT_COLORS = {
    "red": "#f87171",
    "green": "#4ade80",
    "amber": "#fbbf24",
    "blue": "#60a5fa",
    "gray": "#9ca3af",
}
DARK_BACKGROUND_COLORS = {
    "red": "#4c1d1d",
    "green": "#14351f",
    "amber": "#45300f",
    "blue": "#1e2f55",
    "gray": "#2b3442",
}
NAMES = tuple(TEXT_COLORS)
_ALIASES = {"grey": "gray"}
_HEX_RE = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


def check_color(value: Optional[str], what: str = "color") -> Optional[str]:
    """Validate a colour: returns a name from :data:`NAMES` or ``"#rrggbb"``."""
    if value is None:
        return None
    name = _ALIASES.get(value, value)
    if name in TEXT_COLORS:
        return name
    match = _HEX_RE.fullmatch(value)
    if not match:
        raise ValueError(
            f"Invalid {what} {value!r}: use one of {', '.join(NAMES)} or a hex value like '#b91c1c'"
        )
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return "#" + digits.lower()


def to_hex(value: str, background: bool = False) -> str:
    """``"#rrggbb"`` for a checked colour (names use the light shades)."""
    if value.startswith("#"):
        return value
    return (BACKGROUND_COLORS if background else TEXT_COLORS)[value]


def to_rgb(value: str, background: bool = False) -> tuple[int, int, int]:
    h = to_hex(value, background)
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
