"""Request and response contracts for the authentication service.

The models are deliberately narrow. A registration request carries only what
an account needs to exist, and every response carries the role, because the
role is what a client needs in order to decide what it may offer the user.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, field_validator

#: The roles an account may hold.
#:
#: ``advertiser`` buys inventory, ``publisher`` owns the inventory, and
#: ``admin`` administers the platform. A new account is an advertiser.
USER_ROLES: tuple[str, ...] = ("advertiser", "publisher", "admin")

#: The role a newly registered account receives.
DEFAULT_ROLE: str = "advertiser"


class RegisterRequest(BaseModel):
    """Body of a registration request.

    The role is optional and defaults to ``advertiser``. A caller may ask for
    a different role, but the role is validated against the known set so an
    unknown role is refused at the edge rather than stored.
    """

    name: Annotated[str, Field(min_length=2, max_length=80)]
    email: Annotated[str, Field(min_length=3, max_length=254)]
    password: Annotated[str, Field(min_length=8, max_length=128)]
    role: str = DEFAULT_ROLE

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Normalise the address and refuse one that cannot be delivered to."""
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Enter a valid email address")
        return normalized

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        """Refuse a role outside the known set."""
        role = value.strip().lower()
        if role not in USER_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(USER_ROLES)}")
        return role


class LoginRequest(BaseModel):
    """Body of a login request."""

    email: Annotated[str, Field(min_length=3, max_length=254)]
    password: Annotated[str, Field(min_length=1, max_length=128)]


class PasswordResetRequest(BaseModel):
    """Body of a password reset request.

    The response is the same whether or not the address exists, so the
    endpoint cannot be used to find out which addresses have accounts.
    """

    email: Annotated[str, Field(min_length=3, max_length=254)]


class PasswordResetConfirm(BaseModel):
    """Body of a password reset confirmation."""

    token: Annotated[str, Field(min_length=20, max_length=200)]
    password: Annotated[str, Field(min_length=8, max_length=128)]


class UserResponse(BaseModel):
    """An account as the API returns it.

    The password hash is never part of this model, so it cannot leak through a
    response by accident.
    """

    id: int
    name: str
    email: str
    role: str


class ApiKeyCreate(BaseModel):
    """Body of an API key creation request."""

    name: Annotated[str, Field(min_length=1, max_length=120)]


class ApiKeyResponse(BaseModel):
    """An API key as the API returns it.

    Only the prefix is present, which is enough to recognise a key in a list
    without being enough to use it.
    """

    id: int
    name: str
    prefix: str
    created_at: str
    expires_at: str | None = None
    revoked_at: str | None = None
    last_used_at: str | None = None


class ApiKeyCreated(ApiKeyResponse):
    """A newly issued API key, including its plaintext.

    The plaintext appears in exactly one response, at creation. It is not
    recoverable afterwards, because only its hash is stored.
    """

    key: str


class TokenResponse(BaseModel):
    """A freshly issued access token."""

    access_token: str
    token_type: str = "bearer"
