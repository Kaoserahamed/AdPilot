# Day 5 Authentication: Accounts, API Keys, OAuth2 and Role-Based Access

## Repository
`AdPilot` — AI-assisted multi-platform advertising workspace

## What was built

The authentication service lives in `app/auth`, split by concern so that each
piece is small enough to read on its own:

| Module | Owns |
|--------|------|
| `app/auth/models.py` | The request and response contracts, and the role vocabulary |
| `app/auth/passwords.py` | scrypt password hashing and API key hashing |
| `app/auth/tokens.py` | The access token (HS256) and the session token digest |
| `app/auth/schema.py` | The `users`, `sessions`, `password_resets` and `api_keys` tables |
| `app/auth/sessions.py` | The request-scoped identity and the role check |
| `app/auth/routes.py` | The HTTP surface |

## Credentials

Three credentials are accepted, in this order:

1. **A session cookie** — high-entropy random material issued at login and
   stored server-side as a SHA-256 digest, so a database dump does not yield a
   usable session. The cookie is HTTP-only, `SameSite=Lax`, and `Secure`
   outside development.
2. **An API key** — presented in `Authorization: Api-Key`, in
   `Authorization: Bearer` or in `X-API-Key`. Only its hash is stored, and the
   plaintext appears in exactly one response, at creation.
3. **An access token** — a short-lived HS256 token carrying the user id and
   the role, issued by `POST /api/v1/auth/token` and verified by signature and
   expiry.

A password is hashed with scrypt (n=2^14, r=8, p=1) and a per-password salt.
The stored hash records the parameters it was created with, so the work factor
can be raised later without invalidating existing credentials. A user-chosen
password is a low-entropy secret, which is why it gets a deliberately slow
hash; an API key is 256 bits of randomness, which is why it does not.

Every comparison is constant time, and every stored credential is a hash.

## Roles

An account holds one of three roles: `advertiser`, `publisher` or `admin`. A
registration may ask for a role, and an unknown role is refused at the edge
rather than stored.

`require_role(*roles)` is a dependency that admits only the listed roles. It
is applied to the campaign mutations, so a role outside the permitted set
cannot create, update or delete a campaign. The check reads the role of the
*account*, so it is the same answer whether the caller authenticated with a
session, an API key or an access token.

## What was wrong before this was finished

Two things were incomplete in the earlier implementation, and both are fixed
here.

**An access token could not be used.** The token was issued and could be
decoded, but the request-scoped identity only ever looked at a session cookie
or an API key. A script that obtained a token had nothing to do with it. The
identity now verifies a bearer token as well, and reads the account back from
the database, so a token for a deleted account stops working.

**An API key only worked on the authentication routes.** The service
endpoints each had their own session-only dependency, so an API key could
mint a token but could not call the campaigns API with it — which is the
opposite of what a key is for. Every service endpoint now goes through the
same identity dependency, and an API key works everywhere a session does.

## OAuth2

An authorization-code flow is implemented for connecting a platform account:
`GET /api/v1/auth/oauth2/authorize` issues a code bound to the redirect URI it
was requested with, and `POST /api/v1/auth/oauth2/callback` exchanges it for
an access token. The code is single use and short lived, and it is removed
whether the exchange succeeds or fails, so a captured code cannot be replayed.

The outstanding codes are held in memory. A code is short lived and single
use, and an in-memory store keeps a failed exchange from leaving a trace on
disk.

## Password reset

`POST /api/v1/auth/password-reset/request` returns the same response whether
or not the address has an account, so the endpoint cannot be used to find out
which addresses exist. A token is created only when the account does.
Confirming a reset ends every session of that account, because a reset is the
usual response to a suspected compromise and the old sessions may be the
attacker's.

## Tests

The authentication service gained five test modules, and the shared
infrastructure three more:

| Test module | Covers |
|-------------|--------|
| `test_auth_passwords.py` | Hashing never stores the secret; a wrong secret never verifies; a corrupted hash is a failed verification, not a crash |
| `test_auth_tokens.py` | The token carries the user and role; a tampered, expired or malformed token is refused |
| `test_auth_models.py` | The role vocabulary is closed; an unknown role and an unusable address are refused |
| `test_auth_sessions.py` | A session, an API key and an access token all identify the account; a revoked key stops working; the role check admits and refuses correctly |
| `test_auth.py` | The end-to-end flows: register, log in, log out, key issue and revoke, the OAuth2 exchange |
| `test_core_jobs.py` | A replaceable queue; a failing job is contained |
| `test_core_logging.py` | Every record carries its request id and stays one JSON object |
| `test_core_config.py` | The defaults a deployment inherits |
| `test_core_middleware.py` | Request ids, security headers, and the rate limit |
| `test_activity.py` | The activity log is scoped to the caller |
| `test_main.py` | Every service router is mounted and the schema builds |
| `test_schema.py` | The schema is safe to run twice, and migrates a database that predates the role column |

The suite went from 209 tests to 314, with coverage at 93.92% against the 90%
floor.

## Day 5 Outcome
Authentication service implemented: accounts with roles, sessions, API keys,
access tokens, OAuth2 and role-based access control, with the credential
primitives separated from the request handling. 1 PR created targeting
`development`.
