from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00" + b"\x1f\x15\xc4\x89" + b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4" + b"\x00\x00\x00\x00IEND\xaeB`\x82"


@pytest.fixture()
def creative_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "creatives.db"))
    monkeypatch.setattr("app.creatives.settings.storage_dir", str(tmp_path / "storage"))
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/register", json={"name": "Creative Owner", "email": "creative@example.com", "password": "correct-horse-battery"})
        assert response.status_code == 201
        yield client


def campaign_payload() -> dict[str, object]:
    return {"name": "Tour campaign", "product": "Tour package", "description": "A seven day guided tour package for university students.", "objective": "sales", "location": "Dhaka", "audience": "University students", "budget": 500, "duration_days": 7, "landing_page": "https://example.com/tour", "tone": "Warm", "platforms": ["Meta"]}


def test_creative_upload_search_attach_download_and_delete(creative_client: TestClient) -> None:
    campaign_id = creative_client.post("/api/v1/campaigns", json=campaign_payload()).json()["id"]
    response = creative_client.post("/api/v1/creatives", files={"file": ("hero.png", PNG, "image/png")})

    assert response.status_code == 201
    creative = response.json()
    assert creative["file_type"] == "image"
    assert creative["width"] == 1
    assert creative["height"] == 1
    assert creative["file_size"] == len(PNG)
    assert creative_client.get("/api/v1/creatives", params={"search": "hero"}).json()[0]["id"] == creative["id"]
    assert creative_client.get("/api/v1/creatives", params={"file_type": "video"}).json() == []

    attached = creative_client.post(f"/api/v1/creatives/{creative['id']}/attach", json={"campaign_ids": [campaign_id]})
    assert attached.status_code == 200
    assert attached.json()["campaign_ids"] == [campaign_id]
    assert creative_client.get(f"/api/v1/creatives/{creative['id']}/file").content == PNG

    deleted = creative_client.delete(f"/api/v1/creatives/{creative['id']}")
    assert deleted.status_code == 204
    assert creative_client.get("/api/v1/creatives").json() == []


def test_creative_rejects_unsupported_and_invalid_image(creative_client: TestClient) -> None:
    unsupported = creative_client.post("/api/v1/creatives", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert unsupported.status_code == 415
    invalid_image = creative_client.post("/api/v1/creatives", files={"file": ("broken.png", b"not a png", "image/png")})
    assert invalid_image.status_code == 400


def test_creative_attachment_and_library_are_owner_scoped(creative_client: TestClient) -> None:
    campaign_id = creative_client.post("/api/v1/campaigns", json=campaign_payload()).json()["id"]
    creative_id = creative_client.post("/api/v1/creatives", files={"file": ("private.png", PNG, "image/png")}).json()["id"]
    creative_client.post("/api/v1/auth/logout")
    creative_client.post("/api/v1/auth/register", json={"name": "Other User", "email": "other@example.com", "password": "correct-horse-battery"})

    assert creative_client.get("/api/v1/creatives").json() == []
    assert creative_client.get(f"/api/v1/creatives/{creative_id}/file").status_code == 404
    assert creative_client.post(f"/api/v1/creatives/{creative_id}/attach", json={"campaign_ids": [campaign_id]}).status_code == 404
    assert creative_client.delete(f"/api/v1/creatives/{creative_id}").status_code == 404
