"""Tests for the ClaudeCodeBrain adapter — against a mocked runner, no real CLI."""

import json
from datetime import datetime

import pytest

from jarvis.adapters.brain import (
    BillingMode,
    BrainError,
    ClaudeCodeBrain,
    EchoBrain,
)
from jarvis.domain.models import Request, Room, Session, Speaker, Utterance
from jarvis.ports import Brain
from jarvis.ports.brain import Budget


def _request(text="what's the weather?") -> Request:
    return Request(
        utterance=Utterance(text=text, area="kitchen"),
        room=Room(id="kitchen", area="kitchen"),
        speaker=Speaker.household(),
        trace_id="t-1",
    )


def _session(brain_session_id=None) -> Session:
    now = datetime(2026, 6, 26)
    return Session(
        id="s1",
        room_id="kitchen",
        speaker_id="household",
        created_at=now,
        last_active_at=now,
        brain_session_id=brain_session_id,
    )


class RecordingRunner:
    """A fake subprocess runner: records args/env and returns a canned result."""

    def __init__(self, *, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.args: list[str] = []
        self.env: dict[str, str] = {}

    async def __call__(self, args, env):
        self.args = list(args)
        self.env = dict(env)
        return self.returncode, self.stdout, self.stderr


def _ok_json(**overrides) -> str:
    payload = {
        "result": "It's sunny.",
        "session_id": "brain-123",
        "total_cost_usd": 0.0021,
        "usage": {"input_tokens": 12, "output_tokens": 8},
        "is_error": False,
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_satisfies_brain_port():
    assert isinstance(ClaudeCodeBrain(runner=RecordingRunner()), Brain)
    assert isinstance(EchoBrain(), Brain)


async def test_builds_expected_command():
    runner = RecordingRunner(stdout=_ok_json())
    brain = ClaudeCodeBrain(executable="claude", runner=runner, base_env={})
    await brain.invoke(
        _request(),
        _session(brain_session_id="prev-session"),
        tools=["calendar", "web_search"],
        model="fast",
        budget=Budget(max_turns=4),
    )
    assert runner.args == [
        "claude",
        "-p",
        "what's the weather?",
        "--output-format",
        "json",
        "--resume",
        "prev-session",
        "--model",
        "fast",
        "--allowedTools",
        "calendar,web_search",
        "--max-turns",
        "4",
    ]


async def test_parses_result_into_brain_result():
    runner = RecordingRunner(stdout=_ok_json())
    brain = ClaudeCodeBrain(runner=runner, base_env={})
    result = await brain.invoke(_request(), _session())
    assert result.text == "It's sunny."
    assert result.brain_session_id == "brain-123"
    assert result.cost == 0.0021
    assert result.usage is not None
    assert (result.usage.input_tokens, result.usage.output_tokens) == (12, 8)


async def test_subscription_mode_strips_api_key_from_env():
    runner = RecordingRunner(stdout=_ok_json())
    brain = ClaudeCodeBrain(
        runner=runner,
        billing_mode=BillingMode.SUBSCRIPTION,
        base_env={"ANTHROPIC_API_KEY": "sk-should-be-removed", "PATH": "/usr/bin"},
    )
    await brain.invoke(_request(), _session())
    assert "ANTHROPIC_API_KEY" not in runner.env
    assert runner.env["PATH"] == "/usr/bin"


async def test_api_key_mode_sets_the_key():
    runner = RecordingRunner(stdout=_ok_json())
    brain = ClaudeCodeBrain(
        runner=runner,
        billing_mode=BillingMode.API_KEY,
        api_key="sk-explicit",
        base_env={},
    )
    await brain.invoke(_request(), _session())
    assert runner.env["ANTHROPIC_API_KEY"] == "sk-explicit"


async def test_nonzero_exit_raises_brain_error():
    runner = RecordingRunner(returncode=1, stderr="rate limited")
    brain = ClaudeCodeBrain(runner=runner, base_env={})
    with pytest.raises(BrainError, match="rate limited"):
        await brain.invoke(_request(), _session())


async def test_is_error_payload_raises():
    runner = RecordingRunner(stdout=_ok_json(is_error=True, result="model overloaded"))
    brain = ClaudeCodeBrain(runner=runner, base_env={})
    with pytest.raises(BrainError, match="model overloaded"):
        await brain.invoke(_request(), _session())


async def test_echo_brain_echoes_request():
    brain = EchoBrain()
    result = await brain.invoke(_request("hello"), _session())
    assert result.text == "You said: hello"
    assert result.cost == 0.0
