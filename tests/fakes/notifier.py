"""In-memory fake for the ``Notifier`` port — records sent messages."""

from __future__ import annotations


class FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str | None]] = []

    async def notify(self, message: str, *, target: str | None = None) -> None:
        self.sent.append((message, target))
