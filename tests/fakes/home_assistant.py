"""In-memory fake for the ``HomeAssistant`` (hub) port.

Configurable areas/entities, and records every ``call_service`` so tests can
assert device commands without a real hub.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from jarvis.ports.home_assistant import Area, Entity


@dataclass
class ServiceCall:
    domain: str
    service: str
    data: dict[str, Any]
    target: dict[str, Any]


class FakeHomeAssistant:
    def __init__(
        self,
        *,
        areas: Sequence[Area] | None = None,
        entities: Sequence[Entity] | None = None,
    ) -> None:
        self._areas = list(areas) if areas is not None else [Area(id="kitchen", name="Kitchen")]
        self._entities = list(entities) if entities is not None else []
        self.service_calls: list[ServiceCall] = []

    async def get_areas(self) -> Sequence[Area]:
        return list(self._areas)

    async def list_entities(
        self, *, area: str | None = None, domain: str | None = None
    ) -> Sequence[Entity]:
        result = self._entities
        if area is not None:
            result = [e for e in result if e.area_id == area]
        if domain is not None:
            result = [e for e in result if e.entity_id.split(".", 1)[0] == domain]
        return list(result)

    async def call_service(
        self,
        domain: str,
        service: str,
        *,
        data: Mapping[str, Any] | None = None,
        target: Mapping[str, Any] | None = None,
    ) -> None:
        self.service_calls.append(
            ServiceCall(domain, service, dict(data or {}), dict(target or {}))
        )
