"""Runtime configuration for the conductor (README §3.5, §8).

Everything tunable is here, read from ``JARVIS_*`` env vars (or a ``.env``), never
hard-coded. Two M1-friendly defaults keep a fresh boot safe:

* ``brain_mode="echo"`` — answer without spending tokens until the §8 billing
  spike (#18) confirms the subscription pool; flip to ``claude`` then.
* ``tts_mode="null"`` — let Home Assistant's pipeline speak the returned text in
  conversation-agent mode (avoids double speech).

``check_billing_guard`` enforces README §8/§13: with subscription billing, a
stray ``ANTHROPIC_API_KEY`` would silently bill the per-token API account, so we
fail loudly if one is present.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "check_billing_guard"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JARVIS_", env_file=".env", extra="ignore")

    # Brain
    brain_mode: Literal["echo", "claude"] = "echo"
    billing_mode: Literal["subscription", "api_key"] = "subscription"
    claude_executable: str = "claude"
    # Model tiering (README §8): a cheap/fast model for quick Q&A. A stronger model
    # for async coding jobs lands with that path in M2.
    quick_model: str | None = "haiku"
    # Budget guard: per-invocation turn cap (bounds runaway tool loops / cost).
    max_turns: int | None = 6
    rate_limit_message: str = "I'm at my limit right now — try me again in a little while."

    # Hub (Home Assistant)
    ha_base_url: str = "http://homeassistant.local:8123"
    ha_token: str = ""

    # Voice
    tts_mode: Literal["null", "ha_piper"] = "null"
    tts_entity_id: str = "tts.piper"

    # Conductor
    default_area: str = "home"
    session_idle_timeout_s: int = 300
    async_triggers: list[str] = []
    store_url: str = "sqlite+aiosqlite:///jarvis.db"
    log_level: str = "INFO"


def check_billing_guard(settings: Settings, *, env: Mapping[str, str] | None = None) -> None:
    """Fail loudly if an API key is present under subscription billing (README §8)."""
    environ = os.environ if env is None else env
    if settings.billing_mode == "subscription" and environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is set but billing_mode is 'subscription'. Unset it so the "
            "brain draws from the Claude subscription, not the per-token API account "
            "(README §8). If you really intend API billing, set JARVIS_BILLING_MODE=api_key."
        )
