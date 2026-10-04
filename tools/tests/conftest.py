"""Shared fixtures and helpers for repository scorer tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.repo_score.models import CheckResult


def write(root: Path, relative: str, content: str) -> None:
    """Write a file (creating parents) inside a temporary repository."""

    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture()
def healthy_repo(tmp_path: Path) -> Path:
    """A minimal repository that should score well."""

    write(tmp_path, "README.md", "# Healthy\n\n" + ("Documentation body. " * 60))
    write(tmp_path, ".env.example", "API_KEY=\nDATABASE_URL=\n")
    write(tmp_path, ".gitignore", "node_modules/\n.env\n__pycache__/\n.venv/\n")
    write(tmp_path, ".editorconfig", "root = true\n")
    write(
        tmp_path,
        ".github/workflows/ci.yml",
        "on:\n  pull_request:\njobs:\n  web:\n    steps:\n"
        "      - run: npm run lint\n      - run: npm run typecheck\n"
        "      - run: npm run test\n      - run: npm run build\n",
    )
    write(tmp_path, "Dockerfile", "FROM python:3.11\n")
    write(tmp_path, "pytest.ini", "[pytest]\n")
    write(tmp_path, "apps/api/app/__init__.py", "")
    write(
        tmp_path,
        "apps/api/app/service.py",
        '"""Service module."""\n\n\ndef helper() -> int:\n    """Return a value."""\n\n    return 1\n',
    )
    write(tmp_path, "apps/api/tests/test_service.py", "from app.service import helper\n\n\ndef test_helper() -> None:\n    assert helper() == 1\n")
    return tmp_path


def _check(results: list[CheckResult], name: str) -> CheckResult:
    """Return the named check, failing loudly when it is absent."""

    for result in results:
        if result.name == name:
            return result
    raise AssertionError(f"check '{name}' not found in {[r.name for r in results]}")
