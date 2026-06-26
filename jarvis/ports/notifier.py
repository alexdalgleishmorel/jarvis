"""The ``Notifier`` port — the messenger (README §5, §6).

Pings you when an async job finishes. ``target`` selects where the message goes
(a Slack channel, a push token); ``None`` uses the adapter's default.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["Notifier"]


@runtime_checkable
class Notifier(Protocol):
    async def notify(self, message: str, *, target: str | None = None) -> None: ...
