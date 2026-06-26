"""EchoBrain — a tokenless brain adapter for local dev and the first e2e.

Returns a canned reply that echoes the request, so the whole audio loop
(hub → conductor → voice) can be validated without spending tokens or depending
on the §8 billing spike. Swap in ``ClaudeCodeBrain`` once billing is confirmed.
"""

from __future__ import annotations

from collections.abc import Sequence

from jarvis.domain.models import Request, Session
from jarvis.ports.brain import BrainResult, Budget, Usage

__all__ = ["EchoBrain"]


class EchoBrain:
    def __init__(self, *, prefix: str = "You said: ") -> None:
        self._prefix = prefix

    async def invoke(
        self,
        request: Request,
        session: Session,
        *,
        tools: Sequence[str] | None = None,
        model: str | None = None,
        budget: Budget | None = None,
    ) -> BrainResult:
        return BrainResult(
            text=f"{self._prefix}{request.text}",
            brain_session_id=session.brain_session_id or "echo-session",
            cost=0.0,
            usage=Usage(),
            tool_activity=(),
        )
