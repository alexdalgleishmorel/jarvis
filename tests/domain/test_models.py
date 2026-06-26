"""Tests for the domain models — construction, immutability, and small behaviours."""

import dataclasses
from datetime import datetime, timedelta

import pytest

from jarvis.domain.models import (
    HOUSEHOLD_SPEAKER_ID,
    Capability,
    Job,
    JobStatus,
    Request,
    Response,
    Room,
    Route,
    RoutingDecision,
    Session,
    Speaker,
    SpeakerProfile,
    Utterance,
)


def test_value_objects_are_frozen():
    room = Room(id="kitchen", area="kitchen")
    with pytest.raises(dataclasses.FrozenInstanceError):
        room.id = "den"  # type: ignore[misc]


def test_household_speaker_is_unknown_and_permissive():
    speaker = Speaker.household()
    assert speaker.id == HOUSEHOLD_SPEAKER_ID
    assert speaker.is_known is False
    assert speaker.profile.allows("anything")


def test_known_speaker_permissions_are_scoped():
    profile = SpeakerProfile(display_name="Alex", permissions=frozenset({"repos:deploy"}))
    speaker = Speaker(id="alex", profile=profile)
    assert speaker.is_known is True
    assert speaker.profile.allows("repos:deploy")
    assert not speaker.profile.allows("repos:secret")


def test_request_exposes_utterance_text():
    utterance = Utterance(text="what's the weather?", area="kitchen", conversation_id="c1")
    request = Request(
        utterance=utterance,
        room=Room(id="kitchen", area="kitchen"),
        speaker=Speaker.household(),
        trace_id="t-1",
    )
    assert request.text == "what's the weather?"


def test_response_carries_cost_and_latency():
    response = Response(text="sunny", trace_id="t-1", cost=0.002, latency_ms=850.0)
    assert response.cost == 0.002
    assert response.latency_ms == 850.0


def test_routing_decision():
    decision = RoutingDecision(route=Route.ASYNC_JOB, reason="contains 'fix the'")
    assert decision.route is Route.ASYNC_JOB
    assert Route("quick_qa") is Route.QUICK_QA


def test_session_key_and_mutability():
    now = datetime(2026, 1, 1, 12, 0, 0)
    session = Session(
        id="s1",
        room_id="kitchen",
        speaker_id=HOUSEHOLD_SPEAKER_ID,
        created_at=now,
        last_active_at=now,
    )
    assert session.key == ("kitchen", HOUSEHOLD_SPEAKER_ID)
    # Entities are mutable.
    later = now + timedelta(minutes=2)
    session.last_active_at = later
    session.brain_session_id = "brain-123"
    assert session.last_active_at == later
    assert session.brain_session_id == "brain-123"


def test_job_defaults():
    job = Job(id="j1", trace_id="t-1", prompt="bump deps in repo X")
    assert job.status is JobStatus.QUEUED
    assert job.summary is None
    job.status = JobStatus.RUNNING
    assert job.status is JobStatus.RUNNING


def test_capability():
    cap = Capability(name="calendar", description="read the calendar")
    assert cap.required_permission is None
