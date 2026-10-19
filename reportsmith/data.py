"""Build tables from structured data: records, CSV files and DataFrames.

pandas is never imported: DataFrames are read through their public
``columns`` / ``itertuples()`` interface, so reportsmith stays
dependency-free and works with any DataFrame-like object.
"""

from __future__ import annotations

import csv
import io
import numbers
import re
from collections.abc import Mapping
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Callable, Iterable, Optional, Sequence, Union

from .inline import Inline, TextLike

if TYPE_CHECKING:
    from .elements import Table

#: A format string such as ``"{:,.2f}"`` or a callable returning cell text.
CellFormat = Union[str, Callable[[Any], TextLike]]
#: One format for every numeric cell, or a per-column mapping.
Formats = Union[CellFormat, Mapping[Any, CellFormat], None]
#: Display headers, either one per selected column or a key -> label mapping.
Headers = Union[Sequence[TextLike], Mapping[Any, TextLike], None]

_INT_RE = re.compile(r"[+-]?(?:0|[1-9]\d*)")
_FLOAT_RE = re.compile(r"[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?|[+-]?\d+[eE][+-]?\d+")


def is_missing(value: Any) -> bool:
    """None, NaN (float, numpy or Decimal) and pandas ``NA`` / ``NaT``."""
    if value is None or type(value).__name__ in ("NAType", "NaTType"):
        return True
    return isinstance(value, numbers.Number) and value != value


def is_numeric(value: Any) -> bool:
    return isinstance(value, numbers.Number) and not isinstance(value, bool)


def parse_number(text: str) -> Union[str, int, float]:
    """Convert numeric-looking CSV text to int/float; leave everything else.

    Integers with leading zeros (IDs, ZIP codes) and thousands separators are
    kept as text so no information is lost.
    """
    stripped = text.strip()
    if _INT_RE.fullmatch(stripped):
        return int(stripped)
    if _FLOAT_RE.fullmatch(stripped):
        return float(stripped)
    return text


def build_table(
    keys: Sequence[Any],
    rows: Sequence[Sequence[Any]],
    *,
    columns: Optional[Sequence[Any]] = None,
    headers: Headers = None,
    formats: Formats = None,
    align: Optional[Sequence[str]] = None,
    missing: str = "",
    caption: str = "",
    label: str = "",
) -> "Table":
    """Shared core: select columns, format values and build a :class:`Table`."""
    from .elements import Table

    if columns is not None:
        unknown = [c for c in columns if c not in keys]
        if unknown:
            raise ValueError(f"Unknown column(s): {', '.join(map(repr, unknown))}")
        indices = [list(keys).index(c) for c in columns]
        keys = list(columns)
        rows = [[row[i] for i in indices] for row in rows]
    keys = list(keys)

    if headers is None:
        labels: list = [str(k) for k in keys]
    elif isinstance(headers, Mapping):
        _check_keys(headers, keys, "headers")
        labels = [headers.get(k, str(k)) for k in keys]
    else:
        labels = list(headers)
        if len(labels) != len(keys):
            raise ValueError(f"headers has {len(labels)} entries, expected {len(keys)}")

    if formats is None or isinstance(formats, str) or callable(formats):
        default_format, per_column = formats, {}
    else:
        _check_keys(formats, keys, "formats")
        default_format, per_column = None, dict(formats)

    columns_values = list(zip(*rows)) if rows else [() for _ in keys]
    if align is None:
        align = ["right" if _numeric_column(values) else "left" for values in columns_values]

    cells = [
        [
            _format(value, per_column.get(key), default_format, missing)
            for key, value in zip(keys, row)
        ]
        for row in rows
    ]
    return Table(labels, cells, caption=caption, align=align, label=label)


def from_records(
    records: Iterable[Mapping[Any, Any]],
    columns: Optional[Sequence[Any]] = None,
    **options: Any,
) -> "Table":
    records = list(records)
    for i, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise TypeError(f"Record {i} is a {type(record).__name__}, expected a mapping")
    keys: list = []
    for record in records:  # union of keys in first-seen order
        keys.extend(k for k in record if k not in keys)
    if columns is not None and records:
        # Unlike keys absent from some records (filled with ``missing``), a
        # column absent from every record is almost certainly a typo.
        unknown = [c for c in columns if c not in keys]
        if unknown:
            raise ValueError(f"Unknown column(s): {', '.join(map(repr, unknown))}")
    elif columns is not None:
        keys = list(columns)
    rows = [[record.get(k) for k in keys] for record in records]
    return build_table(keys, rows, columns=columns, **options)


def from_csv(
    source: Union[str, Path, IO[str]],
    columns: Optional[Sequence[str]] = None,
    *,
    delimiter: str = ",",
    encoding: str = "utf-8",
    parse_numbers: bool = True,
    **options: Any,
) -> "Table":
    if hasattr(source, "read"):
        text = source.read()
    else:
        text = Path(source).read_text(encoding=encoding)
    # utf-8-sig behaviour for any encoding: drop a leading byte-order mark.
    lines = list(csv.reader(io.StringIO(text.lstrip("﻿")), delimiter=delimiter))
    lines = [line for line in lines if line]  # skip blank lines
    if not lines:
        raise ValueError("CSV input is empty; expected a header row")
    keys, body = lines[0], lines[1:]
    rows: list[list] = []
    for n, line in enumerate(body, start=2):
        if len(line) > len(keys):
            raise ValueError(f"CSV line {n} has {len(line)} fields, expected {len(keys)}")
        values: list = [None if v == "" else v for v in line]
        rows.append(values + [None] * (len(keys) - len(values)))
    if parse_numbers:
        for i in range(len(keys)):
            # All or nothing per column, so a ZIP-code column holding both
            # "00501" and "90210" stays text instead of mixing types.
            parsed = [parse_number(row[i]) if row[i] is not None else None for row in rows]
            if all(p is None or not isinstance(p, str) for p in parsed):
                for row, value in zip(rows, parsed):
                    row[i] = value
    return build_table(keys, rows, columns=columns, **options)


def from_dataframe(
    df: Any,
    columns: Optional[Sequence[Any]] = None,
    *,
    index: bool = False,
    **options: Any,
) -> "Table":
    if not (hasattr(df, "columns") and hasattr(df, "itertuples")):
        raise TypeError(f"Expected a pandas-like DataFrame, got {type(df).__name__}")
    keys = list(df.columns)
    rows = [list(row) for row in df.itertuples(index=index, name=None)]
    if index:
        index_key = df.index.name if df.index.name is not None else ""
        keys = [index_key] + keys
        if columns is not None and index_key not in columns:
            columns = [index_key] + list(columns)
    return build_table(keys, rows, columns=columns, **options)


def _check_keys(mapping: Mapping, keys: Sequence[Any], what: str) -> None:
    unknown = [k for k in mapping if k not in keys]
    if unknown:
        raise ValueError(f"{what} names unknown column(s): {', '.join(map(repr, unknown))}")


def _numeric_column(values: Sequence[Any]) -> bool:
    present = [v for v in values if not is_missing(v)]
    return bool(present) and all(is_numeric(v) for v in present)


def _format(value: Any, column_format: Optional[CellFormat], default_format: Optional[CellFormat], missing: str) -> TextLike:
    if is_missing(value):
        return missing
    if isinstance(value, (list, tuple)):
        return value  # already TextLike (mixed str/Inline content)
    fmt = column_format
    if fmt is None and is_numeric(value):
        fmt = default_format  # a single format applies to numbers only
    if fmt is None:
        return value if isinstance(value, (str, Inline)) else str(value)
    if callable(fmt):
        return fmt(value)
    return fmt.format(value)
