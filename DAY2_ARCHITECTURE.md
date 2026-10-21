# Day 2 Architecture: Service Boundaries, Database Schema, API Contracts

## Repository
`AdPilot` — AI-assisted multi-platform advertising workspace

## Proposed Concept
Enterprise link management SaaS platform (LinkHub-style) with custom branded domains, QR codes, advanced analytics, team workspaces, API rate tiers, and webhook subscriptions.

## Service Boundaries
| Service | Responsibility | Technology |
|---------|---------------|------------|
| API Gateway | Request routing, auth termination, rate limiting, CORS | Nginx + FastAPI middleware |
| Auth Service | User registration, login, JWT session, password hashing (scrypt) | FastAPI, SQLite/PostgreSQL |
| Campaign Service | Campaign CRUD, brief validation, review workflow, ownership | FastAPI, SQLAlchemy |
| Creative Service | Creative upload, MIME validation, storage, attachment/detachment | FastAPI, local/S3 storage |
| AI Service | Campaign copy generation, regeneration, editing, analysis | FastAPI, mock/sandbox/provider adapters |
| Publishing Service | Async job queue, platform adapter execution, status tracking | FastAPI, JobQueue protocol, Celery+Redis (optional) |
| Analytics Service | Click metrics, CTR/CPC/CPA/ROAS, provenance tracking, dashboards | FastAPI, PostgreSQL |
| Web Frontend | React/Vite SPA, dashboard, campaign manager, creative studio | React 18, TypeScript, Vite, Tailwind |

## Database Schema (PostgreSQL)
- `users` — id, email, password_hash (scrypt), session_token_hash, created_at
- `campaigns` — id, user_id, product, description, objective, location, audience, budget, duration, landing_page, tone, offer, platforms, status (DRAFT/READY/PUBLISHING/PENDING_REVIEW/ACTIVE/PAUSED/REJECTED/FAILED), created_at, updated_at
- `creatives` — id, user_id, filename, mime_type, size, dimensions, campaign_id, created_at
- `publishing_jobs` — id, campaign_id, status (queued/running/succeeded/failed), platform, attempt_count, error_message, created_at, updated_at
- `platform_accounts` — id, user_id, platform, encrypted_token, connected_at
- `analytics_metrics` — id, campaign_id, platform, metric, value, currency, reporting_period, source (reported/calculated), created_at
- `activity_log` — id, user_id, action, entity_type, entity_id, metadata, created_at

## API Contracts (OpenAPI-style)
### Auth
- `POST /api/v1/auth/register` — {email, password} → {user}
- `POST /api/v1/auth/login` — {email, password} → session cookie (HTTP-only)
- `POST /api/v1/auth/logout` → 204
- `GET /api/v1/auth/me` → {user}

### Campaigns
- `GET /api/v1/campaigns` — list (filtered by owner)
- `POST /api/v1/campaigns` — {brief fields} → {campaign}
- `GET /api/v1/campaigns/{id}` → {campaign}
- `PUT /api/v1/campaigns/{id}` → {campaign}
- `DELETE /api/v1/campaigns/{id}` → 204
- `POST /api/v1/campaigns/{id}/validate` → {errors, warnings}
- `POST /api/v1/campaigns/{id}/review/confirm` → status READY

### Creatives
- `GET /api/v1/creatives` → list
- `POST /api/v1/creatives` — {file} → {creative}
- `GET /api/v1/creatives/{id}/file` → file download
- `POST /api/v1/creatives/{id}/attach` — {campaign_id} → 204
- `DELETE /api/v1/creatives/{id}/campaigns/{campaign_id}` → 204
- `DELETE /api/v1/creatives/{id}` → 204

### AI
- `GET /api/v1/ai/campaigns/{campaign_id}/generation` → {generation}
- `POST /api/v1/ai/generate-campaign` → {generation}
- `POST /api/v1/ai/regenerate` → {generation}
- `POST /api/v1/ai/edit` → {generation}
- `PUT /api/v1/ai/generations/{id}` → {generation}
- `POST /api/v1/ai/analyze` — {campaign_id, question} → {summary, highlights, metric_lines}

### Publishing
- `POST /api/v1/campaigns/{id}/publish` → {job_id} (202)
- `GET /api/v1/campaigns/{id}/status` → {status}
- `POST /api/v1/campaigns/{id}/pause` → 204
- `GET /api/v1/publishing/jobs` → list
- `POST /api/v1/publishing/jobs/{job_id}/retry` → {job}

### Platforms
- `GET /api/v1/platforms` → list
- `GET /api/v1/platforms/accounts` → list
- `POST /api/v1/platforms/accounts/connect` → {account}
- `DELETE /api/v1/platforms/accounts/{account_id}` → 204

### Analytics
- `GET /api/v1/analytics/overview` → {summary}
- `GET /api/v1/analytics/platforms` → list
- `GET /api/v1/analytics/campaigns/{id}` → {metrics}
- `GET /api/v1/analytics/campaigns/{id}/metrics` → list
- `POST /api/v1/analytics/campaigns/{id}/sync` → 202

### Monitoring
- `GET /api/health`, `GET /api/ready` — public liveness/readiness
- `GET /api/v1/monitoring/snapshot` — queue depth, job outcomes, campaign statuses
- `GET /api/v1/monitoring/health-metrics` — queue backlog, failure count

## Technical Notes
- Rate limiter is in-process (not cluster-safe) — flagged for shared storage before scaling out
- JobQueue protocol is replaceable (ThreadQueue/InlineQueue/RecordingQueue/Celery)
- Live Meta/Google adapters opt-in via `LIVE_EXTERNAL_APIS=true`; sandbox by default
- Secrets not baked into image; supplied via host environment or secret store
- 90% test coverage enforced (pytest.ini + vite.config.ts)

## Day 2 Outcome
Architecture design documented. No code changes. 0 PRs. Ready for Day 3 (CI/CD pipeline).