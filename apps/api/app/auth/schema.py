"""Database schema for the authentication service.

Four tables back authentication: the accounts themselves, the browser sessions,
the password reset tokens, and the API keys. The schema is created
idempotently, so starting the service against an empty database and starting
it against an existing one both work.
"""

from __future__ import annotations

import sqlite3

from app.core import get_connection as _database

#: The statement that adds the role column to a database created before roles
#: existed. A database that already has the column refuses the statement, and
#: the refusal is the expected path.
_ADD_ROLE_COLUMN = "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'advertiser'"


def init_db() -> None:
    """Create the authentication tables if they do not exist yet."""
    with _database() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'advertiser',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                key_hash TEXT NOT NULL,
                prefix TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                revoked_at TEXT,
                last_used_at TEXT
            );
            """
        )
    with _database() as connection:
        try:
            connection.execute(_ADD_ROLE_COLUMN)
        except sqlite3.OperationalError:
            pass
