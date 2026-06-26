"""Tests for the composition root (README §5, §8)."""

import pytest
from fastapi.testclient import TestClient

from jarvis.app.config import Settings, check_billing_guard
from jarvis.app.main import create_app


def _settings(**overrides) -> Settings:
    base = {
        "brain_mode": "echo",
        "tts_mode": "null",
        "store_url": "sqlite+aiosqlite:///:memory:",
        "ha_token": "test-token",
        "default_area": "home",
    }
    base.update(overrides)
    return Settings(**base)


def test_billing_guard_raises_when_key_present_under_subscription():
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        check_billing_guard(
            _settings(billing_mode="subscription"), env={"ANTHROPIC_API_KEY": "sk-leak"}
        )


def test_billing_guard_allows_clean_env_and_api_key_mode():
    # Clean env: fine.
    check_billing_guard(_settings(billing_mode="subscription"), env={})
    # Explicit API-key mode: the key is expected.
    check_billing_guard(_settings(billing_mode="api_key"), env={"ANTHROPIC_API_KEY": "sk"})


def test_app_boots_and_answers_with_echo_brain():
    app = create_app(_settings(), env={})
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}

        resp = client.post("/ingress/utterance", json={"text": "hello", "area": "kitchen"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == "You said: hello"  # EchoBrain
        assert body["trace_id"]
        assert body["latency_ms"] is not None


def test_app_persists_session_across_requests():
    app = create_app(_settings(), env={})
    with TestClient(app) as client:
        client.post("/ingress/utterance", json={"text": "who won in 1998?", "area": "kitchen"})
        # Second turn in the same room continues the session (no error, still answers).
        resp = client.post("/ingress/utterance", json={"text": "and 1999?", "area": "kitchen"})
        assert resp.status_code == 200
        assert resp.json()["text"] == "You said: and 1999?"
