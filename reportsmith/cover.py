"""The cover page: a title page that fills the report's first page."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

from .elements import Figure


class Cover:
    """A cover (title) page for a :class:`~reportsmith.Report`.

    The cover shows the report's title, subtitle, author and date, plus:

    - ``logo``: an image at the top, given as a file path, image bytes, or a
      plot with ``savefig()`` (like :meth:`~reportsmith.Report.figure`).
    - ``logo_width``: the logo's width as a fraction (0-1] of the text width.
    - ``organization``: a name shown under the logo.
    - ``note``: small print at the foot of the page, e.g. "Confidential".

    It replaces the title block and takes the first page on its own, with
    no running header or footer; the content starts on page 2. In Markdown
    and on screen in HTML, it is a centred title area instead of a page.
    """

    def __init__(
        self,
        logo: Union[None, str, Path, bytes, Any] = None,
        logo_width: float = 0.3,
        organization: str = "",
        note: str = "",
    ):
        if not 0 < logo_width <= 1:
            raise ValueError(f"logo_width must be a fraction in (0, 1], got {logo_width}")
        alt = f"{organization} logo" if organization else "Logo"
        self.logo: Optional[Figure] = (
            None if logo is None else Figure(logo, alt=alt, width=logo_width)
        )
        self.organization = organization
        self.note = note

    def __repr__(self) -> str:
        logo = "" if self.logo is None else f"logo={self.logo.source!r}, "
        return f"Cover({logo}organization={self.organization!r}, note={self.note!r})"


def make_cover(value: Union[None, bool, Cover]) -> Optional[Cover]:
    """Normalize ``Report(cover=...)``: ``True`` is a plain cover."""
    if value is None or value is False:
        return None
    if value is True:
        return Cover()
    if isinstance(value, Cover):
        return value
    raise TypeError(f"cover must be True, False, None or a Cover, got {type(value).__name__}")
