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
.github        CI workflows
storage        local development uploads (ignored)
```

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
POST   /api/v1/platforms/accounts/connect
DELETE /api/v1/platforms/accounts/{account_id}
```

Live OAuth clients can be added behind the adapter contract when approved Meta and Google developer credentials are configured.




The local default is sandbox-first. Add approved OAuth credentials and set `LIVE_EXTERNAL_APIS=true` only when Meta and Google developer apps and advertising accounts are available. AdPilot never sends credentials to the browser.
