"""Unit tests for models, repository discovery, and the testing/architecture checks.

Each check is exercised against a synthetic repository so the scoring logic is
verified independently of the real checkout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.repo_score import config
from tools.repo_score.checks import architecture, testing
from tools.repo_score.models import CategoryScore, CheckResult, Status, grade_for
from tools.repo_score.repo import RepoContext, is_test_path

from tests.conftest import _check, healthy_repo, write


# --- Models and config ------------------------------------------------------


def test_category_weights_sum_to_one() -> None:
    config.validate_config()


def test_invalid_weights_are_rejected() -> None:
    with pytest.raises(ValueError):
        config.validate_config({"testing": 0.5, "architecture": 0.2})
    with pytest.raises(ValueError):
        config.validate_config({"testing": 0.0})


@pytest.mark.parametrize(
    ("score", "expected"),
    [(100.0, "A"), (92.5, "A"), (81.0, "B"), (75.0, "C"), (61.0, "D"), (12.0, "F")],
)
def test_grade_boundaries(score: float, expected: str) -> None:
    assert grade_for(score) == expected


def test_category_score_is_weight_normalised() -> None:
    category = CategoryScore(
        name="demo",
        weight=1.0,
        checks=[
            CheckResult(name="a", status=Status.PASS, message=""),
            CheckResult(name="b", status=Status.FAIL, message=""),
        ],
    )
    assert category.score == 50.0


def test_empty_category_scores_zero() -> None:
    assert CategoryScore(name="demo", weight=1.0).score == 0.0


# --- Repo discovery ---------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("apps/api/tests/test_thing.py", True),
        ("apps/web/src/data.test.ts", True),
        ("apps/web/src/thing.spec.tsx", True),
        ("apps/api/app/service.py", False),
    ],
)
def test_test_path_detection(path: str, expected: bool) -> None:
    assert is_test_path(path) is expected


def test_context_ignores_vendor_directories(tmp_path: Path) -> None:
    write(tmp_path, "src/app.py", "x = 1\n")
    write(tmp_path, "node_modules/pkg/index.js", "module.exports = 1\n")
    context = RepoContext(tmp_path)
    assert {source.relative for source in context.source_files()} == {"src/app.py"}


# --- Testing category -------------------------------------------------------


def test_missing_tests_fails_heavily(tmp_path: Path) -> None:
    write(tmp_path, "src/app.py", "x = 1\n")
    assert _check(testing.run(RepoContext(tmp_path)), "tests_present").status is Status.FAIL


def test_healthy_repo_passes_testing(healthy_repo: Path) -> None:
    results = testing.run(RepoContext(healthy_repo))
    assert _check(results, "tests_present").status is Status.PASS
    assert _check(results, "test_framework_configured").message.endswith("pytest")
    assert _check(results, "test_to_source_ratio").status is Status.PASS


def test_low_test_ratio_warns(tmp_path: Path) -> None:
    for index in range(3):
        write(tmp_path, f"src/module_{index}.py", "x = 1\n")
    write(tmp_path, "tests/test_one.py", "def test_one() -> None:\n    assert True\n")
    write(tmp_path, "pytest.ini", "[pytest]\n")
    assert _check(testing.run(RepoContext(tmp_path)), "test_to_source_ratio").status is Status.WARN


def test_very_low_test_ratio_fails(tmp_path: Path) -> None:
    for index in range(10):
        write(tmp_path, f"src/module_{index}.py", "x = 1\n")
    write(tmp_path, "tests/test_one.py", "def test_one() -> None:\n    assert True\n")
    write(tmp_path, "pytest.ini", "[pytest]\n")
    assert _check(testing.run(RepoContext(tmp_path)), "test_to_source_ratio").status is Status.FAIL


# --- Architecture category --------------------------------------------------


def test_import_cycles_are_detected(tmp_path: Path) -> None:
    write(tmp_path, "apps/api/app/__init__.py", "")
    write(tmp_path, "apps/api/app/a.py", "from .b import value_b\n")
    write(tmp_path, "apps/api/app/b.py", "from .a import value_a\n")
    assert _check(architecture.run(RepoContext(tmp_path)), "no_import_cycles").status is Status.FAIL


def test_acyclic_imports_pass(tmp_path: Path) -> None:
    write(tmp_path, "apps/api/app/__init__.py", "")
    write(tmp_path, "apps/api/app/a.py", "from .b import value_b\n")
    write(tmp_path, "apps/api/app/b.py", "VALUE = 1\n")
    assert _check(architecture.run(RepoContext(tmp_path)), "no_import_cycles").status is Status.PASS


def test_oversized_module_fails(healthy_repo: Path) -> None:
    write(healthy_repo, "apps/api/app/huge.py", "\n".join(["x = 1"] * 900))
    assert _check(architecture.run(RepoContext(healthy_repo)), "module_size").status in {Status.WARN, Status.FAIL}


def test_long_function_is_flagged(healthy_repo: Path) -> None:
    body = "\n".join(["    x = 1"] * 200)
    write(healthy_repo, "apps/api/app/long.py", f"def sprawling() -> None:\n{body}\n")
    assert _check(architecture.run(RepoContext(healthy_repo)), "function_size").status in {Status.WARN, Status.FAIL}