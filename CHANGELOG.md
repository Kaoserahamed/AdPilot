# Changelog

All notable changes to AdPilot are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [0.1.0] - 2026-10-04

First tagged release, covering the MVP end to end.

### Added

- AI campaign studio: generate, regenerate, and refine platform-specific Meta
  and Google/YouTube copy, with every change reviewed before it is saved.
- Unified analytics across Meta, Google, and YouTube, keeping platform-reported
  values separate from values AdPilot derives (`ctr`, `cpc`, `cpa`, `roas`).
- Analytics assistant that answers questions grounded only in stored metrics and
  discloses which metrics were not reported by any platform.
- Asynchronous publishing workflow with a queued job record per submission, a
  three-attempt retry ceiling, and replaceable queue backends.
- Campaign validation and a human review gate. Confirmation marks a campaign
  `READY` and never publishes or spends money on its own.
- Sandbox-first advertising adapters for Meta, Google Ads, and YouTube, with
  connected account tokens encrypted at rest.
- Creative library with upload, validation of MIME type, size, and dimensions,
  search, filtering, and attaching assets to campaigns.
- Authentication with cookie sessions, campaign ownership enforcement, and an
  activity log for create, update, and delete actions.
- Monitoring endpoints: `/api/health`, `/api/ready`, and an operational
  `/api/v1/monitoring/snapshot`.
- Structured JSON logging correlated by `X-Request-ID`.
- One-command startup with `docker compose up --build`.
- Dependency auditing in CI (`npm audit`, `pip-audit`) and Dependabot for npm,
  pip, and GitHub Actions.

### Security

- Request id propagation, security response headers, and an in-process
  fixed-window rate limit that treats auth routes as the stricter case.
- Session cookies are `HttpOnly` and `SameSite=Lax`; passwords are hashed with
  a per-user salt and compared in constant time.

### Fixed

- Publishing jobs are committed before the queue is touched, so a queue failure
  cannot lose work.
- Worker exceptions are recorded on the job and reflected in campaign status
  instead of leaking internal detail to the caller.
- `AI_PROVIDER=sandbox` returned 503 whenever an API key was present, because
  only the exact value `mock` was accepted.
- The compose file, the configuration default, and the documentation disagreed
  about that setting's default.
