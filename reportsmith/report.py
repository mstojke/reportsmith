"""The Report — top-level container plus export entry points."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Optional, Sequence, Union

from .elements import Container


class Report(Container):
    """A report document.

    Content is added through the fluent builder methods inherited from
    :class:`~reportsmith.elements.Container` (``paragraph``, ``table``,
    ``section``, ...) and exported with :meth:`to_markdown` /
    :meth:`to_html` / :meth:`to_latex` or saved with :meth:`save_markdown` /
    :meth:`save_html` / :meth:`save_latex`.
    """

    def __init__(
        self,
        title: str,
        author: str = "",
        date: Optional[Union[str, _dt.date, _dt.datetime]] = None,
        subtitle: str = "",
    ):
        super().__init__()
        self.title = title
        self.author = author
        self.subtitle = subtitle
        if date is None:
            self.date = _dt.date.today().isoformat()
        elif isinstance(date, (_dt.date, _dt.datetime)):
            self.date = date.isoformat()
        else:
            self.date = str(date)
        self._level = 1  # report title is <h1>, top-level sections are <h2>

    # -- export ----------------------------------------------------------

    def to_markdown(self, assets_dir: Optional[Union[str, Path]] = None) -> str:
        """Render the report as a Markdown string.

        Figures made from plots or image bytes are embedded as data URIs,
        or written as files into ``assets_dir`` when given.
        """
        from .renderers.markdown import MarkdownRenderer

        return MarkdownRenderer(assets_dir=assets_dir).render(self)

    def to_html(self, full_document: bool = True, css: Optional[str] = None) -> str:
        """Render the report as HTML.

        ``full_document=True`` (default) produces a standalone page with
        embedded CSS; ``False`` produces only the body fragment. Pass ``css``
        to replace the built-in stylesheet.
        """
        from .renderers.html import HtmlRenderer

        return HtmlRenderer(full_document=full_document, css=css).render(self)

    def to_pdf(
        self,
        fonts: Optional[Sequence[str]] = None,
        mono_fonts: Optional[Sequence[str]] = None,
    ) -> bytes:
        """Render the report as PDF bytes.

        Requires the optional ``fpdf2`` dependency (``pip install
        reportsmith[pdf]``). ``fonts`` / ``mono_fonts`` are optional
        (regular, bold, italic, bold-italic) TTF path quadruples; by default
        a Unicode-capable system font family is auto-detected.
        """
        from .renderers.pdf import PdfRenderer

        return PdfRenderer(fonts=fonts, mono_fonts=mono_fonts).render(self)

    def to_latex(
        self,
        full_document: bool = True,
        document_class: str = "article",
        class_options: str = "11pt,a4paper",
        preamble: str = "",
        numbered: bool = False,
        assets_dir: Optional[Union[str, Path]] = None,
    ) -> str:
        """Render the report as LaTeX source.

        ``full_document=True`` (default) produces a compilable document with
        a title block; ``False`` produces only the body content. ``preamble``
        is appended to the built-in preamble; ``numbered=True`` numbers
        sections. Figures made from plots or image bytes are written as files
        into ``assets_dir``, which is required when the report has any.
        """
        from .renderers.latex import LatexRenderer

        return LatexRenderer(
            full_document=full_document,
            document_class=document_class,
            class_options=class_options,
            preamble=preamble,
            numbered=numbered,
            assets_dir=assets_dir,
        ).render(self)

    def save_markdown(self, path: Union[str, Path]) -> Path:
        """Write the Markdown export to ``path`` and return it.

        Figures made from plots or image bytes are written into a
        ``<name>_files`` folder next to it.
        """
        from .renderers.markdown import MarkdownRenderer

        path = Path(path)
        assets_dir, assets_url = _assets_for(path)
        text = MarkdownRenderer(assets_dir=assets_dir, assets_url=assets_url).render(self)
        path.write_text(text, encoding="utf-8")
        return path

    def save_html(
        self, path: Union[str, Path], full_document: bool = True, css: Optional[str] = None
    ) -> Path:
        """Write the HTML export to ``path`` and return it."""
        path = Path(path)
        path.write_text(self.to_html(full_document=full_document, css=css), encoding="utf-8")
        return path

    def save_latex(
        self,
        path: Union[str, Path],
        full_document: bool = True,
        document_class: str = "article",
        class_options: str = "11pt,a4paper",
        preamble: str = "",
        numbered: bool = False,
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
        ).render(self)
        path.write_text(text, encoding="utf-8")
        return path

    def save_pdf(
        self,
        path: Union[str, Path],
        fonts: Optional[Sequence[str]] = None,
        mono_fonts: Optional[Sequence[str]] = None,
    ) -> Path:
        """Write the PDF export to ``path`` and return it (requires fpdf2)."""
        path = Path(path)
        path.write_bytes(self.to_pdf(fonts=fonts, mono_fonts=mono_fonts))
        return path


def _assets_for(path: Path) -> tuple[Path, str]:
    """Folder for a saved document's figure files, and how the document
    refers to it (relative, so the output can be moved as a whole)."""
    folder = f"{path.stem}_files"
    return path.parent / folder, f"{folder}/"
