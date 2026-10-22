"""Password and API key hashing.

Both credentials are hashed with scrypt, because a user-chosen password is a
low-entropy secret and scrypt is deliberately slow to compute. A stored hash
records the parameters it was created with, so the work factor can be raised
later without invalidating the credentials that already exist.

The comparison is constant time, so a caller cannot learn the stored hash one
byte at a time from how long the endpoint takes to answer.
"""

from __future__ import annotations

import hashlib
import hmac
import os

#: Cost parameter for scrypt. 2**14 is the smallest value considered safe.
SCRYPT_N: int = 2**14

#: Block size for scrypt.
SCRYPT_R: int = 8

#: Parallelisation for scrypt.
SCRYPT_P: int = 1

#: Length of the derived key in bytes.
SCRYPT_DKLEN: int = 64

#: Number of random bytes in the per-password salt.
SALT_BYTES: int = 16


def hash_password(password: str) -> str:
    """Return a salted scrypt hash of a password.

    The result records the scheme and the parameters, so
    :func:`verify_password` can check it without consulting the current
    defaults.
    """
    salt = os.urandom(SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Return whether a password matches a stored hash.

    A stored hash that cannot be parsed is a failed verification rather than
    an error: a corrupted record must not turn into a crash in the middle of a
    sign-in attempt.
    """
    try:
        algorithm, n, r, p, salt_hex, expected_hex = encoded.split("$")
        if algorithm != "scrypt":
            return False
        expected = bytes.fromhex(expected_hex)
        actual = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def hash_api_key(key: str) -> str:
    """Return the stored form of an API key."""
    return hash_password(key)


def verify_api_key(key: str, encoded: str) -> bool:
    """Return whether an API key matches its stored form."""
    return verify_password(key, encoded)
