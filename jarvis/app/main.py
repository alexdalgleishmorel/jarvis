"""Composition root — instantiate adapters and inject them into the use-case.

The only layer that knows about concrete adapters (README §5). Real-vs-stub
selection (echo vs Claude brain, null vs Piper voice) is driven entirely by
config. Async resources (the store, the hub client) are built on startup via the
FastAPI lifespan and closed on shutdown.

Run with: ``uvicorn jarvis.app.main:create_app --factory``.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta

from fastapi import FastAPI

from jarvis.adapters.brain import BillingMode, ClaudeCodeBrain, EchoBrain
from jarvis.adapters.ha import HaRestHub
from jarvis.adapters.ingress import HaConversationIngress
from jarvis.adapters.speaker_id import NullSpeakerIdentifier
from jarvis.adapters.store import SqliteStore
from jarvis.adapters.tts import HaPiperTextToSpeech, NullTextToSpeech
from jarvis.app.api import create_ingress_router
from jarvis.app.config import Settings, check_billing_guard
from jarvis.app.events import EventBus
from jarvis.app.observability import configure_logging, new_trace_id, register_event_logging
from jarvis.domain.models import Response, Utterance
from jarvis.domain.routing import RoutingPolicy
from jarvis.domain.sessions import SessionManager
from jarvis.ports.brain import Brain
from jarvis.ports.tts import TextToSpeech
from jarvis.services.handle_utterance import HandleUtterance

__all__ = ["Components", "create_app"]


@dataclass
class Components:
    handle: HandleUtterance
    store: SqliteStore
    hub: HaRestHub

    async def aclose(self) -> None:
        await self.store.aclose()
        await self.hub.aclose()


def _log_level(name: str) -> int:
    level = logging.getLevelName(name.upper())
    return level if isinstance(level, int) else logging.INFO


def _build_brain(settings: Settings, env: Mapping[str, str]) -> Brain:
    if settings.brain_mode == "echo":
        return EchoBrain()
    return ClaudeCodeBrain(
        executable=settings.claude_executable,
        billing_mode=BillingMode(settings.billing_mode),
        api_key=env.get("ANTHROPIC_API_KEY"),
        default_model=settings.quick_model,
    )


def _build_tts(settings: Settings, hub: HaRestHub) -> TextToSpeech:
    if settings.tts_mode == "ha_piper":
        return HaPiperTextToSpeech(hub, tts_entity_id=settings.tts_entity_id)
    return NullTextToSpeech()


async def _build_components(settings: Settings, env: Mapping[str, str]) -> Components:
    store = await SqliteStore.create(settings.store_url)
    hub = HaRestHub(settings.ha_base_url, settings.ha_token)
    bus = EventBus()
    register_event_logging(bus)

    handle = HandleUtterance(
        speaker_identifier=NullSpeakerIdentifier(),
        session_manager=SessionManager(
            idle_timeout=timedelta(seconds=settings.session_idle_timeout_s)
        ),
        routing_policy=RoutingPolicy(async_triggers=settings.async_triggers),
        brain=_build_brain(settings, env),
        tts=_build_tts(settings, hub),
        store=store,
        events=bus,
        model=settings.quick_model,
        trace_id_factory=new_trace_id,
    )
    return Components(handle=handle, store=store, hub=hub)


def create_app(
    settings: Settings | None = None, *, env: Mapping[str, str] | None = None
) -> FastAPI:
    settings = settings or Settings()
    resolved_env = dict(env) if env is not None else None
    check_billing_guard(settings, env=resolved_env)
    configure_logging(level=_log_level(settings.log_level))

    build_env: Mapping[str, str] = resolved_env if resolved_env is not None else os.environ

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        components = await _build_components(settings, build_env)
        app.state.components = components
        app.state.handle = components.handle
        try:
            yield
        finally:
            await components.aclose()

    app = FastAPI(title="Jarvis conductor", lifespan=lifespan)

    ingress = HaConversationIngress(default_area=settings.default_area)

    async def handle(utterance: Utterance) -> Response:
        handler: HandleUtterance = app.state.handle
        return await handler(utterance)

    app.include_router(create_ingress_router(handle, ingress))

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
