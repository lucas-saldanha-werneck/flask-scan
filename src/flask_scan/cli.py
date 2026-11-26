from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from .report import to_markdown, to_stubs
from .scanner import scan_hooks, scan_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="flask-scan",
                                 description="List Flask routes and Flask-to-FastAPI migration effort.")
    ap.add_argument("path", help="a .py file or a folder")
    ap.add_argument("--format", choices=["markdown", "json", "stubs"], default="markdown")
    args = ap.parse_args(argv)
    routes = scan_path(args.path)
    if args.format == "json":
        print(json.dumps([asdict(r) for r in routes], indent=2))
    elif args.format == "stubs":
        print(to_stubs(routes))
    else:
        print(to_markdown(routes, scan_hooks(args.path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
