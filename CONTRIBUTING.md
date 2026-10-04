# Contributing

AdPilot is a full-stack application: a React/Vite frontend in `apps/web` and a
FastAPI backend in `apps/api`.

## Getting set up

The fastest way to run everything is Docker, which needs no local Node or
Python install:

```bash
docker compose up --build
```

For day-to-day development against a local toolchain, use Node.js 20+ and
Python 3.11+:

```bash
npm install
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r apps/api/requirements.txt
cp .env.example .env
```

Then run the web app and the API in separate terminals:

```bash
npm run dev                                  # http://localhost:5173
npm run api:dev                              # http://localhost:8000
```

## Tests

Run both suites before opening a pull request:

```bash
npm run test        # frontend: vitest + testing-library
npm run api:test    # backend: pytest
```

`npm run test:coverage` writes a frontend coverage report to
`apps/web/coverage`. A new feature or fix is expected to arrive with the tests
that pin its behaviour; a change that alters observable behaviour without a
failing-then-passing test will not be merged.

To run a single suite while iterating:

```bash
npm run test --workspace @adpilot/web -- src/Publishing.test.tsx
python -m pytest apps/api/tests/test_monitoring.py -q
```

## Checks that CI runs

| Command | What it covers |
| --- | --- |
| `npm run lint` / `npm run typecheck` | TypeScript, no emit |
| `npm run test` | Frontend suites |
| `npm run build` | Production bundle |
| `npm audit --omit=dev --audit-level=high` | Vulnerabilities in shipped dependencies |
| `python -m pytest` | Backend suites |
| `pip-audit --requirement apps/api/requirements.txt --strict` | Vulnerabilities in Python dependencies |
| `python -m tools.repo_score --fail-under 60` | Repository quality gate |

## Repository quality score

The repository scores itself. Run it before pushing:

```bash
npm run score          # human-readable report
npm run score:ci       # JSON, fails under the CI threshold
```

The score is a weighted rubric covering testing, architecture, cleanliness,
documentation, CI, and hygiene. `--fail-under` in `package.json` and the
`quality` CI job must both stay satisfied; if you lower the threshold to make a
failure pass, that will be noticed in review.

## Branch and commit workflow

- Branch from `main` using a short descriptive name: `fix/publish-retry-ceiling`.
- Open a pull request; CI runs on every pull request.
- Keep commits focused. One logical change per commit, with its tests in the
  same commit, so the history stays readable.
- Use [Conventional Commits](https://www.conventionalcommits.org/) for subjects:
  `feat(api):`, `fix(web):`, `test(web):`, `docs:`, `chore:`, `refactor:`,
  `build:`, `ci:`, `security:`.
- Update `CHANGELOG.md` under `Unreleased` for user-visible changes.

## Reporting a security issue

Please do not open a public issue for a vulnerability. Report it privately to
the maintainers so a fix can be prepared before disclosure.