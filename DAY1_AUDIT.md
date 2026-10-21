# Day 1 Audit: Repository Baseline

## Repository
`AdPilot` — AI-assisted multi-platform advertising workspace

## Day 1 Task
Repository audit - document existing code, identify technical debt | 0 PRs

## Current State Summary

### Tech Stack
- **Web**: React 18, Vite, TypeScript (npm workspace `@adpilot/web`)
- **API**: FastAPI, Pydantic settings, Python 3.11+
- **Data**: PostgreSQL/SQLAlchemy (database service introduced with backend data feature)
- **Jobs**: Redis + Celery architecture (worker service introduced with publishing)
- **Integrations**: Sandbox-first adapters; live Meta and Google clients opt-in via env vars
- **Container**: Docker, Docker Compose, multi-stage Dockerfiles

### Directory Structure (top level)
```
.github/          CI workflows
apps/
  api/            FastAPI backend
  web/            React/Vite frontend
deploy/           nginx config
scripts/          fresh_clone_check.sh, repo_score tool
tools/repo_score  repository quality scorer
compose.yaml      brings the whole stack up with one command
Dockerfile        web image (Vite build + nginx)
apps/api/Dockerfile API container image
```

### Key Files
- `README.md` — comprehensive docs: PRD-driven feature sequence, publishing workflow, unified analytics, AI analytics assistant, activity log, security hardening, monitoring, E2E validation, repo quality scoring
- `PRD.md` — product requirements document driving implementation sequence
- `package.json` — npm workspace, scripts for dev/build/lint/typecheck/test/score
- `apps/api/requirements.txt` + `requirements.lock.txt` — pinned Python deps
- `pytest.ini` — 90% coverage enforcement for API
- `apps/api/tests/test_e2e_journey.py` — full PRD §21 release criteria E2E test
- `tools/repo_score/config.py` — weighted repository quality rubric (A-F grade)

### Technical Debt / Gaps
1. **Rate limiter is in-process only** — not cluster-safe; multiplying effective limit by process count behind a load balancer (documented scaling note in README §Security hardening)
2. **Live Meta/Google OAuth clients not yet configured** — sandbox adapters default; live integrations require approved developer credentials and `LIVE_EXTERNAL_APIS=true`
3. **Celery + Redis job queue backend not yet implemented** — `JobQueue` protocol defined with `ThreadQueue`/`InlineQueue`/`RecordingQueue`; Celery adapter is planned (`set_queue`)
4. **Database service not yet introduced** — README notes PostgreSQL/SQLAlchemy architecture is "introduced with the backend data feature" (future work)
5. **No Kubernetes/Helm manifests** — Docker Compose only; production deployment left to operator
6. **Repo quality scorer gate is `--fail-under 60` in CI** but `score:ci` uses `--fail-under 80` — inconsistency between CI gate and local script

### What's Needed for Proposed Concept (Enterprise Ad Platform)
The implementation plan expands AdPilot into LinkHub-style enterprise link management with custom branded domains, QR codes, advanced analytics, team workspaces, API rate tiers, and webhook subscriptions. Day 1 establishes the audit baseline; Day 2 begins architecture design for client-server boundaries and API contracts.

### Day 1 Outcome
Audit complete. No code changes. 0 PRs. Ready for Day 2 (architecture design).