"""In-process async pub/sub — the backbone of extensibility (README §3.6).

In-proc to start, swappable for Redis/NATS later behind this same small surface.
New interfaces and observers *subscribe to events* rather than being wired into
the request path.

Two guarantees make observers safe to attach:

* **Publishers are never stalled.** ``publish`` schedules each handler as its own
  task and returns immediately — a slow observer cannot hold up the request path.
* **One bad observer can't break the others.** Handler exceptions are caught and
  logged, never propagated to the publisher or sibling handlers.

Subscribe with an exact topic (``"response.ready"``), a prefix wildcard
(``"job.*"``), or ``"*"`` for everything. Tests use :meth:`EventBus.drain` to
await in-flight handlers deterministically.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from jarvis.domain.events import Event

__all__ = ["EventBus", "EventHandler"]

logger = logging.getLogger("jarvis.events")

EventHandler = Callable[[Event], Awaitable[None]]


def _matches(pattern: str, topic: str) -> bool:
    if pattern == "*":
        return True
    if pattern.endswith(".*"):
        return topic.startswith(pattern[:-1])  # "job.*" -> prefix "job."
    return pattern == topic


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[tuple[str, EventHandler]] = []
        # Hold strong refs to in-flight handler tasks so they aren't GC'd, and
        # drop each one as it finishes (bounded memory in a long-running process).
        self._tasks: set[asyncio.Future[None]] = set()

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        """Register ``handler`` for a topic / wildcard. Order of registration is
        the order of dispatch, but handlers run concurrently regardless."""
        self._subscribers.append((topic, handler))

    async def publish(self, event: Event) -> None:
        """Fan the event out to matching subscribers without awaiting them."""
        for pattern, handler in self._subscribers:
            if _matches(pattern, event.topic):
                task = asyncio.create_task(self._dispatch(handler, event))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)

    async def _dispatch(self, handler: EventHandler, event: Event) -> None:
        try:
            await handler(event)
        except Exception:  # an observer must never break the publisher
            logger.exception("event handler failed for topic %s", event.topic)

    async def drain(self) -> None:
        """Await all in-flight handlers. Mainly for tests and clean shutdown."""
        while self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)
