"""Unit tests for report aggregation, rendering, and the command line interface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.repo_score import config, score_repository
from tools.repo_score.cli import main
from tools.repo_score.report import to_json, to_text

from tools.tests.conftest import _check, healthy_repo, write
# --- Aggregation and reporting ---------------------------------------------


def test_healthy_repo_scores_well(healthy_repo: Path) -> None:
    report = score_repository(healthy_repo)
    assert report.score > 70
    assert {category.name for category in report.categories} == set(config.CATEGORY_WEIGHTS)


def test_composite_is_weighted_average(healthy_repo: Path) -> None:
    report = score_repository(healthy_repo)
    expected = round(sum(category.score * category.weight for category in report.categories), 1)
    assert report.score == expected


def test_json_report_is_serialisable(healthy_repo: Path) -> None:
    report = score_repository(healthy_repo)
    payload = json.loads(to_json(report))
    assert payload["grade"] == report.grade
    assert len(payload["categories"]) == len(report.categories)


def test_text_report_includes_score_and_findings(healthy_repo: Path) -> None:
    write(healthy_repo, "src/app.py", "print('x')\n")
    text = to_text(score_repository(healthy_repo))
    assert "Score:" in text
    assert "no_debug_output" in text


# --- CLI --------------------------------------------------------------------


def test_cli_returns_zero_for_generous_threshold(healthy_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(healthy_repo), "--fail-under", "10"]) == 0
    capsys.readouterr()


def test_cli_returns_one_when_below_threshold(healthy_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(healthy_repo), "--fail-under", "99"]) == 1
    capsys.readouterr()


def test_cli_strict_flag_fails_on_failing_checks(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write(tmp_path, "src/app.py", "x = 1\n")
    assert main([str(tmp_path), "--strict"]) == 1
    capsys.readouterr()


def test_cli_emits_json(healthy_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main([str(healthy_repo), "--json"])
    assert "categories" in json.loads(capsys.readouterr().out)


def test_scoring_the_real_repository() -> None:
    """The scorer must run cleanly against the actual project checkout."""

    report = score_repository(Path(__file__).resolve().parents[1])
    assert 0 <= report.score <= 100
    assert report.grade in {"A", "B", "C", "D", "F"}