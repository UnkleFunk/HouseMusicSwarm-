"""Command line: python -m resale_app <command>

    serve      run the web app (and the analysis worker)
    demo       fill a separate demo database with made-up items and run the app on it
    seed       load inventory from a CSV
    ingest     add image files or folders (what a Hazel rule calls)
    watch      poll the drop folder and ingest photos as they arrive
    analyze    read photos for queued items now (no web app needed)
    export     write a listing pack for one platform to a folder
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import os
import sys
from pathlib import Path

from . import config, db


def _settings():
    return config.get_settings()


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .app import create_app

    if args.demo:
        os.environ["RESALE_MODE"] = "demo"
    settings = _settings()
    print(f"Resale app on http://{args.host}:{args.port}  (mode: {settings.mode}, data: {settings.home})")
    if args.host not in ("127.0.0.1", "localhost") and not settings.access_token:
        print("Warning: listening beyond this machine with no RESALE_ACCESS_TOKEN set. Anyone on your network can use it.", file=sys.stderr)
    uvicorn.run(create_app(settings), host=args.host, port=args.port, log_level="info")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    from . import demo

    os.environ["RESALE_MODE"] = "demo"
    os.environ.setdefault("RESALE_HOME", str(config.PACKAGE_DIR / "data" / "demo"))
    settings = _settings()
    conn = db.connect(settings)
    try:
        n = demo.seed_demo(conn, settings)
    finally:
        conn.close()
    print(f"Demo data: {'created ' + str(n) + ' items' if n else 'already there'} in {settings.home}")
    args.demo = True
    return cmd_serve(args)


def cmd_seed(args: argparse.Namespace) -> int:
    from . import seed

    settings = _settings()
    path = Path(args.file).expanduser() if args.file else seed.DEFAULT_FILE
    if not path.is_file():
        print(f"No such file: {path}", file=sys.stderr)
        return 2
    if path == seed.DEFAULT_FILE:
        print(f"Using the sample inventory ({path}). Pass --file to load your own.")
    conn = db.connect(settings)
    try:
        summary = seed.seed(conn, settings, seed.load_rows(path), base_dir=path.parent, update=args.update)
        if args.analyze:
            for item in db.list_items(conn, status="intake"):
                if item["photo_count"]:
                    db.queue_analysis(conn, item["id"])
    finally:
        conn.close()
    print(f"created {summary.created}, updated {summary.updated}, unchanged {summary.skipped}, photos added {summary.photos_added}")
    for err in summary.errors:
        print("  " + err, file=sys.stderr)
    return 1 if summary.errors else 0


def cmd_ingest(args: argparse.Namespace) -> int:
    from .ingest import ingest_paths

    settings = _settings()
    results = ingest_paths([Path(p) for p in args.paths], settings, analyze=not args.no_analyze, move=not args.keep)
    failed = 0
    for r in results:
        if r.error:
            failed += 1
            print(f"FAILED  {r.path}: {r.error}", file=sys.stderr)
        else:
            note = "duplicate" if r.duplicate else ("new item" if r.created else "added")
            print(f"{r.sku}  {note}  {r.path}")
    if not results:
        print("No image files found.", file=sys.stderr)
        return 1
    return 1 if failed else 0


def cmd_watch(args: argparse.Namespace) -> int:
    from .watcher import Watcher

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    settings = _settings()
    if args.drop:
        settings = dataclasses.replace(settings, drop_dir=Path(args.drop).expanduser())
    watcher = Watcher(settings, stable_seconds=args.stable, analyze=not args.no_analyze)
    if args.once:
        # Two passes: the first records each file's size and time, the second sees them unchanged.
        watcher.scan()
        results = watcher.run_once()
        for r in results:
            print(f"{r.sku or '-'}  {r.error or ('duplicate' if r.duplicate else 'ok')}  {r.path}")
        return 0
    watcher.run_forever(args.interval)
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    from . import worker

    settings = _settings()
    conn = db.connect(settings)
    try:
        for sku in args.sku or []:
            item = db.get_item_by_sku(conn, sku)
            if item is None:
                print(f"No such item: {sku}", file=sys.stderr)
                return 2
            db.queue_analysis(conn, item["id"])
        conn.execute("UPDATE items SET analyze_after = 0 WHERE analysis_status = 'queued'")  # a CLI run is a deliberate "now"
        conn.commit()
    finally:
        conn.close()
    n = worker.drain(settings)
    print(f"Analysed {n} item(s) in {settings.mode} mode.")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from . import export
    from .platforms import PLATFORMS

    if args.platform not in PLATFORMS:
        print(f"Unknown platform. Choose from: {', '.join(PLATFORMS)}", file=sys.stderr)
        return 2
    settings = _settings()
    out = Path(args.out).expanduser() if args.out else Path.cwd() / "resale_export" / args.platform
    conn = db.connect(settings)
    try:
        path = export.write_pack(conn, settings, args.platform, out)
        n = len(export.build_entries(conn, args.platform))
    finally:
        conn.close()
    print(f"Wrote {n} approved {args.platform} listing(s) to {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m resale_app", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    def serve_args(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to reach it from your phone")
        sp.add_argument("--port", type=int, default=8090)

    sp = sub.add_parser("serve", help="run the web app")
    serve_args(sp)
    sp.add_argument("--demo", action="store_true", help="offline demo mode (no API calls)")
    sp.set_defaults(func=cmd_serve)

    sp = sub.add_parser("demo", help="demo database + web app, no API key needed")
    serve_args(sp)
    sp.set_defaults(func=cmd_demo)

    sp = sub.add_parser("seed", help="load inventory from a CSV")
    sp.add_argument("--file", help="CSV path (default: the bundled sample)")
    sp.add_argument("--update", action="store_true", help="update rows that already exist")
    sp.add_argument("--analyze", action="store_true", help="queue photo reading for seeded items that have photos")
    sp.set_defaults(func=cmd_seed)

    sp = sub.add_parser("ingest", help="add image files or folders as photos")
    sp.add_argument("paths", nargs="+")
    sp.add_argument("--no-analyze", action="store_true")
    sp.add_argument("--keep", action="store_true", help="leave files where they are (do not move to _processed)")
    sp.set_defaults(func=cmd_ingest)

    sp = sub.add_parser("watch", help="poll the drop folder")
    sp.add_argument("--drop", help="drop folder (default: $RESALE_DROP_DIR or ~/ResaleDrop)")
    sp.add_argument("--interval", type=float, default=3.0)
    sp.add_argument("--stable", type=float, default=5.0, help="seconds a file must be unchanged before ingest")
    sp.add_argument("--once", action="store_true", help="one scan and exit")
    sp.add_argument("--no-analyze", action="store_true")
    sp.set_defaults(func=cmd_watch)

    sp = sub.add_parser("analyze", help="read photos for queued items now")
    sp.add_argument("sku", nargs="*", help="also queue these SKUs (e.g. RS-0003)")
    sp.set_defaults(func=cmd_analyze)

    sp = sub.add_parser("export", help="write a platform's listing pack to a folder")
    sp.add_argument("platform")
    sp.add_argument("--out")
    sp.set_defaults(func=cmd_export)
    return p


def main(argv: list[str] | None = None) -> int:
    config.load_env_files()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
