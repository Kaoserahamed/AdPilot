"""Repository hygiene category: ignore rules, secret exposure, and commit conventions."""

from __future__ import annotations

import re

from ..config import (
    COMMIT_SUBJECT_PATTERN,
    CONVENTIONAL_COMMIT_SAMPLE,
    REQUIRED_IGNORE_PATTERNS,
    SECRET_PATTERNS,
    SECRET_SUPPRESSION_MARKER,
    SECRET_VALUE_PATTERN,
)
from ..models import CheckResult, Status
from ..repo import RepoContext

SECRET_RE = [re.compile(pattern) for pattern in SECRET_PATTERNS]
SECRET_VALUE_RE = re.compile(SECRET_VALUE_PATTERN)
COMMIT_RE = re.compile(COMMIT_SUBJECT_PATTERN)

# Placeholders in committed templates are not real credentials.
SAFE_MARKERS = ("your_", "changeme", "placeholder", "example", "xxx", "<", "dummy")


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in SAFE_MARKERS)


def run(context: RepoContext) -> list[CheckResult]:
    return [
        *_ignore_rules(context),
        *_editorconfig(context),
        *_secrets(context),
        *_commits(context),
        *_worktree(context),
    ]


def _ignore_rules(context: RepoContext) -> list[CheckResult]:
    gitignore = context.read(".gitignore")
    if not gitignore:
        return [CheckResult(name="gitignore_present", status=Status.FAIL, message=".gitignore is missing", weight=2.0)]
    missing = [pattern for pattern in REQUIRED_IGNORE_PATTERNS if pattern not in gitignore]
    return [
        CheckResult(
            name="gitignore_present",
            status=Status.PASS if not missing else Status.WARN,
            message=".gitignore covers required patterns" if not missing else f".gitignore is missing: {', '.join(missing)}",
            weight=2.0,
        )
    ]


def _editorconfig(context: RepoContext) -> list[CheckResult]:
    present = context.exists(".editorconfig")
    return [
        CheckResult(
            name="editorconfig_present",
            status=Status.PASS if present else Status.WARN,
            message=".editorconfig is present" if present else ".editorconfig is missing",
            weight=1.0,
        )
    ]


def _secrets(context: RepoContext) -> list[CheckResult]:
    findings: list[str] = []
    for _, relative in context.iter_paths():
        if relative.endswith(".db"):
            continue
        text = context.read(relative)
        if text and _contains_secret(text):
            findings.append(relative)
    unique = sorted(set(findings))
    if unique:
        return [
            CheckResult(
                name="no_committed_secrets",
                status=Status.FAIL,
                message=f"Potential secret material in: {', '.join(unique[:3])}",
                weight=3.0,
            )
        ]
    return [CheckResult(name="no_committed_secrets", status=Status.PASS, message="No secret-like values found in tracked files", weight=3.0)]


def _contains_secret(text: str) -> bool:
    for line in text.splitlines():
        if SECRET_SUPPRESSION_MARKER in line:
            continue
        if any(pattern.search(line) for pattern in SECRET_RE):
            return True
        if any(not _is_placeholder(match.group(0)) for match in SECRET_VALUE_RE.finditer(line)):
            return True
    return False


def _commits(context: RepoContext) -> list[CheckResult]:
    log = context.git("log", f"-{CONVENTIONAL_COMMIT_SAMPLE}", "--pretty=format:%s")
    if not log:
        return [CheckResult(name="conventional_commits", status=Status.SKIP, message="Git history unavailable", weight=1.0)]
    subjects = [line.strip() for line in log.splitlines() if line.strip()]
    if not subjects:
        return [CheckResult(name="conventional_commits", status=Status.SKIP, message="No commits found", weight=1.0)]
    deviating = [subject for subject in subjects if not COMMIT_RE.match(subject)]
    if not deviating:
        return [
            CheckResult(
                name="conventional_commits",
                status=Status.PASS,
                message=f"All {len(subjects)} recent commits use Conventional Commits",
                weight=1.0,
            )
        ]
    ratio = 1 - (len(deviating) / len(subjects))
    return [
        CheckResult(
            name="conventional_commits",
            status=Status.PASS if ratio >= 0.8 else Status.WARN,
            message=f"{len(deviating)} of {len(subjects)} recent commits deviate, e.g. '{deviating[0][:60]}'",
            weight=1.0,
        )
    ]


def _worktree(context: RepoContext) -> list[CheckResult]:
    output = context.git("status", "--porcelain")
    if output is None:
        return [CheckResult(name="clean_worktree", status=Status.SKIP, message="Git status unavailable", weight=1.0)]
    dirty = [line for line in output.splitlines() if line.strip()]
    return [
        CheckResult(
            name="clean_worktree",
            status=Status.PASS if not dirty else Status.WARN,
            message="Working tree is clean" if not dirty else f"{len(dirty)} uncommitted change(s) in the working tree",
            weight=1.0,
        )
    ]
