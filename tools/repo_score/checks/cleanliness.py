"""Code cleanliness category: formatting, debug debris, and leftover markers."""

from __future__ import annotations

import re

from ..config import (
    DEBUG_OUTPUT_EXEMPT,
    MAX_DEBUG_MARKERS_FAIL,
    MAX_DEBUG_MARKERS_WARN,
    MAX_LINE_LENGTH_WARN,
    MAX_STRIPPED_BLANK_RATIO,
)
from ..models import CheckResult, Status
from ..repo import RepoContext

MARKER = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
DEBUG_PRINT = re.compile(r"\bprint\s*\(")
CONSOLE_LOG = re.compile(r"\bconsole\.(log|debug|dir|table)\s*\(")
TRAILING_WHITESPACE = re.compile(r"[ \t]+$")
TAB_INDENT = re.compile(r"^\t+")


def _is_exempt(relative: str) -> bool:
    """True for entry-point files where printing to stdout is intentional."""

    return any(marker in relative for marker in DEBUG_OUTPUT_EXEMPT)


def run(context: RepoContext) -> list[CheckResult]:
    results: list[CheckResult] = []
    sources = context.source_files()

    long_lines: list[str] = []
    for source in sources:
        for number, line in enumerate(source.lines, start=1):
            if len(line.expandtabs(4)) > MAX_LINE_LENGTH_WARN:
                long_lines.append(f"{source.relative}:{number}")
    if not long_lines:
        results.append(
            CheckResult(
                name="line_length",
                status=Status.PASS,
                message=f"No line exceeds {MAX_LINE_LENGTH_WARN} characters",
                weight=1.5,
            )
        )
    else:
        results.append(
            CheckResult(
                name="line_length",
                status=Status.FAIL if len(long_lines) > 10 else Status.WARN,
                message=f"{len(long_lines)} line(s) exceed {MAX_LINE_LENGTH_WARN} characters",
                weight=1.5,
            )
        )

    markers = [
        f"{source.relative}:{number}"
        for source in sources
        for number, line in enumerate(source.lines, start=1)
        if MARKER.search(line)
    ]
    if len(markers) <= MAX_DEBUG_MARKERS_WARN:
        results.append(CheckResult(name="unresolved_markers", status=Status.PASS, message=f"{len(markers)} TODO/FIXME marker(s)", weight=1.0))
    elif len(markers) <= MAX_DEBUG_MARKERS_FAIL:
        results.append(CheckResult(name="unresolved_markers", status=Status.WARN, message=f"{len(markers)} TODO/FIXME markers, e.g. {markers[0]}", weight=1.0))
    else:
        results.append(CheckResult(name="unresolved_markers", status=Status.FAIL, message=f"{len(markers)} unresolved markers exceed {MAX_DEBUG_MARKERS_FAIL}", weight=1.0))

    stray = [
        f"{source.relative}:{number}"
        for source in sources
        if not _is_exempt(source.relative)
        for number, line in enumerate(source.lines, start=1)
        if DEBUG_PRINT.search(line) or CONSOLE_LOG.search(line)
    ]
    if not stray:
        results.append(CheckResult(name="no_debug_output", status=Status.PASS, message="No stray print/console statements in source", weight=1.5))
    else:
        results.append(
            CheckResult(
                name="no_debug_output",
                status=Status.FAIL if len(stray) > 5 else Status.WARN,
                message=f"{len(stray)} debug statement(s) left in source, e.g. {stray[0]}",
                weight=1.5,
            )
        )

    trailing = sum(1 for source in sources for line in source.lines if TRAILING_WHITESPACE.search(line))
    tabbed = sum(1 for source in sources for line in source.lines if TAB_INDENT.match(line))
    total_lines = sum(source.line_count for source in sources) or 1
    density = (trailing + tabbed) / total_lines
    if density == 0:
        results.append(CheckResult(name="whitespace_hygiene", status=Status.PASS, message="No trailing whitespace or tab indentation", weight=1.0))
    else:
        status = Status.PASS if density <= MAX_STRIPPED_BLANK_RATIO else Status.WARN
        results.append(
            CheckResult(
                name="whitespace_hygiene",
                status=status,
                message=f"{trailing} trailing-whitespace and {tabbed} tab-indented line(s)",
                weight=1.0,
            )
        )

    return results
