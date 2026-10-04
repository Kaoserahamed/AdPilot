# AdPilot

AdPilot is an AI-assisted multi-platform advertising workspace. Give the product one campaign brief, review platform-specific creative, and keep publishing decisions under your control.

## Stack

- Web: React, Vite, TypeScript
- API: FastAPI, Pydantic settings
- Data: PostgreSQL/SQLAlchemy architecture (database service is introduced with the backend data feature)
- Jobs: Redis + Celery architecture (worker service is introduced with publishing)
- Integrations: sandbox-first adapters; live Meta and Google clients are opt-in through environment variables

## Development

Requirements: Node.js 20+, Python 3.11+.

```bash
npm install
npm run dev
```

The web app runs at `http://localhost:5173`. The API foundation is available with:

```bash
python -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r apps/api/requirements.txt
uvicorn app.main:app --app-dir apps/api --reload --port 8000
```

Copy `.env.example` to `.env` before starting services. No secrets are required for the deterministic local experience.

## Repository layout

```text
apps/web       React/Vite frontend
apps/api       FastAPI backend
tools/repo_score  repository quality scorer
.github        CI workflows
storage        local development uploads (ignored)
```

## Publishing workflow

Publishing is asynchronous (PRD §8.16). `POST /api/v1/campaigns/{id}/publish` re-validates ownership and review state, persists a publishing job, then hands it to a queue. The request returns `202` immediately; the worker performs the platform calls and updates status.

```text
POST /api/v1/campaigns/{id}/publish
GET  /api/v1/campaigns/{id}/status
POST /api/v1/campaigns/{id}/pause
GET  /api/v1/publishing/jobs
POST /api/v1/publishing/jobs/{job_id}/retry
```

Campaigns move through `DRAFT → READY → PUBLISHING → PENDING_REVIEW → ACTIVE | PAUSED | REJECTED | FAILED`. Publishing requires a prior review confirmation and at least one connected account per selected platform. A duplicate publish while a job is queued or running returns `409`, and retries stop at three attempts.

Job rows are committed before the queue is touched, so a queue failure cannot lose work. Worker exceptions are recorded on the job and reflected in campaign status instead of leaking internal detail.

### Queue backend

`app/jobs.py` defines a `JobQueue` protocol so the backend is replaceable (PRD §8.17) without touching callers:

- `ThreadQueue` (default) runs jobs on a background thread pool.
- `InlineQueue` runs jobs synchronously; tests use it so assertions never race the worker.
- `RecordingQueue` captures submissions without executing them.

A Celery + Redis backend only needs to implement `JobQueue` and be installed with `set_queue`.

## Unified analytics

Metrics are collected from platform adapters through the same replaceable queue as publishing, and stored with full provenance: platform, campaign, metric, value, currency, reporting period, and source (PRD §8.18).

```text
GET  /api/v1/analytics/overview
GET  /api/v1/analytics/platforms
GET  /api/v1/analytics/campaigns/{id}
GET  /api/v1/analytics/campaigns/{id}/metrics
POST /api/v1/analytics/campaigns/{id}/sync
```

Platform-reported values (`spend`, `impressions`, `reach`, `clicks`, `conversions`, `revenue`) keep the source the adapter returned. AdPilot-derived values (`ctr`, `cpc`, `cpa`, `roas`) are stored separately and marked `calculated` with source `adpilot`, so the dashboard can always distinguish reported numbers from computed ones (PRD §8.19). A ratio without a denominator is reported as `null` rather than zero, which would imply a real measurement.

The reporting period is snapped to the UTC day, so repeated syncs upsert the same rows instead of appending duplicate snapshots.

## Activity log

Every important action is recorded (PRD §8.21).

```text
GET /api/v1/activity
GET /api/v1/activity?campaign_id={id}&limit={n}
GET /api/v1/activity/recent?limit={n}
```

## Repository quality scoring

`tools/repo_score` measures this repository across weighted categories and reports a composite grade. It is read-only: it inspects the checkout and never rewrites code.

```bash
python -m tools.repo_score              # human-readable report
python -m tools.repo_score --verbose    # include passing checks
python -m tools.repo_score --json       # machine-readable report
python -m tools.repo_score --strict     # exit 1 if any check fails
npm run score
```

| Category | Weight | Signals |
| --- | --- | --- |
| Testing | 25% | test presence, test-to-source ratio, runner config, case count, source coverage |
| Architecture | 20% | module size, function size, import cycles, top-level module count |
| Code cleanliness | 20% | line length, TODO/FIXME markers, stray debug output, whitespace |
| Documentation | 15% | README substance, `.env.example`, docstring ratio, Markdown count |
| CI/CD | 10% | workflow presence, lint/typecheck/test/build stages, PR trigger, containerization |
| Repository hygiene | 10% | ignore rules, `.editorconfig`, secret detection, commit convention, clean worktree |

