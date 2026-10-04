"""Documentation category: README substance, env templates, and docstrings."""

from __future__ import annotations

import ast

from ..config import MIN_DOCSTRING_RATIO_PASS, MIN_DOCSTRING_RATIO_WARN, MIN_README_CHARS
from ..models import CheckResult, Status
from ..repo import RepoContext, SourceFile

DOCSTRING_PROBE = ('"""', "'''")


def _documented_definitions(source: SourceFile) -> tuple[int, int]:
    """Return ``(documented, total)`` for module-level functions and classes."""

    if not source.relative.endswith(".py"):
        return (0, 0)
    try:
        tree = ast.parse("\n".join(source.lines))
    except SyntaxError:
        return (0, 0)
    documented = 0
    total = 0
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            total += 1
            if ast.get_docstring(node):
                documented += 1
    return (documented, total)


def run(context: RepoContext) -> list[CheckResult]:
    results: list[CheckResult] = []

    readme = ""
    for name in ("README.md", "readme.md", "README.rst"):
        if context.exists(name):
            readme = context.read(name)
            break
    if not readme:
        results.append(CheckResult(name="readme_present", status=Status.FAIL, message="No README found at the repository root", weight=2.0))
    elif len(readme) < MIN_README_CHARS:
        results.append(
            CheckResult(
                name="readme_present",
                status=Status.WARN,
                message=f"README is only {len(readme)} characters; expected at least {MIN_README_CHARS}",
                weight=2.0,
            )
        )
    else:
        headings = readme.count("\n#")
        results.append(
            CheckResult(
                name="readme_present",
                status=Status.PASS,
                message=f"README has {len(readme)} characters and {headings} heading(s)",
                weight=2.0,
            )
        )

    results.append(
        CheckResult(
            name="env_example",
            status=Status.PASS if context.exists(".env.example") else Status.FAIL,
            message=".env.example is present" if context.exists(".env.example") else ".env.example is missing",
            weight=1.5,
        )
    )

    documented = total = 0
    for source in context.source_files():
        found_documented, found_total = _documented_definitions(source)
        documented += found_documented
        total += found_total
    if total == 0:
        results.append(
            CheckResult(
                name="docstrings",
                status=Status.SKIP,
                message="No Python module-level functions or classes to annotate",
                weight=1.0,
            )
        )
    else:
        ratio = documented / total
        if ratio >= MIN_DOCSTRING_RATIO_PASS:
            status, message = Status.PASS, f"{ratio:.0%} of public Python definitions carry docstrings"
        elif ratio >= MIN_DOCSTRING_RATIO_WARN:
            status, message = Status.WARN, f"Only {ratio:.0%} of public Python definitions carry docstrings"
        else:
            status, message = Status.FAIL, f"Just {ratio:.0%} of public Python definitions carry docstrings"
        results.append(CheckResult(name="docstrings", status=status, message=message, weight=1.5))

    markdown = context.markdown_files()
    results.append(
        CheckResult(
            name="documentation_files",
            status=Status.PASS if len(markdown) >= 2 else Status.WARN,
            message=f"{len(markdown)} Markdown document(s) in the repository",
            weight=1.0,
        )
    )

    return results