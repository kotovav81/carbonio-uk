"""Initial CLI placeholder; commands are implemented incrementally."""

from __future__ import annotations

import argparse

from . import audit, discovery, fetch, glossary, live_compare, manual, merge, package_overlay, pilot, report, review, staged_merge, translate, validate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="carbonio-uk")
    parser.add_argument("--version", action="version", version="carbonio-uk 0.1.0")
    subparsers = parser.add_subparsers(dest="command")
    discovery.add_parser(subparsers)
    fetch.add_parser(subparsers)
    audit.add_parser(subparsers)
    validate.add_parser(subparsers)
    glossary.add_parser(subparsers)
    translate.add_parser(subparsers)
    pilot.add_parser(subparsers)
    manual.add_parser(subparsers)
    live_compare.add_parser(subparsers)
    review.add_parser(subparsers)
    merge.add_parser(subparsers)
    staged_merge.add_parser(subparsers)
    package_overlay.add_parser(subparsers)
    report.add_parser(subparsers)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return 0
    if hasattr(args, "handler"):
        return args.handler(args)
    parser.error(f"command not implemented yet: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
