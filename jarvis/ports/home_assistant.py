"""The ``HomeAssistant`` port — the hub (README §3.4, §5).

The hub owns devices; this is the *only* path to them. We read and command
entities and read areas; we never maintain a competing device registry.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

__all__ = ["Area", "Entity", "HomeAssistant"]


@dataclass(frozen=True, slots=True)
class Area:
    """A Home Assistant area (≈ a room)."""

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class Entity:
    """A Home Assistant entity (a light, speaker, sensor, …)."""

    entity_id: str
    state: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)
    area_id: str | None = None


@runtime_checkable
class HomeAssistant(Protocol):
    async def get_areas(self) -> Sequence[Area]: ...

    async def list_entities(
        self, *, area: str | None = None, domain: str | None = None
    ) -> Sequence[Entity]: ...

    async def call_service(
        self,
        domain: str,
        service: str,
        *,
        data: Mapping[str, Any] | None = None,
        target: Mapping[str, Any] | None = None,
    ) -> None: ...
