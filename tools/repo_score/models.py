"""Scoring data structures for the repository quality scorer.

A score is always decomposable: every point in a category total traces back to
a named check with a human-readable message. That is deliberate — an opaque
single number is not actionable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    """Outcome of a single check."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


STATUS_POINTS: dict[Status, float] = {
    Status.PASS: 100.0,
    Status.WARN: 60.0,
    Status.FAIL: 0.0,
    Status.SKIP: 100.0,
}

GRADE_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (90.0, "A"),
    (80.0, "B"),
    (70.0, "C"),
    (60.0, "D"),
)


def grade_for(score: float) -> str:
    """Map a 0-100 composite score onto a letter grade."""

    for threshold, letter in GRADE_THRESHOLDS:
        if score >= threshold:
            return letter
    return "F"


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one named check inside a category."""

    name: str
    status: Status
    message: str
    weight: float = 1.0

    @property
    def points(self) -> float:
        return STATUS_POINTS[self.status]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "weight": self.weight,
        }


@dataclass
class CategoryScore:
    """Weighted collection of checks that rolls up into one category score."""

    name: str
    weight: float
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def score(self) -> float:
        total = sum(check.weight for check in self.checks)
        if total <= 0:
            return 0.0
        earned = sum(check.points * check.weight for check in self.checks)
        return round(earned / total, 1)

    @property
    def failures(self) -> list[CheckResult]:
        return [check for check in self.checks if check.status is Status.FAIL]

    @property
    def warnings(self) -> list[CheckResult]:
        return [check for check in self.checks if check.status is Status.WARN]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "weight": self.weight,
            "score": self.score,
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass
class ScoreReport:
    """Full repository score across all categories."""

    root: str
    categories: list[CategoryScore] = field(default_factory=list)

    @property
    def score(self) -> float:
        total = sum(category.weight for category in self.categories)
        if total <= 0:
            return 0.0
        earned = sum(category.score * category.weight for category in self.categories)
        return round(earned / total, 1)

    @property
    def grade(self) -> str:
        return grade_for(self.score)

    @property
    def passed(self) -> bool:
        """True when no category contains a failing check."""

        return not any(category.failures for category in self.categories)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "score": self.score,
            "grade": self.grade,
            "passed": self.passed,
            "categories": [category.to_dict() for category in self.categories],
        }
