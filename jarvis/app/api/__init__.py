"""FastAPI routes — the hub ingress endpoint and (later) the config API."""

from jarvis.app.api.ingress import (
    UtteranceRequest,
    UtteranceResponse,
    create_ingress_router,
)

__all__ = ["UtteranceRequest", "UtteranceResponse", "create_ingress_router"]
