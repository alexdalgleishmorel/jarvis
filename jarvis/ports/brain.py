"""The ``Brain`` port — the single seam over cognition (README §3.3, §5).

All reasoning goes through here. How Claude is reached (``claude -p`` vs Agent
SDK), auth, billing mode, and model policy are implementation details of one
adapter; the rest of the system never knows.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from jarvis.domain.models import Request, Session

__all__ = ["Brain", "BrainError", "BrainRateLimited", "BrainResult", "Budget", "Usage"]


class BrainError(RuntimeError):
    """A brain invocation failed. Caught by handle_utterance's fail-soft path."""


class BrainRateLimited(BrainError):
    """The brain hit a rate/usage limit (README §8). Handled with a distinct,
    graceful spoken message rather than the generic failure fallback."""


@dataclass(frozen=True, slots=True)
class Usage:
    """Token usage reported by a brain invocation."""

    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True, slots=True)
class Budget:
    """Per-invocation guard rails (README §8): a turn cap and a cost ceiling."""

    max_turns: int | None = None
    max_cost: float | None = None


@dataclass(frozen=True, slots=True)
class BrainResult:
    """What a brain invocation returns.

    ``brain_session_id`` is threaded back into the ``Session`` so the next
    utterance can ``--resume``. ``cost``/``usage`` are captured on every
    invocation (README §13); ``tool_activity`` names the tools the brain used.
    """

    text: str
    brain_session_id: str | None = None
    cost: float | None = None
    usage: Usage | None = None
    tool_activity: tuple[str, ...] = ()


@runtime_checkable
class Brain(Protocol):
    async def invoke(
        self,
        request: Request,
        session: Session,
        *,
        tools: Sequence[str] | None = None,
        model: str | None = None,
        budget: Budget | None = None,
    ) -> BrainResult: ...
