"""Repository quality scorer for AdPilot.

Scores a checkout across weighted categories (testing, architecture, code
cleanliness, documentation, CI/CD, and repository hygiene) and reports a
composite grade. The rubric is an original construction from common
repository-health signals; see ``config`` for every tunable weight and threshold.

Usage::

    python -m tools.repo_score            # human-readable report
    python -m tools.repo_score --json     # machine-readable report
"""

from __future__ import annotations

from .models import CategoryScore, CheckResult, ScoreReport, Status, grade_for
from .repo import RepoContext
from .runner import score_repository

__all__ = [
    "CategoryScore",
    "CheckResult",
    "RepoContext",
    "ScoreReport",
    "Status",
    "grade_for",
    "score_repository",
]