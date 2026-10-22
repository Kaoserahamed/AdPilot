# Day 4 Project Restructuring: Separate Service Modules

## Repository
`AdPilot` — AI-assisted multi-platform advertising workspace

## What changed

The API was a single flat package: seventeen top-level modules in
`apps/api/app/`, each one a service boundary the architecture document
described, but with nothing marking where one ended and the next began. The
service list in `DAY2_ARCHITECTURE.md` was implemented, but only as a naming
convention in the imports.

The modules are now packages, one per service, with the shared infrastructure
in a package of its own:

| Package | Owns |
|---------|------|
| `app/core` | Settings, the database handle, the job queue, structured logging, the HTTP middleware |
| `app/auth` | Accounts, sessions, API keys, access tokens, OAuth2 |
| `app/campaigns` | Campaign records and brief validation |
| `app/creatives` | Uploaded creatives and their campaign attachments |
| `app/ai` | Copy generation and the analytics assistant |
| `app/publishing` | Platform adapters, campaign publishing, publishing jobs, the activity log |
| `app/analytics` | Campaign metrics, derived KPIs, the monitoring snapshot |
| `app/main.py` | The application itself: router registration and the lifecycle |

The dependency direction is one-way. `core` depends on nothing inside the
application; every service depends on `core`; and the services depend on each
other only where the architecture says they do — publishing and analytics
share platform adapters, the AI assistant reads analytics, campaign validation
reads generated copy. There are no import cycles.

## The rules that made it work

**The package `__init__` is the public API.** A service module writes
`from app.core import settings`, not `from app.core.config import settings`, so
a caller is not coupled to the file a name happens to live in. The `__init__`
re-exports the names, and lists them in `__all__` so a linter treats them as
intentional re-exports rather than unused imports.

**Cross-package imports are absolute, intra-package imports are relative.**
`from app.auth import authenticated_user` says "another service"; `from
.config import settings` says "a sibling module in this package". The
distinction is what makes the boundary readable.

**The split was driven by size as well as by ownership.** The repository's own
quality scorer flags a module over 400 lines, and the authentication module had
grown to 474. Splitting it by concern — `models`, `passwords`, `tokens`,
`schema`, `sessions`, `routes` — brought every module under the threshold
without changing a single behaviour.

## What the placeholder directories became

The earlier marker commit had added empty `apps/ad-server`, `apps/bidder`,
`apps/creative` and `apps/analytics` directories, and a `shared/` directory,
as a sketch of a different service layout. The real implementation puts the
services inside the API, where the architecture document and the running
system already put them, so the empty directories were removed rather than
left to rot beside the code they were meant to describe.

The authentication marker stub at `apps/ad-server/auth/README.md` described a
separate PostgreSQL-backed service using PyJWT and `python-oauth2`. The
implementation that exists uses SQLite, a hand-rolled HS256 token and the
standard library, and lives at `app/auth`. The stub was replaced by
`DAY5_AUTHENTICATION.md`, which describes what was actually built.

## Verification

| Gate | Before | After |
|------|--------|-------|
| `pytest` | 209 passed | **314 passed** |
| Coverage | 92.98% | **93.92%** |
| `ruff check .` | **1 error** | **clean** |
| Top-level API modules | 17 | **1** (`main`) |
| Largest module | 474 lines | **398 lines** |
| Architecture score | 73.3/100 | **89.3/100** |
| Overall quality score | 87.2/100 | **89.9/100** |

Every module the restructure produced has a matching test module, and the
authentication service gained ten: the credential primitives, the token
implementation, the request contracts, the request-scoped identity, the job
queue, the configuration, the logging helpers, the middleware, the activity log
and the application wiring.

## Day 4 Outcome
Seventeen flat modules replaced by seven service packages plus the application
entry point. Every service boundary in `DAY2_ARCHITECTURE.md` is now a package
rather than a convention. 1 PR created targeting `development`.
