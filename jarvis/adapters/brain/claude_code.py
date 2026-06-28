"""ClaudeCodeBrain — the brain's current adapter (README §3.3, §5, §8).

Shells ``claude -p ... --output-format json`` and parses the result into a
``BrainResult``. This is the *only* place that knows how Claude is reached; the
rest of the system sees just the ``Brain`` port.

Billing (README §8) is owned here and nowhere else:

* **Billing mode is a config flag** — subscription-OAuth (default) vs API key —
  so a future policy change needs no system-wide rewrite.
* In subscription mode we **strip ``ANTHROPIC_API_KEY`` from the subprocess
  environment**, so a key leaking in from a shell profile / ``.env`` / container
  can't silently switch billing to the per-token API account.

The subprocess is run through an injected ``runner`` so the adapter is fully
testable without a real CLI or any token spend; the real round-trip is exercised
on the box once the §8 billing spike (#18) confirms which pool headless draws
from.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable, Mapping, Sequence
from enum import Enum

from jarvis.domain.models import Request, Session
from jarvis.ports.brain import BrainError, BrainRateLimited, BrainResult, Budget, Usage

__all__ = ["BillingMode", "BrainError", "BrainRateLimited", "ClaudeCodeBrain"]

# (returncode, stdout, stderr)
Runner = Callable[[Sequence[str], Mapping[str, str]], Awaitable[tuple[int, str, str]]]

# Substrings that mark a rate/usage limit rather than a generic failure.
_RATE_LIMIT_HINTS = ("rate limit", "rate_limit", "429", "overloaded", "usage limit", "quota")


def _is_rate_limit(text: str) -> bool:
    low = text.lower()
    return any(hint in low for hint in _RATE_LIMIT_HINTS)


class BillingMode(Enum):
    SUBSCRIPTION = "subscription"
    API_KEY = "api_key"


async def _subprocess_runner(args: Sequence[str], env: Mapping[str, str]) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=dict(env),
    )
    out, err = await proc.communicate()
    return proc.returncode or 0, out.decode(), err.decode()


class ClaudeCodeBrain:
    def __init__(
        self,
        *,
        executable: str = "claude",
        billing_mode: BillingMode = BillingMode.SUBSCRIPTION,
        api_key: str | None = None,
        default_model: str | None = None,
        base_env: Mapping[str, str] | None = None,
        runner: Runner | None = None,
    ) -> None:
        self._executable = executable
        self._billing_mode = billing_mode
        self._api_key = api_key
        self._default_model = default_model
        self._base_env = dict(base_env if base_env is not None else os.environ)
        self._runner = runner or _subprocess_runner

    def _env(self) -> dict[str, str]:
        env = dict(self._base_env)
        if self._billing_mode is BillingMode.SUBSCRIPTION:
            # Never let a stray key bill the API account instead of the
            # subscription (README §8, §13).
            env.pop("ANTHROPIC_API_KEY", None)
        elif self._billing_mode is BillingMode.API_KEY and self._api_key:
            env["ANTHROPIC_API_KEY"] = self._api_key
        return env

    def _build_args(
        self,
        request: Request,
        session: Session,
        tools: Sequence[str] | None,
        model: str | None,
        budget: Budget | None,
    ) -> list[str]:
        args = [self._executable, "-p", request.text, "--output-format", "json"]
        if session.brain_session_id:
            args += ["--resume", session.brain_session_id]
        chosen_model = model or self._default_model
        if chosen_model:
            args += ["--model", chosen_model]
        if tools:
            args += ["--allowedTools", ",".join(tools)]
        if budget and budget.max_turns is not None:
            args += ["--max-turns", str(budget.max_turns)]
        return args

    async def invoke(
        self,
        request: Request,
        session: Session,
        *,
        tools: Sequence[str] | None = None,
        model: str | None = None,
        budget: Budget | None = None,
    ) -> BrainResult:
        args = self._build_args(request, session, tools, model, budget)
        returncode, stdout, stderr = await self._runner(args, self._env())
        if returncode != 0:
            message = f"claude exited {returncode}: {stderr.strip()}"
            if _is_rate_limit(stderr) or _is_rate_limit(stdout):
                raise BrainRateLimited(message)
            raise BrainError(message)
        return _parse_result(stdout)


def _parse_result(stdout: str) -> BrainResult:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise BrainError(f"could not parse brain output: {exc}") from exc

    if data.get("is_error"):
        message = str(data.get("result") or "brain reported is_error")
        status = str(data.get("api_error_status") or "")
        if _is_rate_limit(message) or _is_rate_limit(status):
            raise BrainRateLimited(message)
        raise BrainError(message)

    usage_raw = data.get("usage") or {}
    usage = Usage(
        input_tokens=int(usage_raw.get("input_tokens", 0)),
        output_tokens=int(usage_raw.get("output_tokens", 0)),
    )
    return BrainResult(
        text=str(data.get("result", "")),
        brain_session_id=data.get("session_id"),
        cost=data.get("total_cost_usd"),
        usage=usage,
        tool_activity=(),
    )
