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