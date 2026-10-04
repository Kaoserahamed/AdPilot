"""CI/CD category: pipeline presence, required stages, and containerization."""

from __future__ import annotations

from ..models import CheckResult, Status
from ..repo import RepoContext

REQUIRED_STAGES = ("lint", "typecheck", "test", "build")


def _workflows(context: RepoContext) -> dict[str, str]:
    if not context.exists(".github/workflows"):
        return {}
    workflows = {}
    for _, relative in context.iter_paths({".yml", ".yaml"}):
        if relative.startswith(".github/workflows/"):
            workflows[relative] = context.read(relative)
    return workflows


def run(context: RepoContext) -> list[CheckResult]:
    results: list[CheckResult] = []
    workflows = _workflows(context)

    if not workflows:
        results.append(CheckResult(name="ci_configured", status=Status.FAIL, message="No GitHub Actions workflows found", weight=3.0))
        return results

    results.append(
        CheckResult(
            name="ci_configured",
            status=Status.PASS,
            message=f"{len(workflows)} workflow file(s): {', '.join(sorted(workflows))}",
            weight=2.0,
        )
    )

    combined = "\n".join(workflows.values()).lower()
    missing = [stage for stage in REQUIRED_STAGES if "run:" in combined and stage not in combined]
    if missing:
        results.append(
            CheckResult(
                name="ci_stages",
                status=Status.WARN,
                message=f"CI pipeline does not reference: {', '.join(missing)}",
                weight=2.0,
            )
        )
    else:
        results.append(
            CheckResult(
                name="ci_stages",
                status=Status.PASS,
                message=f"CI pipeline covers {', '.join(REQUIRED_STAGES)}",
                weight=2.0,
            )
        )

    triggers = "pull_request" in combined
    results.append(
        CheckResult(
            name="ci_pull_request_trigger",
            status=Status.PASS if triggers else Status.WARN,
            message="CI runs on pull requests" if triggers else "CI does not run on pull_request events",
            weight=1.0,
        )
    )

    containerised = any(context.exists(name) for name in ("Dockerfile", "docker-compose.yml", "compose.yaml"))
    results.append(
        CheckResult(
            name="containerization",
            status=Status.PASS if containerised else Status.WARN,
            message="Container definition present" if containerised else "No Dockerfile or compose file found",
            weight=1.0,
        )
    )

    return results
