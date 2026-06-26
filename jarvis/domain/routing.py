"""RoutingPolicy — classify a request as QUICK_QA or ASYNC_JOB.

Device commands ("turn on the kitchen lights") are handled upstream by the hub
and never reach us (README §5). What's left is either a quick spoken answer or an
async coding job that we acknowledge now and notify on later.

The policy is explicit and rule-driven first, and can grow smarter behind the
same ``classify`` interface. Its parameters are config-driven (README §3.5): the
async triggers are injected, defaulting to *none* — so in M1 everything routes to
QUICK_QA. M2 wires the ASYNC_JOB path and populates the triggers from config
(``SUGGESTED_ASYNC_TRIGGERS`` is a ready starting set).
"""

from __future__ import annotations

from collections.abc import Sequence

from jarvis.domain.models import Request, Route, RoutingDecision

__all__ = ["SUGGESTED_ASYNC_TRIGGERS", "RoutingPolicy"]

# A starting set of cues that indicate a coding job rather than a question.
# Not enabled by default — M2 opts in via config.
SUGGESTED_ASYNC_TRIGGERS: tuple[str, ...] = (
    "open a pr",
    "open a pull request",
    "fix the",
    "refactor",
    "implement",
    "add a test",
    "in the repo",
    "bump",
    "deploy",
    "kick off",
)


class RoutingPolicy:
    def __init__(self, *, async_triggers: Sequence[str] = ()) -> None:
        self._async_triggers = tuple(trigger.lower() for trigger in async_triggers)

    def classify(self, request: Request) -> RoutingDecision:
        text = request.text.lower()
        for trigger in self._async_triggers:
            if trigger in text:
                return RoutingDecision(
                    route=Route.ASYNC_JOB,
                    reason=f"matched async trigger: {trigger!r}",
                )
        return RoutingDecision(route=Route.QUICK_QA, reason="no async trigger matched")
