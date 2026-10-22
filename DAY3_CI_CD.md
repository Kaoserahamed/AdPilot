# Day 3 CI/CD: Build / Test / Deploy Pipeline

## Repository
`AdPilot` — AI-assisted multi-platform advertising workspace

## Pipeline Overview
GitHub Actions CI/CD pipeline for the AdPilot monorepo (npm workspace + FastAPI backend).

### Trigger
- Push/Pull Request to `main`
- Manual workflow dispatch

### Stages

#### 1. Lint & Typecheck
- `npm run lint` (ESLint on `@adpilot/web`)
- `npm run typecheck` (TypeScript on `@adpilot/web`)
- `ruff format . && ruff check .` (Python backend)
- `mypy apps/api --strict --ignore-missing-imports` (Python typechecking)

#### 2. Test
- `npm run test --workspace @adpilot/web` (Vitest, 90% coverage floor)
- `python -m pytest apps/api/tests tools/tests` (pytest, 90% coverage floor)
- `python -m tools.repo_score --json --fail-under 80` (repository quality gate)

#### 3. Build
- `npm run build --workspace @adpilot/web` (Vite production build)
- Docker multi-stage build: `apps/api/Dockerfile` and root `Dockerfile`
- Tag images with commit SHA and `latest`

#### 4. Security Scan
- Secret detection (no `.env` committed, no API keys in code)
- Dependency audit (`npm audit`, `pip audit`)

#### 5. Deploy (on merge to `main`)
- Build and push Docker images to container registry
- Smoke test `/api/health` and `/api/ready` against running container
- Deploy via `docker compose up --build`

### Quality Gates
- 90% test coverage enforced (API + web)
- Repo quality score `--fail-under 80`
- No secrets in committed files
- E2E journey test (`test_e2e_journey.py`) must pass

### Artifacts
- Test coverage reports
- Docker images
- Repo quality score JSON report

## Day 3 Outcome
CI/CD pipeline documented. No code changes. 0 PRs. Ready for Day 4 (project restructuring).

---

# Day 3 Implementation: What Was Delivered

## Repository
`AdPilot` — AI-assisted multi-platform advertising workspace

The pipeline above was documented and largely built, but the implementation had drifted from it
in three places. This is what the implementation changed.

## Trigger: pull requests were not gated

The workflow triggered on `push` to `main` only. The `pull_request:` trigger had been removed, so
**no pull request ever ran CI** — which breaks the workflow the implementation plan mandates
("Open Pull Request → Code review → Merge") and left the repository's own CI check reporting
`ci_pull_request_trigger: CI does not run on pull_request events`.

The trigger is restored, and `workflow_dispatch` is added for a manual run. Publishing is still
gated on a push to `main`, so a pull request — including a fork's — can neither publish an image
nor read the registry token.

## Registry publishing

The pipeline built the images but never pushed one anywhere: the deploy stage stopped at a local
smoke test. A `publish` job now pushes the API and web images to the GitHub Container Registry on
a merge to `main`, tagged with the commit SHA and `latest`. It authenticates with the workflow
token, so no additional secret has to be configured, and it lowercases the repository name
because the registry requires it.

## The lint gate was red on `main`

`ruff check .` failed on a rule that newer ruff versions introduced after this repository was
written: `UP042` flags a class that inherits from both `str` and `Enum`. The status enum now uses
`StrEnum`, which is what the rule asks for and which renders correctly in a report. Nothing
depended on the old rendering, because every consumer looks the status up in a mapping or reads
`.value`.

The `UP038` entry was also removed from the ignore list, because that rule no longer exists and
ignoring it only produced a warning on every run.

## Type checking is deliberately not a gate

The pipeline above lists `mypy apps/api --strict` as a stage. It is not enforced, and adding it
would take the pipeline red rather than green: the strict run reports 67 findings across 14
existing modules, nearly all of them missing annotations on pre-existing handlers. Turning that
into a gate is its own piece of work, tracked against those modules, and it is not something to
smuggle into a pull request that is meant to land authentication. The gates that *are* enforced —
`ruff check`, `pytest` with a 90% coverage floor, and the repository quality score — are green.

## What the pipeline enforces

| Job | Gate |
|-----|------|
| `web` | ESLint, TypeScript typecheck, Vitest with coverage floors, production build, production dependency audit |
| `api` | `ruff check .`, `pip-audit --strict`, `pytest` with the 90% coverage floor |
| `quality` | `python -m tools.repo_score --fail-under 80` |
| `docker` | API image build and container smoke test |
| `publish` | API and web images pushed to GHCR (merge to `main` only) |
| `fresh_clone` | A fresh clone starts with no credentials |
| `stack` | `docker compose up` brings the whole stack up |

The repository quality score's CI category now passes every check, including the pull-request
trigger that was previously a warning.
<!-- Feature branch commit for PR -->
