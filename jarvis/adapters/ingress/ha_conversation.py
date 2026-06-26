"""HA conversation ingress — turn the hub's call into a domain ``Utterance``.

The conductor is registered as Home Assistant's conversation agent; everything
the hub can't handle natively is forwarded here as ``{text, area,
conversation_id, speaker?}`` (README §4, §5, §6). This adapter is the thin,
pure mapping from that payload to the domain. New input surfaces (a wall tablet,
a Slack DM) are just new ingress adapters producing an ``Utterance`` — the whole
pipeline downstream is reused (§9).

The optional ``speaker`` hint is accepted but not used in M1 (the
``SpeakerIdentifier`` resolves identity); it's a seam for later.
"""

from __future__ import annotations

from dataclasses import dataclass

from jarvis.domain.models import Utterance

__all__ = ["HaConversationIngress", "HaConversationPayload"]


@dataclass(frozen=True, slots=True)
class HaConversationPayload:
    text: str
    area: str | None = None
    conversation_id: str | None = None
    speaker: str | None = None


class HaConversationIngress:
    def __init__(self, *, default_area: str = "home") -> None:
        self._default_area = default_area

    def to_utterance(self, payload: HaConversationPayload) -> Utterance:
        return Utterance(
            text=payload.text,
            area=payload.area or self._default_area,
            conversation_id=payload.conversation_id,
        )
