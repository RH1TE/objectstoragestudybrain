from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from .index import search
from .pipeline import sync
from .settings import Settings


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _storage_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--bucket", default=os.getenv("STUDY_BRAIN_BUCKET"))
    parser.add_argument("--source-prefix", default=os.getenv("STUDY_BRAIN_SOURCE_PREFIX", ""))
    parser.add_argument("--derived-prefix", default=os.getenv("STUDY_BRAIN_DERIVED_PREFIX"))
    parser.add_argument("--endpoint-url", default=os.getenv("STUDY_BRAIN_ENDPOINT_URL"))
    parser.add_argument("--region", default=os.getenv("STUDY_BRAIN_REGION"))
    parser.add_argument("--profile", default=os.getenv("STUDY_BRAIN_PROFILE"))
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(os.getenv("STUDY_BRAIN_WORK_DIR", "work")),
    )


def _settings(args: argparse.Namespace) -> Settings:
    return Settings(
        bucket=args.bucket,
        work_dir=args.work_dir,
        source_prefix=args.source_prefix,
        derived_prefix=args.derived_prefix,
        endpoint_url=args.endpoint_url,
        region=args.region,
        profile=args.profile,
    )

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="studybrain")
    commands = parser.add_subparsers(dest="command", required=True)

    sync_parser = commands.add_parser("sync")
    _storage_args(sync_parser)
    sync_parser.add_argument(
        "--write-back",
        action="store_true",
        default=_env_bool("STUDY_BRAIN_WRITE_BACK"),
    )

    watch_parser = commands.add_parser("watch")
    _storage_args(watch_parser)
    watch_parser.add_argument(
        "--write-back",
        action="store_true",
        default=_env_bool("STUDY_BRAIN_WRITE_BACK"),
    )
    watch_parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("STUDY_BRAIN_INTERVAL", "60")),
    )

    search_parser = commands.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(os.getenv("STUDY_BRAIN_WORK_DIR", "work")),
    )
    search_parser.add_argument("--limit", type=int, default=5)

    return parser

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "search":
        rows = search(args.work_dir / "index.sqlite3", args.query, args.limit)
        print(json.dumps(rows, indent=2))
        return

    if not args.bucket:
        parser.error("--bucket or STUDY_BRAIN_BUCKET is required")

    settings = _settings(args)
    if args.command == "sync":
        print(json.dumps(sync(settings, write_back=args.write_back), indent=2))
        return

    if args.interval < 10:
        raise SystemExit("--interval must be at least 10 seconds")

    while True:
        result = sync(settings, write_back=args.write_back)
        print(json.dumps(result), flush=True)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
