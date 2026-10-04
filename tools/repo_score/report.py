"""Renders a :class:`ScoreReport` as text or JSON."""

from __future__ import annotations

import json

from .models import ScoreReport, Status

STATUS_MARK = {
    Status.PASS: "PASS",
    Status.WARN: "WARN",
    Status.FAIL: "FAIL",
    Status.SKIP: "SKIP",
}


def to_json(report: ScoreReport) -> str:
    return json.dumps(report.to_dict(), indent=2)


def to_text(report: ScoreReport, verbose: bool = False) -> str:
    lines: list[str] = []
    lines.append("AdPilot repository quality report")
    lines.append("=" * 62)
    lines.append(f"Root:  {report.root}")
    lines.append(f"Score: {report.score:.1f}/100   Grade: {report.grade}   Result: {'PASS' if report.passed else 'FAIL'}")
    lines.append("")

    for category in report.categories:
        lines.append(f"{category.name.upper()}  {category.score:5.1f}/100  (weight {category.weight:.0%})")
        for check in category.checks:
            if not verbose and check.status is Status.PASS:
                continue
            lines.append(f"  [{STATUS_MARK[check.status]}] {check.name}: {check.message}")
        if verbose:
            passed = sum(1 for check in category.checks if check.status is Status.PASS)
            lines.append(f"  {passed}/{len(category.checks)} checks passed")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"