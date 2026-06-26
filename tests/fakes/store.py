"""In-memory fake for the ``Store`` port — dict-backed, no I/O.

Shares the contract the SQLite adapter will be tested against (README §3.9).
"""

from __future__ import annotations

from collections.abc import Sequence

from jarvis.domain.models import Capability, Job, Session, Speaker


class InMemoryStore:
    def __init__(self) -> None:
        self._sessions: dict[tuple[str, str], Session] = {}
        self._jobs: dict[str, Job] = {}
        self._speakers: dict[str, Speaker] = {}
        self._capabilities: dict[str, Capability] = {}
        self._config: dict[str, str] = {}

    async def get_session(self, key: tuple[str, str]) -> Session | None:
        return self._sessions.get(key)

    async def upsert_session(self, session: Session) -> None:
        self._sessions[session.key] = session

    async def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    async def upsert_job(self, job: Job) -> None:
        self._jobs[job.id] = job

    async def list_jobs(self) -> Sequence[Job]:
        return list(self._jobs.values())

    async def get_speaker(self, speaker_id: str) -> Speaker | None:
        return self._speakers.get(speaker_id)

    async def upsert_speaker(self, speaker: Speaker) -> None:
        self._speakers[speaker.id] = speaker

    async def list_speakers(self) -> Sequence[Speaker]:
        return list(self._speakers.values())

    async def list_capabilities(self) -> Sequence[Capability]:
        return list(self._capabilities.values())

    async def upsert_capability(self, capability: Capability) -> None:
        self._capabilities[capability.name] = capability

    async def get_config(self, key: str) -> str | None:
        return self._config.get(key)

    async def set_config(self, key: str, value: str) -> None:
        self._config[key] = value
