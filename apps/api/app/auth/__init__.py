"""Authentication service: accounts, sessions, API keys, tokens and OAuth2.

The service owns everything that answers *who is calling and what may they do*:

* **Accounts** — an advertiser, a publisher or an administrator, with a
  scrypt-hashed password.
* **Sessions** — a server-side session identified by a cookie, stored as a
  hash so a database dump does not hand out working sessions.
* **API keys** — a per-user credential, also stored only as a hash, usable
  through ``Authorization: Api-Key``, ``Authorization: Bearer`` or
  ``X-API-Key``.
* **Tokens** — a short-lived HS256 access token carrying the user id and role.
* **OAuth2** — an authorization-code flow for connecting a platform account.

The modules are split by concern so that each one stays small and can be read
on its own: ``models`` holds the request and response contracts, ``passwords``
the credential hashing, ``tokens`` the JWT and session-token helpers,
``schema`` the table definitions, ``sessions`` the request-scoped identity,
and ``routes`` the HTTP surface.
"""

from app.auth.models import (
    DEFAULT_ROLE,
    USER_ROLES,
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyResponse,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.auth.passwords import (
    hash_api_key,
    hash_password,
    verify_api_key,
    verify_password,
)
from app.auth.routes import router
from app.auth.schema import init_db
from app.auth.sessions import (
    authenticated_user,
    current_user,
    require_role,
)
from app.auth.tokens import create_access_token, decode_access_token
from app.core import settings

__all__ = [
    "DEFAULT_ROLE",
    "USER_ROLES",
    "ApiKeyCreate",
    "ApiKeyCreated",
    "ApiKeyResponse",
    "LoginRequest",
    "PasswordResetConfirm",
    "PasswordResetRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserResponse",
    "authenticated_user",
    "create_access_token",
    "current_user",
    "decode_access_token",
    "hash_api_key",
    "hash_password",
    "init_db",
    "require_role",
    "router",
    "settings",
    "verify_api_key",
    "verify_password",
]
