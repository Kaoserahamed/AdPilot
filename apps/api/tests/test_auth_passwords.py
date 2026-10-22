"""Tests for the credential hashing primitives.

The point of these tests is the rule the whole scheme rests on: a stored
credential is a hash, never the secret, and a wrong secret never verifies.
"""

from __future__ import annotations

from app.auth.passwords import (
    hash_api_key,
    hash_password,
    verify_api_key,
    verify_password,
)


def test_a_password_hash_is_never_the_password() -> None:
    """The stored value must not contain the plaintext it stands for."""
    encoded = hash_password("correct horse battery staple")

    assert "correct horse battery staple" not in encoded
    assert encoded.startswith("scrypt$")


def test_a_password_hash_records_its_parameters() -> None:
    """The parameters travel with the hash, so the work factor can be raised later."""
    encoded = hash_password("correct horse battery staple")

    algorithm, cost, block_size, parallelism, salt, derived = encoded.split("$")

    assert algorithm == "scrypt"
    assert int(cost) == 2**14
    assert int(block_size) == 8
    assert int(parallelism) == 1
    assert len(salt) == 32
    assert len(derived) == 128


def test_two_hashes_of_one_password_differ() -> None:
    """The salt is random, so the hashes cannot be compared across accounts."""
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")

    assert first != second


def test_the_right_password_verifies() -> None:
    """A password verifies against its own hash."""
    encoded = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", encoded)


def test_a_wrong_password_does_not_verify() -> None:
    """A password one character away does not verify."""
    encoded = hash_password("correct horse battery staple")

    assert not verify_password("correct horse battery stapl", encoded)


def test_a_hash_from_another_scheme_does_not_verify() -> None:
    """Only the scrypt scheme is accepted."""
    assert not verify_password("anything", "bcrypt$16384$8$1$aa$bb")


def test_a_corrupted_hash_does_not_raise() -> None:
    """A record that cannot be parsed is a failed verification, not a crash."""
    assert not verify_password("anything", "not-a-hash")
    assert not verify_password("anything", "scrypt$notanumber$8$1$aa$bb")


def test_an_api_key_is_stored_as_a_hash() -> None:
    """An API key is hashed the same way a password is."""
    key = "a-secret-api-key"
    encoded = hash_api_key(key)

    assert key not in encoded
    assert verify_api_key(key, encoded)
    assert not verify_api_key("another-key", encoded)
