"""The FastAPI ingress endpoint the hub calls (README §5, §6).

Receives the conversation-agent payload, maps it to a domain ``Utterance`` via
the ingress adapter, runs ``handle_utterance``, and returns the reply text. In
the conversation-agent path Home Assistant's pipeline speaks that text.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import APIRouter
from pydantic import BaseModel

from jarvis.adapters.ingress import HaConversationIngress, HaConversationPayload
from jarvis.domain.models import Response, Utterance

__all__ = ["UtteranceRequest", "UtteranceResponse", "create_ingress_router"]

Handler = Callable[[Utterance], Awaitable[Response]]


class UtteranceRequest(BaseModel):
    text: str
    area: str | None = None
    conversation_id: str | None = None
    speaker: str | None = None


class UtteranceResponse(BaseModel):
    text: str
    trace_id: str
    conversation_id: str | None = None
    cost: float | None = None
    latency_ms: float | None = None


def create_ingress_router(handle: Handler, ingress: HaConversationIngress) -> APIRouter:
    router = APIRouter()

    @router.post("/ingress/utterance", response_model=UtteranceResponse)
    async def ingress_utterance(body: UtteranceRequest) -> UtteranceResponse:
        utterance = ingress.to_utterance(
            HaConversationPayload(
                text=body.text,
                area=body.area,
                conversation_id=body.conversation_id,
                speaker=body.speaker,
            )
        )
        response = await handle(utterance)
        return UtteranceResponse(
            text=response.text,
            trace_id=response.trace_id,
            conversation_id=body.conversation_id,
            cost=response.cost,
            latency_ms=response.latency_ms,
        )

    return router
