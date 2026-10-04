# AdPilot

AdPilot is an AI-assisted multi-platform advertising workspace. Give the product one campaign brief, review platform-specific creative, and keep publishing decisions under your control.

## Stack

- Web: React, Vite, TypeScript
- API: FastAPI, Pydantic settings
- Data: PostgreSQL/SQLAlchemy architecture (database service is introduced with the backend data feature)
- Jobs: Redis + Celery architecture (worker service is introduced with publishing)
- Integrations: sandbox-first adapters; live Meta and Google clients are opt-in through environment variables

## Run the whole app with one command

Docker Compose starts the API, the built web app, and the storage volume
together. No local Node or Python install is required.

```bash
docker compose up --build
```

The workspace is then at `http://localhost:5173`. Requests to `/api` are
reverse-proxied to the API service by nginx, so the browser talks to a single
origin and the session cookie needs no CORS handling. The API is also published
directly on `http://localhost:8000` for debugging.

`compose.yaml` waits for the API health check before starting the web container,
so a half-ready stack is not something you have to wait on manually. Data
persists in the `adpilot-data` volume; add `--volumes` to `docker compose down`
to discard it.

To run the services directly on your machine instead, use the steps below.

### Verifying a fresh clone

`scripts/fresh_clone_check.sh` clones the repository into a scratch directory,
builds both images, starts the stack, and asserts `/api/health`, `/api/ready`,
and the nginx-proxied health endpoint all respond. It fails if a `.env` file is
present, which keeps the "no credentials required" claim honest.

```bash
./scripts/fresh_clone_check.sh
```

It runs in CI on every pull request, so the one-command startup is verified
rather than merely documented. Pass a repository URL as the first argument to
check a specific remote.

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
pip install -r apps/api/requirements.lock.txt
uvicorn app.main:app --app-dir apps/api --reload --port 8000
```

`apps/api/requirements.txt` lists the direct dependencies; `requirements.lock.txt`
pins every transitive one and is what CI and the container image install.
Regenerate the lock after changing `requirements.txt`:

```bash
pip-compile --strip-extras --output-file=apps/api/requirements.lock.txt apps/api/requirements.txt
```

Copy `.env.example` to `.env` before starting services. No secrets are required for the deterministic local experience.



### Running the tests

Both suites are hermetic: they need no accounts, no API keys, and no network.

```bash
python -m pytest
npm run test
```

The API tests write only to a temporary directory, and the web tests mock
`fetch`. `apps/api/tests/test_isolation.py` enforces this rather than describing
it: it fails if any test module imports an HTTP client or a provider SDK, or if
`LIVE_EXTERNAL_APIS` is left enabled for a run. That flag is the difference
between the sandbox adapters and calls that could spend real money.

Coverage is enforced, not merely reported. `pytest.ini` requires 90% for the API;
`apps/web/vite.config.ts` requires 90% statements, 90% lines, 75% branches, and
65% functions for the web app. Either suite fails the build below its floor.

### Where dependencies are declared

This repository is an npm workspace, so the dependency manifests are:

| File | Contains |
| --- | --- |
| `apps/web/package.json` | the only npm manifest with dependencies: React and React DOM at runtime, the rest under `devDependencies` |
| root `package.json` | workspace scripts only; it declares no dependencies by design |

The Python side is the reverse. `apps/api/requirements.txt` lists the direct
dependencies and `requirements.lock.txt` pins every resolved package, which is
what CI and the API image install. To inspect the installed footprint:

```bash
npm ls --workspace @adpilot/web --depth=0
pip list
```

## Repository layout

```text
apps/web       React/Vite frontend
apps/api       FastAPI backend
tools/repo_score  repository quality scorer
.github        CI workflows
deploy         nginx config used by the web image
Dockerfile     web image (Vite build + nginx)
apps/api/Dockerfile  API container image
compose.yaml   brings the whole stack up with one command
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

## AI analytics assistant

`POST /api/v1/ai/analyze` answers questions about campaign performance using only retrieved campaign data (PRD §8.20).

```text
POST /api/v1/ai/analyze   { "campaign_id": 1, "question": "What happened last week?" }
```

The response returns the reporting period, a summary, highlights, and the metric lines each statement is based on.

The "must not invent missing metrics" rule is **enforced in code, not just requested in a prompt**:

