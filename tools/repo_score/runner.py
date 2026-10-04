"""Aggregates every category check into a single :class:`ScoreReport`."""

from __future__ import annotations

from pathlib import Path

from .checks import architecture, ci, cleanliness, documentation, hygiene, testing
from .config import CATEGORY_WEIGHTS, validate_config
from .models import CategoryScore, CheckResult, ScoreReport
from .repo import RepoContext

CATEGORY_CHECKS = {
    "testing": testing.run,
    "architecture": architecture.run,
    "cleanliness": cleanliness.run,
    "ci": ci.run,
    "documentation": documentation.run,
    "hygiene": hygiene.run,
}


def score_repository(root: Path | str = ".") -> ScoreReport:
    """Run every category check against ``root`` and build the composite report."""

    validate_config()
    context = RepoContext(Path(root))
    categories = [
        CategoryScore(name=name, weight=CATEGORY_WEIGHTS[name], checks=list(check(context)))
        for name, check in CATEGORY_CHECKS.items()
    ]
    return ScoreReport(root=str(context.root), categories=categories)


def collect_failures(report: ScoreReport) -> list[tuple[str, CheckResult]]:
    """Flatten every failing check as ``(category, check)`` pairs."""

    return [(category.name, check) for category in report.categories for check in category.failures]