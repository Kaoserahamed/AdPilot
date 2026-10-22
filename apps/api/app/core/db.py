"""Shared SQLite helpers.

Every router needs the same two things: a connection configured identically, and
a check that a campaign belongs to the caller. Those helpers were previously
copy-pasted into ten and seven modules respectively, so a change to the
connection setup had to be repeated in ten places and it was easy to miss one.

``creatives.py`` selected only the ``id`` column because that is all it needed;
``owned_campaign`` returns the full row, which those call sites are free to
ignore. A missing campaign and one owned by another user both raise 404 on
purpose: distinguishing them would confirm that an id exists elsewhere.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import HTTPException, status

from .config import settings


def get_connection() -> sqlite3.Connection:
    """Open a configured connection to the application database.

    Foreign keys are enabled on every connection because SQLite defaults them
    off per connection, and ``Row`` is returned so callers can read by name.
    """

    path = Path(settings.auth_db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def owned_campaign(connection: sqlite3.Connection, campaign_id: int, user_id: int) -> sqlite3.Row:
    """Fetch a campaign the caller owns, or raise 404."""

    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT * FROM campaigns WHERE id = ? AND user_id = ?",
        (campaign_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return row
