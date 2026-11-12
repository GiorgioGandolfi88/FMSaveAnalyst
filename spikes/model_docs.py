"""Step 0 spike: dump every fmsave record type with field types, status and docstring text.

Usage:
    python spikes/model_docs.py > docs/fmsave-models.md

Needs no save file: it introspects the installed fmsave package.
"""

from __future__ import annotations

import dataclasses
import inspect
import re
import typing

import fmsave

ATTR_LINE = re.compile(r"^\s{4}(\w+):\s?(.*)$")


def attribute_docs(cls: type) -> dict[str, str]:
    out: dict[str, str] = {}
    in_attrs = False
    current = None
    for line in (inspect.getdoc(cls) or "").splitlines():
        if line.strip() == "Attributes:":
            in_attrs = True
            continue
        if not in_attrs:
            continue
        m = ATTR_LINE.match(line)
        if m:
            current = m.group(1)
            out[current] = m.group(2).strip()
        elif current and line.strip():
            out[current] += " " + line.strip()
    return out


def type_name(tp: object) -> str:
    s = str(tp).replace("typing.", "").replace("fmsave.models.", "")
    return re.sub(r"<class '([\w.]+)'>", lambda m: m.group(1).split(".")[-1], s)


def main() -> None:
    record_types = sorted(
        (
            obj
            for name, obj in vars(fmsave).items()
            if inspect.isclass(obj) and dataclasses.is_dataclass(obj)
        ),
        key=lambda c: c.__name__,
    )
    print("# fmsave record types (generated)\n")
    print(f"fmsave {fmsave.__version__}, OUTPUT_SCHEMA_VERSION={fmsave.OUTPUT_SCHEMA_VERSION}\n")
    for cls in record_types:
        try:
            hints = typing.get_type_hints(cls)
        except Exception:
            hints = {}
        docs = attribute_docs(cls)
        summary = (inspect.getdoc(cls) or "").splitlines()[0] if cls.__doc__ else ""
        print(f"## {cls.__name__}\n\n{summary}\n")
        print("| field | type | status | description |\n|---|---|---|---|")
        for f in dataclasses.fields(cls):
            try:
                status = str(fmsave.field_status(cls, f.name)).split(".")[-1]
            except Exception:
                status = ""
            desc = docs.get(f.name, "").replace("|", "\\|")
            tname = type_name(hints.get(f.name, f.type)).replace("|", "\\|")
            print(f"| {f.name} | `{tname}` | {status} | {desc} |")
        print()


if __name__ == "__main__":
    main()
