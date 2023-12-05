"""watchtower command line.

    watchtower sources list                     table of configured sources
    watchtower collect --source <id> [--since 2026-10-01T00:00:00Z] [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys

from watchtower import __version__
from watchtower.collectors import get_collector
from watchtower.collectors.base import Strongbox, credential_ref, ship
from watchtower.sources import (
    DEFAULT_CONFIG,
    SourceConfigError,
    get_source,
    load_sources,
)


def _since(value: str | None, interval_minutes: int) -> dt.datetime:
    if value:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    # one interval plus a five-minute overlap; the ingest API de-duplicates on (source, raw id)
    return dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=interval_minutes + 5)


def cmd_sources_list(args: argparse.Namespace) -> int:
    sources = load_sources(args.config)
    rows = [("ID", "TYPE", "COLLECTOR", "EVERY", "ADDED", "NOTE")]
    for s in sources:
        rows.append((s.id, s.type, s.collector, f"{s.interval_minutes}m", s.added.isoformat(), s.note or ""))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]) - 1)]
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths, strict=False)) + "  " + r[-1])
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    source = get_source(load_sources(args.config), args.source)
    since = _since(args.since, source.interval_minutes)
    cls = get_collector(source.collector)
    if args.dry_run:
        print("\n".join(cls(source).describe(since)))
        print(f"credential: strongbox://{credential_ref(source)}")
        return 0
    collector = cls(source, credentials=Strongbox().read(credential_ref(source)))
    ship(collector.collect(since))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="watchtower", description="Watchtower collectors and sources")
    p.add_argument("--version", action="version", version=f"watchtower {__version__}")
    p.add_argument("--config", default=str(DEFAULT_CONFIG), help="path to sources.yaml")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    src = sub.add_parser("sources", help="inspect config/sources.yaml")
    src_sub = src.add_subparsers(dest="sources_command", required=True)
    src_sub.add_parser("list", help="list configured sources").set_defaults(func=cmd_sources_list)

    col = sub.add_parser("collect", help="run one collection pass for a source")
    col.add_argument("--source", required=True, help="source id from sources.yaml")
    col.add_argument("--since", help="ISO timestamp (UTC); default: one interval ago")
    col.add_argument("--dry-run", action="store_true", help="print the plan; no network calls")
    col.set_defaults(func=cmd_collect)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    try:
        return args.func(args)
    except SourceConfigError as e:
        for problem in e.problems:
            print(f"{args.config}: {problem}", file=sys.stderr)
        return 2
    except KeyError as e:
        print(e.args[0], file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