Each check reports `PASS`, `WARN`, `FAIL`, or `SKIP`. Checks are weighted within a category and categories are weighted into the composite, which maps to a letter grade (`A` >= 90, `B` >= 80, `C` >= 70, `D` >= 60, else `F`).

Every weight and threshold lives in `tools/repo_score/config.py`; `validate_config()` enforces that category weights sum to `1.0`. Adjust the model there without touching check logic.

CI runs the scorer as a quality gate (`--fail-under 60`) and uploads the JSON report as an artifact.

### A note on the rubric

This rubric is an original construction from commonly used repository-health signals. It is not a reproduction of any third party's proprietary criteria. Company-internal curation rubrics used for AI training data are generally unpublished, so if you have a specific external rubric in mind, encode it in `config.py` and the scoring engine will use it unchanged.

## Product implementation sequence

The product follows `PRD.md`: foundation, authentication, campaigns, creatives, AI generation, platform adapters, Meta, Google Ads/YouTube, validation, publishing workers, analytics, AI analysis, hardening, and release validation.

## Authentication

Local authentication uses an HTTP-only session cookie. Passwords are stored as scrypt hashes, session tokens are stored only as SHA-256 hashes, and reset requests use a generic response to avoid account enumeration. The local SQLite database is configured through `AUTH_DB_PATH` and is ignored by Git.

Available endpoints:

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/logout
GET  /api/v1/auth/me
POST /api/v1/auth/password-reset/request
POST /api/v1/auth/password-reset/confirm
```


## Live integrations


## Campaign management

Campaign briefs are persisted per authenticated user with the required fields from the PRD: product, description, objective, location, audience, budget, duration, landing page, tone, offer, and selected platforms. Campaign ownership is enforced on list, detail, update, and delete operations, and create/update/delete actions are recorded in the activity log.

Available endpoints:

```text
GET    /api/v1/campaigns
POST   /api/v1/campaigns
GET    /api/v1/campaigns/{id}
PUT    /api/v1/campaigns/{id}
DELETE /api/v1/campaigns/{id}
```

## Creative library

Creatives are stored in per-user directories with generated filenames. The API validates MIME type, size, and image dimensions, and returns metadata for images, videos, and logos. Creatives can be searched, filtered, downloaded, attached to owned campaigns, detached, and deleted.

Available endpoints:

```text
GET    /api/v1/creatives
POST   /api/v1/creatives
GET    /api/v1/creatives/{id}/file
POST   /api/v1/creatives/{id}/attach
DELETE /api/v1/creatives/{id}/campaigns/{campaign_id}
DELETE /api/v1/creatives/{id}
```


## AI campaign studio

AI output is generated as structured data and validated before persistence. Meta copy and Google/YouTube copy use separate schemas. The review studio supports generation, regeneration, shortening, expansion, tone changes, CTA changes, direct copy editing, and reviewed-content saves. Generated content is never published automatically.

Available endpoints:

```text
GET  /api/v1/ai/campaigns/{campaign_id}/generation
POST /api/v1/ai/generate-campaign
POST /api/v1/ai/regenerate
POST /api/v1/ai/edit
PUT  /api/v1/ai/generations/{generation_id}
```

The default provider is `sandbox`. Set `AI_PROVIDER`, `AI_API_KEY`, and `AI_MODEL` to opt into a configured provider.

## Platform adapters

Advertising integrations implement a shared adapter contract for account discovery, campaign validation, creative upload, campaign/ad creation, publishing, pause, status, and metrics. Meta, Google Ads, and YouTube use deterministic sandbox adapters by default. Connected account tokens are encrypted at rest with Fernet-derived key material and are never returned by the API.

Available endpoints:

```text
GET    /api/v1/platforms
GET    /api/v1/platforms/accounts

## Validation and human review

Validation checks required campaign fields, budget, duration, landing page, targeting, attached creative presence, platform creative compatibility, and generated platform content. The review screen shows per-platform readiness and errors/warnings. Review confirmation only transitions a campaign to `READY`; it never publishes or spends money.

Available endpoints:

```text
POST /api/v1/campaigns/{id}/validate
POST /api/v1/campaigns/{id}/review/confirm
```

POST   /api/v1/platforms/accounts/connect
DELETE /api/v1/platforms/accounts/{account_id}
```

Live OAuth clients can be added behind the adapter contract when approved Meta and Google developer credentials are configured.




The local default is sandbox-first. Add approved OAuth credentials and set `LIVE_EXTERNAL_APIS=true` only when Meta and Google developer apps and advertising accounts are available. AdPilot never sends credentials to the browser.