- the assistant reads only stored metric rows and their provenance;
- every numeric figure in the response is extracted and checked against those stored values;
- a figure that cannot be traced back to a stored metric is rejected with `502` before it reaches the user;
- metrics no platform reported are listed under `unavailable` and set `data_complete` to `false` rather than being estimated.

Dates are stripped before comparison, and non-metric identifiers (campaign id, budget) are allowlisted, so the guard targets figures rather than incidental numbers.

## Activity log

Every important action is recorded (PRD §8.21).

```text
GET /api/v1/activity
GET /api/v1/activity?campaign_id={id}&limit={n}
GET /api/v1/activity/recent?limit={n}
```

## Security hardening

Cross-cutting request handling lives in `app/middleware.py` (PRD §11.1, §14):

- **Request ids** — every request gets an `X-Request-ID` (an inbound one is echoed, otherwise one is generated) and every log line carries it.
- **Security headers** — `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Cross-Origin-Opener-Policy`, and `Permissions-Policy` are set on success and error responses.
- **Structured errors** — rate-limit and unhandled-error responses return `{ "error": { "code", "message", "request_id", "timestamp" } }`. Internal detail is never exposed.
- **Rate limiting** — a fixed-window counter, 120 requests/minute per client per route, tightened to 20/minute on `/api/v1/auth` where credential stuffing concentrates. Exceeding it returns `429` with `Retry-After`.
- **CORS** — restricted to the configured `WEB_ORIGIN`.

`/api/health` and `/api/ready` are exempt from rate limiting. Load balancers poll them frequently, and limiting them would report a false outage during a traffic spike.

> **Scaling note:** the limiter is in-process state. It is correct for a single API process and needs no Redis, but it is **not** cluster-safe — running several API processes behind a load balancer multiplies the effective limit by the process count. Move the counter to shared storage before scaling out. This is the same replaceable-backend pattern used for the job queue.

## Monitoring

Operational visibility without new infrastructure (PRD §20, §22):

```text
GET /api/v1/monitoring/snapshot        # queue depth, job outcomes, campaign statuses, connected accounts
GET /api/v1/monitoring/health-metrics  # unauthenticated liveness detail for a load balancer
```

`/snapshot` reports queued/running/succeeded/failed publishing jobs, campaigns grouped by status, connected account count, and recent activity volume. `/health-metrics` exposes only queue backlog and failure count, so it is safe for a load balancer to poll without credentials.

`GET /api/health` and `GET /api/ready` remain the primary liveness and readiness probes.

## Running with Docker

```bash
docker build -t adpilot-api .
docker run -p 8000:8000 -v adpilot-data:/data adpilot-api
```

Or with compose:

```bash
docker compose up --build
```

The image is multi-stage: dependencies are built into a virtualenv in the builder stage and copied into a slim runtime. It runs as a non-root user, declares a `HEALTHCHECK`, and keeps uploads and the local database on a `/data` volume so they survive redeploys.

Secrets are **not** baked into the image or `compose.yaml`. Supply them through the host environment or a managed secret store (`JWT_SECRET`, `AI_API_KEY`, `META_CLIENT_*`, `GOOGLE_CLIENT_*`).

CI builds the image and smoke tests `/api/health` and `/api/ready` against a running container, so a broken image fails the pipeline before release.

## End-to-end validation

`apps/api/tests/test_e2e_journey.py` walks the full PRD §21 release criteria through public HTTP endpoints only:

```text
Register → Login → Create campaign → Upload creative → Generate AI content
→ Edit content → Validate → Review → Connect account → Publish
→ Retrieve metrics → View dashboard → Ask AI to summarise → Audit trail
```

A second test asserts that every release-criteria endpoint exists and rejects anonymous access with `401`, while `/api/health`, `/api/ready`, and `/api/v1/monitoring/health-metrics` stay public for load balancers.

Run it alone with:

```bash
python -m pytest apps/api/tests/test_e2e_journey.py
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

The default provider is `mock`, which runs a deterministic local generator and needs no API key. `sandbox` is accepted as an alias. To opt into a configured provider, set `AI_PROVIDER` to `openai` or `gemini` together with `AI_API_KEY` and `AI_MODEL`; an unrecognised provider name is rejected with a `503` once a key is present.

Set `LOG_LEVEL` to `DEBUG`, `INFO`, `WARNING`, or `ERROR` to control log verbosity. An unrecognised value falls back to `INFO` rather than preventing startup.

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
