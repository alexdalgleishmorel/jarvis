"""A no-op voice for the conversation-agent path (README §6).

When the conductor is Home Assistant's conversation agent, HA's own Assist
pipeline speaks the text the conductor returns. Wiring this null voice on the
synchronous QA path keeps ``handle_utterance`` calling the ``TextToSpeech`` port
uniformly while avoiding a double-spoken reply. Proactive speech (M2) uses the
real ``HaPiperTextToSpeech`` instead.
"""

from __future__ import annotations

__all__ = ["NullTextToSpeech"]


class NullTextToSpeech:
    async def speak(self, text: str, *, area: str) -> None:
        return None
