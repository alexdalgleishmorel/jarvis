"""Tests for RoutingPolicy (README §5, §6)."""

from jarvis.domain.models import Request, Room, Route, Speaker, Utterance
from jarvis.domain.routing import SUGGESTED_ASYNC_TRIGGERS, RoutingPolicy


def _request(text: str) -> Request:
    return Request(
        utterance=Utterance(text=text, area="kitchen"),
        room=Room(id="kitchen", area="kitchen"),
        speaker=Speaker.household(),
        trace_id="t-1",
    )


def test_m1_default_routes_everything_to_quick_qa():
    policy = RoutingPolicy()  # no triggers configured
    # Even job-shaped text stays QUICK_QA until M2 enables triggers.
    decision = policy.classify(_request("open a PR to fix the build in the repo"))
    assert decision.route is Route.QUICK_QA


def test_async_trigger_matches_when_configured():
    policy = RoutingPolicy(async_triggers=["open a pr", "refactor"])
    decision = policy.classify(_request("Hey Jarvis, open a PR for the new endpoint"))
    assert decision.route is Route.ASYNC_JOB
    assert "open a pr" in decision.reason


def test_question_stays_quick_qa_with_triggers_configured():
    policy = RoutingPolicy(async_triggers=SUGGESTED_ASYNC_TRIGGERS)
    decision = policy.classify(_request("what's on my calendar tomorrow?"))
    assert decision.route is Route.QUICK_QA


def test_matching_is_case_insensitive():
    policy = RoutingPolicy(async_triggers=["Deploy"])
    decision = policy.classify(_request("please DEPLOY the staging service"))
    assert decision.route is Route.ASYNC_JOB
