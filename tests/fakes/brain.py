"""In-memory fake for the ``Brain`` port (README §3.9).

Returns a canned ``BrainResult`` and records every invocation so tests can
assert on the model, tool allow-list, and budget — all without spending tokens.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from jarvis.domain.models import Request, Session
from jarvis.ports.brain import BrainResult, Budget, Usage


@dataclass
class BrainCall:
    request: Request
    session: Session
    tools: tuple[str, ...]
    model: str | None
    budget: Budget | None


class FakeBrain:
    def __init__(
        self,
        *,
        response: str = "(fake answer)",
        brain_session_id: str = "fake-session",
        cost: float = 0.0,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.brain_session_id = brain_session_id
        self.cost = cost
        self.error = error
        self.calls: list[BrainCall] = []

    async def invoke(
        self,
        request: Request,
        session: Session,
        *,
        tools: Sequence[str] | None = None,
        model: str | None = None,
        budget: Budget | None = None,
    ) -> BrainResult:
        self.calls.append(
            BrainCall(
                request=request,
                session=session,
                tools=tuple(tools or ()),
                model=model,
                budget=budget,
            )
        )
        if self.error is not None:
            raise self.error
        return BrainResult(
            text=self.response,
            brain_session_id=self.brain_session_id,
            cost=self.cost,
            usage=Usage(input_tokens=10, output_tokens=20),
            tool_activity=(),
        )

    @property
    def last_call(self) -> BrainCall:
        return self.calls[-1]
