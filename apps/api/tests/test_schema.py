"""Tests for the authentication database schema.

The schema has to be safe to run against a database that already exists, and
against one created before the role column existed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.auth.schema import init_db
from app.core import get_connection


@pytest.fixture()
def auth_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the service at a temporary database."""
    path = tmp_path / "schema.db"
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(path))
    return path


def test_the_schema_can_be_created_twice(auth_db: Path) -> None:
    """Starting the service against an existing database is not an error."""
    init_db()
    init_db()

    with get_connection() as connection:
        tables = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }

    assert {"users", "sessions", "password_resets", "api_keys"} <= tables


def test_a_new_user_defaults_to_the_advertiser_role(auth_db: Path) -> None:
    """The role column has a default, so an insert without one still works."""
    init_db()

    with get_connection() as connection:
        connection.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            ("Alex", "alex@example.com", "hash", "2026-01-01T00:00:00+00:00"),
        )
        row = connection.execute("SELECT role FROM users").fetchone()

    assert row["role"] == "advertiser"


def test_an_existing_database_gains_the_role_column(auth_db: Path) -> None:
    """A database created before roles existed is migrated in place."""
    with sqlite3.connect(auth_db) as connection:
        connection.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,"
            " email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO users (name, email, password_hash, created_at)"
            " VALUES ('Alex', 'alex@example.com', 'hash', '2026-01-01T00:00:00+00:00')"
        )

    init_db()

    with get_connection() as connection:
        row = connection.execute("SELECT role FROM users").fetchone()

    assert row["role"] == "advertiser"
