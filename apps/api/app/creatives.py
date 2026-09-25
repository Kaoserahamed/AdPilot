import secrets

import sqlite3
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .auth import _current_user
from .config import settings

router = APIRouter(prefix="/api/v1/creatives", tags=["creatives"])
CreativeType = Literal["image", "video", "logo"]
ALLOWED_TYPES = {
    "image/jpeg": ("image", ".jpg"),
    "image/png": ("image", ".png"),
    "image/webp": ("image", ".webp"),
    "image/svg+xml": ("logo", ".svg"),
    "video/mp4": ("video", ".mp4"),
    "video/quicktime": ("video", ".mov"),
    "video/webm": ("video", ".webm"),
}


class CreativeResponse(BaseModel):
    id: int
    file_name: str
    file_url: str
    file_type: CreativeType
    mime_type: str
    file_size: int
    width: int | None
    height: int | None
    duration: float | None
    created_at: str
    campaign_ids: list[int]


class AttachRequest(BaseModel):
    campaign_ids: Annotated[list[int], Field(min_length=1, max_length=50)]


def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(settings.auth_db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_creative_db() -> None:
    from .auth import init_db
    from .campaigns import init_campaign_db

    init_db()
    init_campaign_db()
    Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)
    with _database() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS creatives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                file_name TEXT NOT NULL, stored_name TEXT NOT NULL UNIQUE, file_type TEXT NOT NULL,
                mime_type TEXT NOT NULL, file_size INTEGER NOT NULL, width INTEGER, height INTEGER,
                duration REAL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS campaign_creatives (
                campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
                creative_id INTEGER NOT NULL REFERENCES creatives(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL, PRIMARY KEY (campaign_id, creative_id)
            );
            """
        )


def _user(session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name)):
    return _current_user(session_token)


def _image_dimensions(data: bytes, mime_type: str) -> tuple[int | None, int | None]:
    try:
        if mime_type == "image/png" and data[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", data[16:24])
        if mime_type == "image/gif" and data[:3] == b"GIF":
            return struct.unpack("<HH", data[6:10])
        if mime_type == "image/jpeg" and data[:2] == b"\xff\xd8":
            offset = 2
            while offset < len(data) - 9:
                if data[offset] != 0xFF:
                    offset += 1
                    continue
                marker = data[offset + 1]
                offset += 2
                if marker in (0xD8, 0xD9):
                    continue
                length = int.from_bytes(data[offset:offset + 2], "big")
                if marker in range(0xC0, 0xC4):
                    return int.from_bytes(data[offset + 5:offset + 7], "big"), int.from_bytes(data[offset + 3:offset + 5], "big")
                offset += length
    except (IndexError, ValueError, struct.error):
        return None, None
    return None, None


def _owned_creative(connection: sqlite3.Connection, creative_id: int, user_id: int) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM creatives WHERE id = ? AND user_id = ?", (creative_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creative not found")
    return row


def _owned_campaign(connection: sqlite3.Connection, campaign_id: int, user_id: int) -> sqlite3.Row:
    row = connection.execute("SELECT id FROM campaigns WHERE id = ? AND user_id = ?", (campaign_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return row


@router.get("", response_model=list[CreativeResponse])
def list_creatives(search: str | None = Query(default=None, max_length=120), file_type: CreativeType | None = None, user=Depends(_user)) -> list[CreativeResponse]:
    init_creative_db()
    query = "SELECT * FROM creatives WHERE user_id = ?"
    values: list[object] = [user["id"]]
    if search:
        query += " AND file_name LIKE ?"
        values.append(f"%{search}%")
    if file_type:
        query += " AND file_type = ?"
        values.append(file_type)
    query += " ORDER BY created_at DESC"
    with _database() as connection:
        return [_row(row) for row in connection.execute(query, values).fetchall()]


@router.post("", response_model=CreativeResponse, status_code=status.HTTP_201_CREATED)
async def upload_creative(file: UploadFile = File(...), user=Depends(_user)) -> CreativeResponse:
    init_creative_db()
    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file type")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty")
    if len(data) > settings.creative_max_file_size_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds the 25 MB upload limit")
    creative_type, extension = ALLOWED_TYPES[mime_type]
    original_name = Path(file.filename or "creative").name[:180]
    stored_name = f"{secrets.token_hex(16)}{extension}"
    storage_root = Path(settings.storage_dir).resolve()
    storage_path = storage_root / f"user-{user['id']}" / stored_name
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(data)
    width, height = _image_dimensions(data, mime_type) if creative_type == "image" else (None, None)
    if creative_type == "image" and (width is None or height is None):
        storage_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image dimensions could not be read")
    now = datetime.now(timezone.utc).isoformat()
    with _database() as connection:
        cursor = connection.execute("INSERT INTO creatives (user_id, file_name, stored_name, file_type, mime_type, file_size, width, height, duration, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (user["id"], original_name, stored_name, creative_type, mime_type, len(data), width, height, None, now))
        row = connection.execute("SELECT * FROM creatives WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row(row)


@router.get("/{creative_id}/file")
def download_creative(creative_id: int, user=Depends(_user)) -> FileResponse:
    init_creative_db()
    with _database() as connection:
        row = _owned_creative(connection, creative_id, user["id"])
    path = (Path(settings.storage_dir).resolve() / f"user-{user['id']}" / row["stored_name"]).resolve()
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creative file not found")
    return FileResponse(path, media_type=row["mime_type"], filename=row["file_name"])


@router.post("/{creative_id}/attach", response_model=CreativeResponse)
def attach_creative(creative_id: int, payload: AttachRequest, user=Depends(_user)) -> CreativeResponse:
    init_creative_db()
    with _database() as connection:
        row = _owned_creative(connection, creative_id, user["id"])
        for campaign_id in set(payload.campaign_ids):
            _owned_campaign(connection, campaign_id, user["id"])
            connection.execute("INSERT OR IGNORE INTO campaign_creatives (campaign_id, creative_id, created_at) VALUES (?, ?, ?)", (campaign_id, creative_id, datetime.now(timezone.utc).isoformat()))
    return _row(row)


@router.delete("/{creative_id}/campaigns/{campaign_id}", response_model=CreativeResponse)
def detach_creative(creative_id: int, campaign_id: int, user=Depends(_user)) -> CreativeResponse:
    init_creative_db()
    with _database() as connection:
        row = _owned_creative(connection, creative_id, user["id"])
        _owned_campaign(connection, campaign_id, user["id"])
        connection.execute("DELETE FROM campaign_creatives WHERE creative_id = ? AND campaign_id = ?", (creative_id, campaign_id))
    return _row(row)


@router.delete("/{creative_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_creative(creative_id: int, user=Depends(_user)) -> Response:
    init_creative_db()
    with _database() as connection:
        row = _owned_creative(connection, creative_id, user["id"])
        path = (Path(settings.storage_dir).resolve() / f"user-{user['id']}" / row["stored_name"]).resolve()
        connection.execute("DELETE FROM creatives WHERE id = ? AND user_id = ?", (creative_id, user["id"]))
    path.unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _row(row: sqlite3.Row) -> CreativeResponse:
    with _database() as connection:
        campaign_ids = [item[0] for item in connection.execute("SELECT campaign_id FROM campaign_creatives WHERE creative_id = ? ORDER BY campaign_id", (row["id"],))]
    return CreativeResponse(
        id=row["id"], file_name=row["file_name"], file_url=f"/api/v1/creatives/{row['id']}/file", file_type=row["file_type"],
        mime_type=row["mime_type"], file_size=row["file_size"], width=row["width"], height=row["height"],
        duration=row["duration"], created_at=row["created_at"], campaign_ids=campaign_ids,
    )
