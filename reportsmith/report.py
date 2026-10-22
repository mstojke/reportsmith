"""The Report — top-level container plus export entry points."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any, Optional, Sequence, Union

from .elements import Container


class Report(Container):
    """A report document.

    Content is added through the fluent builder methods inherited from
    :class:`~reportsmith.elements.Container` (``paragraph``, ``table``,
    ``section``, ...) and exported with :meth:`to_markdown` /
    :meth:`to_html` / :meth:`to_latex` / :meth:`to_pdf`, or saved with the
    matching ``save_*`` methods or :meth:`save`.

    ``description``, ``keywords`` and ``language`` are document metadata:
    HTML ``<meta>`` tags and ``lang``, PDF document properties, LaTeX's PDF
    fields, and optional Markdown front matter.
    """

    def __init__(
        self,
        title: str,
        author: str = "",
        date: Optional[Union[str, _dt.date, _dt.datetime]] = None,
        subtitle: str = "",
        description: str = "",
        keywords: Sequence[str] = (),
        language: str = "en",
    ):
        super().__init__()
        self.title = title
        self.author = author
        self.subtitle = subtitle
        self.description = description
        if isinstance(keywords, str):
            raise TypeError("keywords must be a sequence of strings, not a single string")
        self.keywords = [str(k) for k in keywords]
        self.language = language
        if date is None:
            self.date = _dt.date.today().isoformat()
        elif isinstance(date, (_dt.date, _dt.datetime)):
            self.date = date.isoformat()
        else:
            self.date = str(date)
        self._level = 1  # report title is <h1>, top-level sections are <h2>

    # -- export ----------------------------------------------------------

    def to_markdown(
        self, assets_dir: Optional[Union[str, Path]] = None, front_matter: bool = False
    ) -> str:
        """Render the report as a Markdown string.

        Figures made from plots or image bytes are embedded as data URIs,
        or written as files into ``assets_dir`` when given.
        ``front_matter=True`` starts the document with a YAML metadata block
        (title, author, date, ...) for static-site generators.
        """
        from .renderers.markdown import MarkdownRenderer

        return MarkdownRenderer(assets_dir=assets_dir, front_matter=front_matter).render(self)

    def to_html(
        self,
        full_document: bool = True,
        css: Optional[str] = None,
        theme: str = "auto",
        highlight: bool = False,
    ) -> str:
        """Render the report as HTML.

        ``full_document=True`` (default) produces a standalone page with
        embedded CSS; ``False`` produces only the body fragment. Pass ``css``
        to replace the built-in stylesheet, or ``theme`` (``"auto"``,
        ``"light"`` or ``"dark"``) to choose its colours. ``highlight=True``
        colours code blocks with Pygments (``pip install
        reportsmith[highlight]``).
        """
        from .renderers.html import HtmlRenderer

        return HtmlRenderer(
            full_document=full_document, css=css, theme=theme, highlight=highlight
        ).render(self)

    def to_pdf(
        self,
        fonts: Optional[Sequence[str]] = None,
        mono_fonts: Optional[Sequence[str]] = None,
        highlight: bool = False,
    ) -> bytes:
        """Render the report as PDF bytes.

        Requires the optional ``fpdf2`` dependency (``pip install
        reportsmith[pdf]``). ``fonts`` / ``mono_fonts`` are optional
        (regular, bold, italic, bold-italic) TTF path quadruples; by default
        a Unicode-capable system font family is auto-detected.
        ``highlight=True`` colours code blocks with Pygments.
        """
        from .renderers.pdf import PdfRenderer

        return PdfRenderer(fonts=fonts, mono_fonts=mono_fonts, highlight=highlight).render(self)

    def to_latex(
        self,
        full_document: bool = True,
        document_class: str = "article",
        class_options: str = "11pt,a4paper",
        preamble: str = "",
        numbered: bool = False,
        assets_dir: Optional[Union[str, Path]] = None,
        highlight: bool = False,
    ) -> str:
        """Render the report as LaTeX source.

        ``full_document=True`` (default) produces a compilable document with
        a title block; ``False`` produces only the body content. ``preamble``
        is appended to the built-in preamble; ``numbered=True`` numbers
        sections. Figures made from plots or image bytes are written as files
        into ``assets_dir``, which is required when the report has any.
        ``highlight=True`` colours code blocks with Pygments.
        """
        from .renderers.latex import LatexRenderer

        return LatexRenderer(
            full_document=full_document,
            document_class=document_class,
            class_options=class_options,
            preamble=preamble,
            numbered=numbered,
            assets_dir=assets_dir,
            highlight=highlight,
        ).render(self)

    def save_markdown(self, path: Union[str, Path], front_matter: bool = False) -> Path:
        """Write the Markdown export to ``path`` and return it.

        Figures made from plots or image bytes are written into a
        ``<name>_files`` folder next to it.
        """
        from .renderers.markdown import MarkdownRenderer

        path = Path(path)
        assets_dir, assets_url = _assets_for(path)
        text = MarkdownRenderer(
            assets_dir=assets_dir, assets_url=assets_url, front_matter=front_matter
        ).render(self)
        path.write_text(text, encoding="utf-8")
        return path

    def save_html(
        self,
        path: Union[str, Path],
        full_document: bool = True,
        css: Optional[str] = None,
        theme: str = "auto",
        highlight: bool = False,
    ) -> Path:
        """Write the HTML export to ``path`` and return it."""
        path = Path(path)
        html = self.to_html(full_document=full_document, css=css, theme=theme, highlight=highlight)
        path.write_text(html, encoding="utf-8")
        return path

    def save_latex(
        self,
        path: Union[str, Path],
        full_document: bool = True,
        document_class: str = "article",
        class_options: str = "11pt,a4paper",
        preamble: str = "",
        numbered: bool = False,
        highlight: bool = False,
    ) -> Path:
        """Write the LaTeX export to ``path`` and return it.

        Figures made from plots or image bytes are written into a
        ``<name>_files`` folder next to it (plots as vector PDF).
        """
        from .renderers.latex import LatexRenderer

        path = Path(path)
        assets_dir, assets_url = _assets_for(path)
        text = LatexRenderer(
            full_document=full_document,
            document_class=document_class,
            class_options=class_options,
            preamble=preamble,
            numbered=numbered,
            assets_dir=assets_dir,
            assets_url=assets_url,
            highlight=highlight,
        ).render(self)
        path.write_text(text, encoding="utf-8")
        return path

    def save_pdf(
        self,
        path: Union[str, Path],
        fonts: Optional[Sequence[str]] = None,
        mono_fonts: Optional[Sequence[str]] = None,
        highlight: bool = False,
    ) -> Path:
        """Write the PDF export to ``path`` and return it (requires fpdf2)."""
        path = Path(path)
        path.write_bytes(self.to_pdf(fonts=fonts, mono_fonts=mono_fonts, highlight=highlight))
        return path

    def save(self, path: Union[str, Path], **options: Any) -> Path:
        """Write the report in the format given by the file extension.

        ``.md`` / ``.markdown``, ``.html`` / ``.htm``, ``.tex`` and ``.pdf``
        call :meth:`save_markdown`, :meth:`save_html`, :meth:`save_latex` and
        :meth:`save_pdf`; ``options`` are passed on to that method.
        """
        path = Path(path)
        method = _SAVERS.get(path.suffix.lower())
        if method is None:
            known = ", ".join(sorted(_SAVERS))
            raise ValueError(
                f"Can't tell the format of {path.name!r} from its extension; use one of {known}"
            )
        return getattr(self, method)(path, **options)


_SAVERS = {
    ".md": "save_markdown",
    ".markdown": "save_markdown",
    ".html": "save_html",
    ".htm": "save_html",
    ".tex": "save_latex",
    ".pdf": "save_pdf",
}


def _assets_for(path: Path) -> tuple[Path, str]:
    """Folder for a saved document's figure files, and how the document
    refers to it (relative, so the output can be moved as a whole)."""
    folder = f"{path.stem}_files"
    return path.parent / folder, f"{folder}/"
