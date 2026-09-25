from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_endpoint_defaults_to_sandbox() -> None:
    response = client.get("/api/ready")

    assert response.status_code == 200
    assert response.json()["integrations"] == "sandbox"
    assert response.json()["ai_provider"] == "mock"
