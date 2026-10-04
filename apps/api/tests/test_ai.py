"""AI provider selection and generation tests."""

from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.ai import GeminiProvider, OpenAIProvider, SandboxProvider, get_provider
from app.main import app


@pytest.fixture()
def ai_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("app.auth.settings.auth_db_path", str(tmp_path / "ai.db"))
    with TestClient(app) as client:
        assert client.post("/api/v1/auth/register", json={"name": "AI Owner", "email": "ai@example.com", "password": "correct-horse-battery"}).status_code == 201
        yield client


@pytest.fixture()
def provider_settings(monkeypatch: pytest.MonkeyPatch):
    """Point the provider resolver at explicit provider/key values."""

    def apply(provider: str, api_key: str) -> None:
        monkeypatch.setattr("app.ai.settings.ai_provider", provider)
        monkeypatch.setattr("app.ai.settings.ai_api_key", api_key)

    return apply


def test_default_provider_is_the_sandbox(provider_settings) -> None:
    provider_settings("mock", "")
    assert isinstance(get_provider(), SandboxProvider)


def test_sandbox_alias_resolves_without_a_key(provider_settings) -> None:
    # `sandbox` is the value documented in the README and defaulted in
    # compose.yaml, so it must not be rejected.
    provider_settings("sandbox", "")
    assert isinstance(get_provider(), SandboxProvider)


def test_sandbox_alias_still_resolves_when_a_key_is_present(provider_settings) -> None:
    # Regression: a user following the README who also sets an API key would
    # previously get a 503 because only the literal "mock" was recognised.
    provider_settings("sandbox", "sk-configured-but-sandbox-requested")
    assert isinstance(get_provider(), SandboxProvider)


def test_provider_name_is_matched_case_insensitively(provider_settings) -> None:
    provider_settings("SandBox", "")
    assert isinstance(get_provider(), SandboxProvider)


def test_openai_provider_requires_a_key(provider_settings) -> None:
    provider_settings("openai", "sk-test-key")
    provider = get_provider()

    assert isinstance(provider, OpenAIProvider)
    assert provider.name == "openai"


def test_gemini_provider_requires_a_key(provider_settings) -> None:
    provider_settings("gemini", "gemini-test-key")
    assert isinstance(get_provider(), GeminiProvider)


def test_configured_provider_falls_back_to_sandbox_without_a_key(provider_settings) -> None:
    # Asking for OpenAI with no key must not attempt a real call; the sandbox
    # keeps a fresh clone working with zero credentials.
    provider_settings("openai", "")
    assert isinstance(get_provider(), SandboxProvider)


def test_unknown_provider_is_rejected_and_names_the_bad_value(provider_settings) -> None:
    provider_settings("not-a-provider", "sk-test-key")

    with pytest.raises(HTTPException) as raised:
        get_provider()

    assert raised.value.status_code == 503
    # The message must name the offending value so it is actionable.
    assert "not-a-provider" in raised.value.detail


def campaign_payload() -> dict[str, object]:
    return {"name": "Tour launch", "product": "Bangladesh tour package", "description": "A seven day guided tour package for university students.", "objective": "sales", "location": "Dhaka, Bangladesh", "audience": "University students", "budget": 500, "duration_days": 7, "landing_page": "https://example.com/tour", "tone": "Adventurous and warm", "platforms": ["Meta", "Google"]}


def create_campaign(client: TestClient) -> int:
    return client.post("/api/v1/campaigns", json=campaign_payload()).json()["id"]


def test_generate_and_latest_generation(ai_client: TestClient) -> None:
    campaign_id = create_campaign(ai_client)
    response = ai_client.post("/api/v1/ai/generate-campaign", json={"campaign_id": campaign_id})

    assert response.status_code == 201
    generated = response.json()
    assert generated["provider"] == "sandbox"
    assert generated["status"] == "generated"
    assert {ad["platform"] for ad in generated["content"]["platform_ads"]} == {"Meta", "Google"}
    assert ai_client.get(f"/api/v1/ai/campaigns/{campaign_id}/generation").json()["id"] == generated["id"]


def test_edit_and_manual_review_save(ai_client: TestClient) -> None:
    campaign_id = create_campaign(ai_client)
    generated = ai_client.post("/api/v1/ai/generate-campaign", json={"campaign_id": campaign_id}).json()
    edited = ai_client.post("/api/v1/ai/edit", json={"campaign_id": campaign_id, "platform": "Meta", "action": "change_cta", "value": "Book now"})

    assert edited.status_code == 201
    assert edited.json()["status"] == "edited"
    assert any(ad["cta"] == "Book now" for ad in edited.json()["content"]["platform_ads"] if ad["platform"] == "Meta")

    content = edited.json()["content"]
    saved = ai_client.put(f"/api/v1/ai/generations/{edited.json()['id']}", json={"content": content})
    assert saved.status_code == 200
    assert saved.json()["status"] == "reviewed"
    assert generated["id"] != saved.json()["id"]


def test_malformed_provider_output_is_rejected(ai_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign_id = create_campaign(ai_client)

    class InvalidProvider:
        name = "invalid"
        model = "test"

        def generate(self, campaign: dict[str, object], instruction: str | None = None) -> dict[str, object]:
            return {"strategy": {"unexpected": "missing required fields"}}

        def edit(self, content: dict[str, object], platform: str, action: str, value: str | None = None) -> dict[str, object]:
            return content

    monkeypatch.setattr("app.ai.get_provider", lambda: InvalidProvider())
    response = ai_client.post("/api/v1/ai/generate-campaign", json={"campaign_id": campaign_id})

    assert response.status_code == 422
    assert ai_client.get(f"/api/v1/ai/campaigns/{campaign_id}/generation").status_code == 404


def test_generation_is_owner_scoped(ai_client: TestClient) -> None:
    campaign_id = create_campaign(ai_client)
    generated = ai_client.post("/api/v1/ai/generate-campaign", json={"campaign_id": campaign_id}).json()
    ai_client.post("/api/v1/auth/logout")
    ai_client.post("/api/v1/auth/register", json={"name": "Other AI User", "email": "other-ai@example.com", "password": "correct-horse-battery"})

    assert ai_client.get(f"/api/v1/ai/campaigns/{campaign_id}/generation").status_code == 404
    assert ai_client.post("/api/v1/ai/generate-campaign", json={"campaign_id": campaign_id}).status_code == 404
    assert ai_client.put(f"/api/v1/ai/generations/{generated['id']}", json={"content": generated["content"]}).status_code == 404
