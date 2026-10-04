"""Tests for the shared SQLite helpers.

These helpers replaced near-identical private copies that had been pasted into
ten and seven modules. The behaviour the copies had in common is asserted here
once, so a future change to connection setup has a single place to be verified.
"""

import sqlite3

import pytest
from fastapi import HTTPException

from app.db import get_connection, owned_campaign


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    """Point the settings object at a database inside the temporary directory."""

    path = tmp_path / "nested" / "helpers.db"
    monkeypatch.setattr("app.db.settings.auth_db_path", str(path))
    return path


def seed(db_path, campaign_id: int = 1, user_id: int = 1) -> None:
    """Create a minimal campaigns table holding one owned row."""

    connection = get_connection()
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS campaigns (id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT)"
        )
        connection.execute("INSERT INTO campaigns (id, user_id, name) VALUES (?, ?, ?)", (campaign_id, user_id, "Owned"))
        connection.commit()
    finally:
        connection.close()


def test_get_connection_creates_missing_parent_directories(db_path) -> None:
    """The directory is created on connect.

    auth.py did this in its copy; the other nine did not, so a fresh deployment
    with no data directory failed at the first query instead of at startup.
    """

    assert not db_path.parent.exists()

    connection = get_connection()

    assert db_path.parent.is_dir()
    assert db_path.exists()
    connection.close()


def test_get_connection_returns_rows_accessible_by_name(db_path) -> None:
    """row_factory is set, so callers can read columns by name."""

    connection = get_connection()
    try:
        connection.execute("CREATE TABLE campaigns (id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("INSERT INTO campaigns (id, name) VALUES (1, 'By name')")
        row = connection.execute("SELECT * FROM campaigns").fetchone()

        assert isinstance(row, sqlite3.Row)
        assert row["name"] == "By name"
    finally:
        connection.close()


def test_get_connection_enables_foreign_keys(db_path) -> None:
    """SQLite defaults foreign keys off per connection, so it must be set here."""

    connection = get_connection()
    try:
        enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0]

        assert enabled == 1
    finally:
        connection.close()


def test_owned_campaign_returns_the_row(db_path) -> None:
    """A campaign owned by the caller is returned with its columns."""

    seed(db_path)

    connection = get_connection()
    try:
        row = owned_campaign(connection, 1, 1)

        assert row["name"] == "Owned"
    finally:
        connection.close()


def test_owned_campaign_rejects_a_campaign_owned_by_someone_else(db_path) -> None:
    """Another user's campaign is reported as not found.

    Returning a distinct error here would confirm that the id exists, so the
    response must be identical to a genuinely missing campaign.
    """

    seed(db_path, campaign_id=1, user_id=1)

    connection = get_connection()
    try:
        with pytest.raises(HTTPException) as foreign:
            owned_campaign(connection, 1, user_id=2)
        with pytest.raises(HTTPException) as missing:
            owned_campaign(connection, 999, user_id=1)
    finally:
        connection.close()

    assert foreign.value.status_code == 404
    assert foreign.value.detail == missing.value.detail == "Campaign not found"
