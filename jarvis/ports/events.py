"""The ``EventPublisher`` port — the seam over the event bus (README §3.6).

In-process now, swappable for Redis/NATS later. Use-cases and adapters publish
through this port; the concrete ``EventBus`` in ``jarvis.app.events`` implements
it. Subscription is a property of the concrete bus, not of this producer-facing
port.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from jarvis.domain.events import Event

__all__ = ["EventPublisher"]


@runtime_checkable
class EventPublisher(Protocol):
    async def publish(self, event: Event) -> None: ...
