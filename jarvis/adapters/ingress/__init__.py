"""Ingress adapters — map an input surface's payload to a domain ``Utterance``."""

from jarvis.adapters.ingress.ha_conversation import (
    HaConversationIngress,
    HaConversationPayload,
)

__all__ = ["HaConversationIngress", "HaConversationPayload"]
