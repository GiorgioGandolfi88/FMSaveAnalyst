"""Import saves from the command line.

    python -m fmsa.ingest CAREER.fmsa SAVE.fm [SAVE2.fm ...]

Saves are imported in the order given (oldest first).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from fmsa.ingest.importer import ImportRejected, import_save


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m fmsa.ingest")
    parser.add_argument("career", type=Path, help="career database (.fmsa), created if missing")
    parser.add_argument("saves", type=Path, nargs="+", help="Football Manager save files")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    status = 0
    for save in args.saves:
        print(f"Importing {save.name} ...", flush=True)
        try:
            result = import_save(args.career, save)
        except ImportRejected as exc:
            print(f"  rejected: {exc}")
            status = 1
            continue
        print(
            f"  import #{result.import_id}: {result.game} {result.build} "
            f"game date {result.game_date}, {result.seconds}s"
        )
        for r in result.readers:
            s = r.stats
            line = (
                f"    {r.reader:22s} {r.status:11s} rows={s.rows:<8d} new={s.inserted:<8d} "
                f"upd={s.updated:<6d} same={s.unchanged:<8d} closed={s.closed:<6d} {r.seconds}s"
            )
            print(line)
    try:
        import psutil

        mi = psutil.Process().memory_info()
        peak = getattr(mi, "peak_wset", mi.rss) / 2**20
        print(f"Peak memory: {peak:.0f} MB")
    except ImportError:
        pass
    print(f"Database size: {args.career.stat().st_size / 2**20:.0f} MB")
    return status


if __name__ == "__main__":
    sys.exit(main())
