"""Command line entry point: ``python -m tools.repo_score``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .report import to_json, to_text
from .runner import score_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="repo_score", description="Score repository quality across weighted categories.")
    parser.add_argument("path", nargs="?", default=".", help="Repository root to score (default: current directory)")
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON")
    parser.add_argument("--verbose", action="store_true", help="Include passing checks in the text report")
    parser.add_argument("--fail-under", type=float, default=None, help="Exit non-zero when the score is below this value")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any check fails")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = score_repository(Path(args.path))

    if args.json:
        print(to_json(report))
    else:
        print(to_text(report, verbose=args.verbose))

    if args.fail_under is not None and report.score < args.fail_under:
        print(f"error: score {report.score:.1f} is below the required {args.fail_under:.1f}", file=sys.stderr)
        return 1
    if args.strict and not report.passed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())