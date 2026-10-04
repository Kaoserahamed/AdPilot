"""Repository discovery helpers shared by every check module."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".idea",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "coverage",
        "dist",
        "node_modules",
        "playwright-report",
        "storage",
        "test-results",
        "venv",
    }
)

SOURCE_SUFFIXES = frozenset({".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"})

TEXT_SUFFIXES = frozenset(
    {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".md", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".txt"}
)

TEST_FILE_PATTERNS = ("test_", "_test.", ".test.", ".spec.")


@dataclass(frozen=True)
class SourceFile:
    """A readable source file plus its pre-split lines."""

    path: Path
    relative: str
    lines: tuple[str, ...]

    @property
    def line_count(self) -> int:
        return len(self.lines)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def is_test_path(relative: str) -> bool:
    """True when the relative path looks like a test file."""

    name = relative.replace("\\", "/").rsplit("/", 1)[-1]
    return any(pattern in name for pattern in TEST_FILE_PATTERNS)


class RepoContext:
    """Read-only accessor for the repository under analysis."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()

    def exists(self, relative: str) -> bool:
        return (self.root / relative).exists()

    def read(self, relative: str) -> str:
        path = self.root / relative
        if not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return ""

    def _is_ignored(self, relative_path: Path) -> bool:
        return any(part in IGNORED_DIRECTORIES for part in relative_path.parts)

    def iter_paths(self, suffixes: frozenset[str] | set[str] | None = None):
        """Yield ``(absolute_path, relative_path)`` for non-ignored files."""

        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(self.root)
            if self._is_ignored(relative):
                continue
            if suffixes is not None and path.suffix.lower() not in suffixes:
                continue
            yield path, relative.as_posix()

    def source_files(self) -> list[SourceFile]:
        """All non-test source files."""

        collected = []
        for path, relative in self.iter_paths(SOURCE_SUFFIXES):
            if is_test_path(relative):
                continue
            collected.append(self._load(path, relative))
        return collected

    def test_files(self) -> list[SourceFile]:
        """All recognised test files."""

        return [self._load(path, relative) for path, relative in self.iter_paths(SOURCE_SUFFIXES) if is_test_path(relative)]

    def markdown_files(self) -> list[str]:
        return [relative for _, relative in self.iter_paths({".md"})]

    def _load(self, path: Path, relative: str) -> SourceFile:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            raw = ""
        return SourceFile(path=path, relative=relative, lines=tuple(raw.splitlines()))

    def git(self, *args: str) -> str | None:
        """Run a git command, returning stdout or ``None`` when git is unavailable."""

        try:
            completed = subprocess.run(
                ["git", *args],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return completed.stdout if completed.returncode == 0 else None