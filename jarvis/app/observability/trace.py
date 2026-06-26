"""Trace ids — one per utterance, threaded through every event (README §13)."""

from __future__ import annotations

from uuid import uuid4

__all__ = ["new_trace_id"]


def new_trace_id() -> str:
    return uuid4().hex
