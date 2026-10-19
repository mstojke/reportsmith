"""Image assets for figures: files written next to a document, or data URIs."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional, Union

_MIME = {"png": "image/png", "jpeg": "image/jpeg", "gif": "image/gif", "svg": "image/svg+xml"}


def data_uri(data: bytes, fmt: str) -> str:
    return f"data:{_MIME[fmt]};base64,{base64.b64encode(data).decode('ascii')}"


class Assets:
    """Writes generated figure images into ``directory`` (created on first
    use) as ``figure-1.png``, ``figure-2.pdf``, ...; :meth:`write` returns
    the reference to put in the document: ``url_prefix`` + file name."""

    def __init__(self, directory: Union[str, Path], url_prefix: Optional[str] = None):
        self.directory = Path(directory)
        self.url_prefix = self.directory.as_posix() + "/" if url_prefix is None else url_prefix
        self._count = 0

    def write(self, data: bytes, fmt: str) -> str:
        self._count += 1
        name = f"figure-{self._count}.{'jpg' if fmt == 'jpeg' else fmt}"
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / name).write_bytes(data)
        return self.url_prefix + name


def path_reference(source: Union[str, Path]) -> str:
    """How a figure's source path is written in the document."""
    return source.as_posix() if isinstance(source, Path) else source
