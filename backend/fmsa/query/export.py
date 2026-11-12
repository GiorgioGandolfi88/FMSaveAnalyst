"""Write query results as CSV or JSON files."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from typing import IO, Any, Literal

ExportFormat = Literal["csv", "csv_excel", "json"]
EXTENSIONS: dict[str, str] = {"csv": ".csv", "csv_excel": ".csv", "json": ".json"}


def write_export(
    fmt: ExportFormat, columns: list[str], rows: Iterable[list[Any]], out: IO[str]
) -> int:
    """Write rows to a text stream; returns the number of rows written.

    csv: comma separated, UTF-8. csv_excel: semicolon separated (as Excel expects with Italian
    and most European regional settings); the caller opens the file as UTF-8 with BOM.
    json: an array of objects, one per row.
    """
    n = 0
    if fmt == "json":
        out.write("[")
        for row in rows:
            out.write(",\n" if n else "\n")
            out.write(json.dumps(dict(zip(columns, row, strict=True)), ensure_ascii=False))
            n += 1
        out.write("\n]\n")
        return n
    writer = csv.writer(out, delimiter=";" if fmt == "csv_excel" else ",", lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
        n += 1
    return n
