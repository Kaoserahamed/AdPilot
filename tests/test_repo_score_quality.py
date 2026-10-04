"""Unit tests for cleanliness, documentation, CI, and hygiene categories."""

from __future__ import annotations

from pathlib import Path

from tools.repo_score.checks import ci, cleanliness, documentation, hygiene
from tools.repo_score.models import Status
from tools.repo_score.repo import RepoContext

from tests.conftest import _check, healthy_repo, write

# Assembled at runtime so this file does not itself trip the secret scanner.
FAKE_KEY = "8f2b91" + "c4d7e6a0f3b5c8d1e2f7a9b4c6d"
FAKE_KEY_HEADER = "-----BEGIN RSA" + " PRIVATE KEY-----"

# --- Code cleanliness -------------------------------------------------------


def test_debug_output_is_flagged(tmp_path: Path) -> None:
    write(tmp_path, "src/app.py", "print('debug')\n")
    assert _check(cleanliness.run(RepoContext(tmp_path)), "no_debug_output").status is Status.WARN


def test_entry_point_print_is_not_flagged(tmp_path: Path) -> None:
    write(tmp_path, "tools/cli.py", "print('output')\n")
    assert _check(cleanliness.run(RepoContext(tmp_path)), "no_debug_output").status is Status.PASS


def test_long_lines_are_flagged(tmp_path: Path) -> None:
    write(tmp_path, "src/app.py", "x = '" + "a" * 300 + "'\n")
    assert _check(cleanliness.run(RepoContext(tmp_path)), "line_length").status in {Status.WARN, Status.FAIL}


def test_todo_markers_are_flagged(tmp_path: Path) -> None:
    write(tmp_path, "src/app.py", "\n".join(["# TODO something"] * 12))
    assert _check(cleanliness.run(RepoContext(tmp_path)), "unresolved_markers").status in {Status.WARN, Status.FAIL}


# --- Documentation ----------------------------------------------------------


def test_missing_readme_fails(tmp_path: Path) -> None:
    assert _check(documentation.run(RepoContext(tmp_path)), "readme_present").status is Status.FAIL


def test_thin_readme_warns(tmp_path: Path) -> None:
    write(tmp_path, "README.md", "# Tiny\n")
    assert _check(documentation.run(RepoContext(tmp_path)), "readme_present").status is Status.WARN


def test_docstring_ratio_is_measured(tmp_path: Path) -> None:
    write(tmp_path, "src/app.py", "\n".join(["def handler() -> None:\n    pass"] * 2))
    assert _check(documentation.run(RepoContext(tmp_path)), "docstrings").status in {Status.WARN, Status.FAIL}


def test_documented_public_definitions_pass(tmp_path: Path) -> None:
    block = '"""Module-level function."""\n\n\ndef handler() -> int:\n    """Do a thing."""\n\n    return 1\n'
    write(tmp_path, "src/app.py", block * 2)
    assert _check(documentation.run(RepoContext(tmp_path)), "docstrings").status is Status.PASS


# --- CI ---------------------------------------------------------------------


def test_missing_ci_fails(tmp_path: Path) -> None:
    assert _check(ci.run(RepoContext(tmp_path)), "ci_configured").status is Status.FAIL


def test_ci_without_all_stages_warns(healthy_repo: Path) -> None:
    write(healthy_repo, ".github/workflows/ci.yml", "on:\n  pull_request:\njobs:\n  web:\n    steps:\n      - run: npm test\n")
    assert _check(ci.run(RepoContext(healthy_repo)), "ci_stages").status is Status.WARN


def test_full_ci_passes(healthy_repo: Path) -> None:
    assert _check(ci.run(RepoContext(healthy_repo)), "ci_stages").status is Status.PASS


# --- Hygiene ----------------------------------------------------------------


def test_missing_gitignore_fails(tmp_path: Path) -> None:
    assert _check(hygiene.run(RepoContext(tmp_path)), "gitignore_present").status is Status.FAIL


def test_incomplete_gitignore_warns(tmp_path: Path) -> None:
    write(tmp_path, ".gitignore", "*.log\n")
    assert _check(hygiene.run(RepoContext(tmp_path)), "gitignore_present").status is Status.WARN


def test_real_secret_is_detected(tmp_path: Path) -> None:
    write(tmp_path, "config.py", f'API_KEY = "{FAKE_KEY}"\n')
    assert _check(hygiene.run(RepoContext(tmp_path)), "no_committed_secrets").status is Status.FAIL


def test_secret_suppression_marker_is_honoured(tmp_path: Path) -> None:
    write(tmp_path, "config.py", f'API_KEY = "{FAKE_KEY}"  # repo-score: allow-secret\n')
    assert _check(hygiene.run(RepoContext(tmp_path)), "no_committed_secrets").status is Status.PASS


def test_placeholder_secret_is_allowed(tmp_path: Path) -> None:
    write(tmp_path, ".env.example", 'API_KEY="your_api_key_here"\n')
    assert _check(hygiene.run(RepoContext(tmp_path)), "no_committed_secrets").status is Status.PASS


def test_private_key_block_is_detected(tmp_path: Path) -> None:
    write(tmp_path, "key.pem", f"{FAKE_KEY_HEADER}\nabc\n")
    assert _check(hygiene.run(RepoContext(tmp_path)), "no_committed_secrets").status is Status.FAIL