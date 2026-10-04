"""Architecture category: module boundaries, file size, and import direction."""

from __future__ import annotations

import ast
import re
from collections import defaultdict

from ..config import (
    MAX_FUNCTION_LINES_FAIL,
    MAX_FUNCTION_LINES_WARN,
    MAX_MODULE_LINES_PASS,
)
from ..models import CheckResult, Status
from ..repo import RepoContext, SourceFile

PY_IMPORT = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.MULTILINE)
TS_IMPORT = re.compile(r"""^\s*(?:import|export).*?from\s+['"]([^'"]+)['"]""", re.MULTILINE)


def _python_modules(files: list[SourceFile]) -> dict[str, SourceFile]:
    modules = {}
    for source in files:
        if source.relative.endswith(".py") and "/app/" in f"/{source.relative}":
            name = source.relative.split("/app/", 1)[1].removesuffix(".py").replace("/", ".")
            if name != "__init__" and not name.endswith(".__init__"):
                modules[name] = source
    return modules


def _longest_functions(source: SourceFile) -> list[tuple[str, int]]:
    if not source.relative.endswith(".py"):
        return []
    try:
        tree = ast.parse("\n".join(source.lines))
    except SyntaxError:
        return []
    spans: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            spans.append((node.name, (node.end_lineno or node.lineno) - node.lineno + 1))
    return spans


def _cycles(edges: dict[str, set[str]]) -> list[list[str]]:
    found: list[list[str]] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def walk(node: str, path: list[str]) -> None:
        if node in visiting:
            found.append(path[path.index(node) :] if node in path else path)
            return
        if node in visited:
            return
        visiting.add(node)
        for neighbour in sorted(edges.get(node, ())):
            walk(neighbour, [*path, neighbour])
        visiting.discard(node)
        visited.add(node)

    for node in sorted(edges):
        walk(node, [node])
    return found


def run(context: RepoContext) -> list[CheckResult]:
    results: list[CheckResult] = []
    sources = context.source_files()

    if not sources:
        return [CheckResult(name="source_detected", status=Status.FAIL, message="No source files found", weight=3.0)]

    oversized = [source for source in sources if source.line_count > MAX_MODULE_LINES_PASS]
    if not oversized:
        status, message = Status.PASS, f"All {len(sources)} source file(s) are within {MAX_MODULE_LINES_PASS} lines"
    elif len(oversized) * 2 <= len(sources):
        status, message = Status.WARN, f"{len(oversized)} source file(s) exceed {MAX_MODULE_LINES_PASS} lines"
    else:
        status, message = Status.FAIL, f"{len(oversized)} of {len(sources)} source files exceed {MAX_MODULE_LINES_PASS} lines"
    results.append(CheckResult(name="module_size", status=status, message=message, weight=2.0))

    longest: tuple[str, int] = ("", 0)
    too_long: list[str] = []
    for source in sources:
        for name, length in _longest_functions(source):
            if length > longest[1]:
                longest = (f"{source.relative}:{name}", length)
            if length > MAX_FUNCTION_LINES_WARN:
                too_long.append(f"{source.relative}:{name}")
    if longest[1] > MAX_FUNCTION_LINES_FAIL:
        status, message = Status.FAIL, f"{len(too_long)} function(s) exceed {MAX_FUNCTION_LINES_WARN} lines; longest is {longest[0]} ({longest[1]})"
    elif longest[1] > MAX_FUNCTION_LINES_WARN:
        status, message = Status.WARN, f"Longest function is {longest[0]} ({longest[1]} lines)"
    else:
        status, message = Status.PASS, f"Longest function is {longest[0] or 'n/a'} ({longest[1]} lines)"
    results.append(CheckResult(name="function_size", status=status, message=message, weight=2.0))

    modules = _python_modules(sources)
    edges: dict[str, set[str]] = defaultdict(set)
    for name, source in modules.items():
        for match in PY_IMPORT.finditer(source.text):
            imported = (match.group(1) or match.group(2) or "").lstrip(".")
            target = imported if imported in modules else None
            if target and target != name:
                edges[name].add(target)

    cycles = _cycles(edges)
    if cycles:
        preview = cycles[0]
        status, message = Status.FAIL, f"{len(cycles)} circular import cycle(s) detected, e.g. {' -> '.join(preview)}"
    else:
        status, message = Status.PASS, f"No circular imports across {len(modules)} backend module(s)"
    results.append(CheckResult(name="no_import_cycles", status=status, message=message, weight=2.5))

    interface_modules = sorted(name for name in modules if name.count(".") == 0)
    results.append(
        CheckResult(
            name="layered_structure",
            status=Status.PASS if len(interface_modules) <= 8 else Status.WARN,
            message=f"{len(interface_modules)} top-level API module(s) registered: {', '.join(interface_modules) or 'none'}",
            weight=1.0,
        )
    )

    return results
