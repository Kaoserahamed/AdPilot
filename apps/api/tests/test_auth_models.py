"""Tests for the request contracts of the authentication service.

The validators are the first line of defence, so an invalid role or an
unusable address is refused at the edge rather than stored.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.auth.models import (
    DEFAULT_ROLE,
    USER_ROLES,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
)


def test_the_role_vocabulary_is_closed() -> None:
    """The three roles the platform knows about."""
    assert USER_ROLES == ("advertiser", "publisher", "admin")
    assert DEFAULT_ROLE == "advertiser"


def test_a_registration_defaults_to_the_advertiser_role() -> None:
    """A new account buys inventory until it says otherwise."""
    request = RegisterRequest(name="Alex", email="alex@example.com", password="example-password")

    assert request.role == "advertiser"


def test_a_registration_may_ask_for_the_publisher_role() -> None:
    """A caller may state the role it wants."""
    request = RegisterRequest(
        name="Alex", email="alex@example.com", password="example-password", role="publisher"
    )

    assert request.role == "publisher"


def test_the_role_is_normalised() -> None:
    """A role in a different case is still the same role."""
    request = RegisterRequest(
        name="Alex", email="alex@example.com", password="example-password", role="PUBLISHER"
    )

    assert request.role == "publisher"


def test_an_unknown_role_is_refused() -> None:
    """A role outside the known set never reaches the database."""
    with pytest.raises(ValidationError):
        RegisterRequest(
            name="Alex", email="alex@example.com", password="example-password", role="superuser"
        )


def test_the_email_is_normalised() -> None:
    """The address is lowercased, so the same person is the same account."""
    request = RegisterRequest(name="Alex", email="  Alex@Example.COM ", password="example-password")

    assert request.email == "alex@example.com"


@pytest.mark.parametrize("address", ["no-at-sign", "@example.com", "alex@", "   "])
def test_an_unusable_email_is_refused(address: str) -> None:
    """An address that could not be delivered to is refused."""
    with pytest.raises(ValidationError):
        RegisterRequest(name="Alex", email=address, password="example-password")


def test_a_short_password_is_refused() -> None:
    """A password below the minimum length never reaches the hash."""
    with pytest.raises(ValidationError):
        RegisterRequest(name="Alex", email="alex@example.com", password="short")


def test_a_login_carries_an_address_and_a_password() -> None:
    """The login request is the pair the credential check needs."""
    request = LoginRequest(email="alex@example.com", password="example-password")

    assert request.email == "alex@example.com"


def test_a_password_reset_request_carries_only_an_address() -> None:
    """The reset request is an address and nothing else."""
    request = PasswordResetRequest(email="alex@example.com")

    assert request.email == "alex@example.com"


def test_a_password_reset_confirmation_carries_a_token() -> None:
    """The confirmation carries the token and the new password."""
    request = PasswordResetConfirm(token="t" * 32, password="example-password")

    assert request.token == "t" * 32
