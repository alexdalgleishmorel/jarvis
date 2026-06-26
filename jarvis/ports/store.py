"""The ``Store`` port — persistence (README §5, §10).

Holds sessions, jobs, speaker profiles, the capability registry, and assistant
config. SQLite now, Postgres-ready later — callers never know which. Typed config
CRUD grows on top of the simple key/value config methods here in M3.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from jarvis.domain.models import Capability, Job, Session, Speaker

__all__ = ["Store"]


@runtime_checkable
class Store(Protocol):
    # Sessions — keyed by (room_id, speaker_id), matching ``Session.key``.
    async def get_session(self, key: tuple[str, str]) -> Session | None: ...
    async def upsert_session(self, session: Session) -> None: ...

    # Jobs.
    async def get_job(self, job_id: str) -> Job | None: ...
    async def upsert_job(self, job: Job) -> None: ...
    async def list_jobs(self) -> Sequence[Job]: ...

    # Speaker profiles.
    async def get_speaker(self, speaker_id: str) -> Speaker | None: ...
    async def upsert_speaker(self, speaker: Speaker) -> None: ...
    async def list_speakers(self) -> Sequence[Speaker]: ...

    # Capability registry.
    async def list_capabilities(self) -> Sequence[Capability]: ...
    async def upsert_capability(self, capability: Capability) -> None: ...

    # Assistant config (simple key/value; typed CRUD layers on this in M3).
    async def get_config(self, key: str) -> str | None: ...
    async def set_config(self, key: str, value: str) -> None: ...
