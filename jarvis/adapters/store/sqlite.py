"""SQLite ``Store`` adapter — persistence behind the ``Store`` port (README §5, §11).

SQLite now, Postgres-ready: built on async SQLAlchemy 2.0, and upserts go through
``Session.merge`` (keyed by primary key) rather than a SQLite-specific
``ON CONFLICT``, so the same code runs on Postgres later.

The ORM rows live here, in the adapter — the domain dataclasses stay pure and are
mapped to/from these rows. Persists sessions, jobs, speaker profiles, the
capability registry, and key/value config; the typed config CRUD layers on top of
this in M3.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import JSON, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

from jarvis.domain.models import Capability, Job, JobStatus, Session, Speaker, SpeakerProfile

__all__ = ["SqliteStore"]


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"

    room_id: Mapped[str] = mapped_column(primary_key=True)
    speaker_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str] = mapped_column()
    created_at: Mapped[datetime] = mapped_column()
    last_active_at: Mapped[datetime] = mapped_column()
    brain_session_id: Mapped[str | None] = mapped_column()


class JobRow(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(primary_key=True)
    trace_id: Mapped[str] = mapped_column()
    prompt: Mapped[str] = mapped_column()
    target_repo: Mapped[str | None] = mapped_column()
    status: Mapped[str] = mapped_column()
    summary: Mapped[str | None] = mapped_column()
    brain_session_id: Mapped[str | None] = mapped_column()
    created_at: Mapped[datetime | None] = mapped_column()
    updated_at: Mapped[datetime | None] = mapped_column()


class SpeakerRow(Base):
    __tablename__ = "speakers"

    id: Mapped[str] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column()
    calendar_account: Mapped[str | None] = mapped_column()
    gmail_account: Mapped[str | None] = mapped_column()
    preferred_voice: Mapped[str | None] = mapped_column()
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list)


class CapabilityRow(Base):
    __tablename__ = "capabilities"

    name: Mapped[str] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(default="")
    required_permission: Mapped[str | None] = mapped_column()


class ConfigRow(Base):
    __tablename__ = "config"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column()


# ──────────────────────────── row ↔ domain mapping ────────────────────────────


def _to_session(row: SessionRow) -> Session:
    return Session(
        id=row.id,
        room_id=row.room_id,
        speaker_id=row.speaker_id,
        created_at=row.created_at,
        last_active_at=row.last_active_at,
        brain_session_id=row.brain_session_id,
    )


def _to_job(row: JobRow) -> Job:
    return Job(
        id=row.id,
        trace_id=row.trace_id,
        prompt=row.prompt,
        target_repo=row.target_repo,
        status=JobStatus(row.status),
        summary=row.summary,
        brain_session_id=row.brain_session_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_speaker(row: SpeakerRow) -> Speaker:
    return Speaker(
        id=row.id,
        profile=SpeakerProfile(
            display_name=row.display_name,
            calendar_account=row.calendar_account,
            gmail_account=row.gmail_account,
            preferred_voice=row.preferred_voice,
            permissions=frozenset(row.permissions),
        ),
    )


def _to_capability(row: CapabilityRow) -> Capability:
    return Capability(
        name=row.name,
        description=row.description,
        required_permission=row.required_permission,
    )


# ──────────────────────────── adapter ────────────────────────────


def _make_engine(url: str) -> AsyncEngine:
    if ":memory:" in url:
        # Keep one connection so the in-memory database survives across operations.
        return create_async_engine(
            url, poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
    return create_async_engine(url)


class SqliteStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    async def create(cls, url: str = "sqlite+aiosqlite:///:memory:") -> SqliteStore:
        engine = _make_engine(url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return cls(engine)

    async def aclose(self) -> None:
        await self._engine.dispose()

    # Sessions ----------------------------------------------------------------

    async def get_session(self, key: tuple[str, str]) -> Session | None:
        room_id, speaker_id = key
        async with self._sessionmaker() as db:
            row = await db.get(SessionRow, (room_id, speaker_id))
            return _to_session(row) if row is not None else None

    async def upsert_session(self, session: Session) -> None:
        async with self._sessionmaker() as db:
            await db.merge(
                SessionRow(
                    room_id=session.room_id,
                    speaker_id=session.speaker_id,
                    id=session.id,
                    created_at=session.created_at,
                    last_active_at=session.last_active_at,
                    brain_session_id=session.brain_session_id,
                )
            )
            await db.commit()

    # Jobs --------------------------------------------------------------------

    async def get_job(self, job_id: str) -> Job | None:
        async with self._sessionmaker() as db:
            row = await db.get(JobRow, job_id)
            return _to_job(row) if row is not None else None

    async def upsert_job(self, job: Job) -> None:
        async with self._sessionmaker() as db:
            await db.merge(
                JobRow(
                    id=job.id,
                    trace_id=job.trace_id,
                    prompt=job.prompt,
                    target_repo=job.target_repo,
                    status=job.status.value,
                    summary=job.summary,
                    brain_session_id=job.brain_session_id,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                )
            )
            await db.commit()

    async def list_jobs(self) -> Sequence[Job]:
        async with self._sessionmaker() as db:
            rows = (await db.scalars(select(JobRow))).all()
            return [_to_job(row) for row in rows]

    # Speakers ----------------------------------------------------------------

    async def get_speaker(self, speaker_id: str) -> Speaker | None:
        async with self._sessionmaker() as db:
            row = await db.get(SpeakerRow, speaker_id)
            return _to_speaker(row) if row is not None else None

    async def upsert_speaker(self, speaker: Speaker) -> None:
        async with self._sessionmaker() as db:
            await db.merge(
                SpeakerRow(
                    id=speaker.id,
                    display_name=speaker.profile.display_name,
                    calendar_account=speaker.profile.calendar_account,
                    gmail_account=speaker.profile.gmail_account,
                    preferred_voice=speaker.profile.preferred_voice,
                    permissions=sorted(speaker.profile.permissions),
                )
            )
            await db.commit()

    async def list_speakers(self) -> Sequence[Speaker]:
        async with self._sessionmaker() as db:
            rows = (await db.scalars(select(SpeakerRow))).all()
            return [_to_speaker(row) for row in rows]

    # Capabilities ------------------------------------------------------------

    async def list_capabilities(self) -> Sequence[Capability]:
        async with self._sessionmaker() as db:
            rows = (await db.scalars(select(CapabilityRow))).all()
            return [_to_capability(row) for row in rows]

    async def upsert_capability(self, capability: Capability) -> None:
        async with self._sessionmaker() as db:
            await db.merge(
                CapabilityRow(
                    name=capability.name,
                    description=capability.description,
                    required_permission=capability.required_permission,
                )
            )
            await db.commit()

    # Config ------------------------------------------------------------------

    async def get_config(self, key: str) -> str | None:
        async with self._sessionmaker() as db:
            row = await db.get(ConfigRow, key)
            return row.value if row is not None else None

    async def set_config(self, key: str, value: str) -> None:
        async with self._sessionmaker() as db:
            await db.merge(ConfigRow(key=key, value=value))
            await db.commit()
