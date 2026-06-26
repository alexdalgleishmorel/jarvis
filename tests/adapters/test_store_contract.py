"""Shared Store contract — run against both InMemoryStore and SqliteStore.

The fake and the SQLite adapter must behave identically (README §3.9), so every
test here is parameterized over both implementations.
"""

from datetime import datetime

import pytest
import pytest_asyncio

from jarvis.adapters.store import SqliteStore
from jarvis.domain.models import (
    Capability,
    Job,
    JobStatus,
    Session,
    Speaker,
    SpeakerProfile,
)
from jarvis.ports import Store
from tests.fakes import InMemoryStore

BASE = datetime(2026, 6, 26, 9, 0, 0)


@pytest_asyncio.fixture(params=["memory", "sqlite"])
async def store(request, tmp_path):
    if request.param == "memory":
        yield InMemoryStore()
    else:
        impl = await SqliteStore.create(f"sqlite+aiosqlite:///{tmp_path}/jarvis.db")
        yield impl
        await impl.aclose()


def _session(brain_session_id=None) -> Session:
    return Session(
        id="s1",
        room_id="kitchen",
        speaker_id="household",
        created_at=BASE,
        last_active_at=BASE,
        brain_session_id=brain_session_id,
    )


async def test_satisfies_store_port(store):
    assert isinstance(store, Store)


async def test_session_roundtrip_and_upsert_by_key(store):
    assert await store.get_session(("kitchen", "household")) is None

    await store.upsert_session(_session())
    loaded = await store.get_session(("kitchen", "household"))
    assert loaded is not None
    assert loaded.id == "s1"
    assert loaded.brain_session_id is None

    # Upsert by the same (room, speaker) key overwrites in place.
    await store.upsert_session(_session(brain_session_id="brain-9"))
    reloaded = await store.get_session(("kitchen", "household"))
    assert reloaded.brain_session_id == "brain-9"


async def test_job_roundtrip_status_and_list(store):
    assert await store.get_job("j1") is None

    job = Job(id="j1", trace_id="t-1", prompt="bump deps", target_repo="acme/web")
    await store.upsert_job(job)

    loaded = await store.get_job("j1")
    assert loaded is not None
    assert loaded.status is JobStatus.QUEUED
    assert loaded.target_repo == "acme/web"

    job.status = JobStatus.COMPLETED
    job.summary = "opened PR #5"
    await store.upsert_job(job)
    assert (await store.get_job("j1")).status is JobStatus.COMPLETED

    assert [j.id for j in await store.list_jobs()] == ["j1"]


async def test_speaker_roundtrip_preserves_profile_and_permissions(store):
    speaker = Speaker(
        id="alex",
        profile=SpeakerProfile(
            display_name="Alex",
            calendar_account="alex@example.com",
            preferred_voice="en_US-amy",
            permissions=frozenset({"repos:deploy", "calendar"}),
        ),
    )
    await store.upsert_speaker(speaker)

    loaded = await store.get_speaker("alex")
    assert loaded is not None
    assert loaded.profile.display_name == "Alex"
    assert loaded.profile.calendar_account == "alex@example.com"
    assert loaded.profile.permissions == frozenset({"repos:deploy", "calendar"})
    assert [s.id for s in await store.list_speakers()] == ["alex"]


async def test_capability_roundtrip(store):
    await store.upsert_capability(Capability(name="web_search", description="search the web"))
    caps = await store.list_capabilities()
    assert [c.name for c in caps] == ["web_search"]
    assert caps[0].description == "search the web"


async def test_config_get_set_and_missing(store):
    assert await store.get_config("session.idle_timeout_s") is None
    await store.set_config("session.idle_timeout_s", "120")
    assert await store.get_config("session.idle_timeout_s") == "120"
    await store.set_config("session.idle_timeout_s", "300")
    assert await store.get_config("session.idle_timeout_s") == "300"


@pytest.mark.parametrize("missing", ["nope", "also-nope"])
async def test_missing_lookups_return_none(store, missing):
    assert await store.get_config(missing) is None
    assert await store.get_job(missing) is None
    assert await store.get_speaker(missing) is None
