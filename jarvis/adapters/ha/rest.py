"""Home Assistant REST adapter — the hub (README §3.4, §5).

The hub owns devices; this is the only path to them. We read areas/entities and
call services over HA's REST API; we never keep a competing device registry.

Areas and an entity's area aren't in ``/api/states``, so they're resolved through
the template endpoint (``areas()`` / ``area_id(entity)``). Base URL and token are
config, not constants. The httpx client/transport is injectable so the adapter is
testable against a mock; the real round-trip is a smoke test on the box (§5).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from jarvis.ports.home_assistant import Area, Entity

__all__ = ["HaRestHub"]

_AREAS_TEMPLATE = (
    "[{% for a in areas() %}"
    '{"id": {{ a | tojson }}, "name": {{ area_name(a) | tojson }}}'
    "{% if not loop.last %},{% endif %}"
    "{% endfor %}]"
)

_ENTITY_AREA_TEMPLATE = (
    "{% set ns = namespace(items=[]) %}"
    "{% for s in states %}"
    '{% set ns.items = ns.items + [{"e": s.entity_id, "a": area_id(s.entity_id)}] %}'
    "{% endfor %}{{ ns.items | tojson }}"
)


class HaRestHub:
    def __init__(
        self,
        base_url: str = "http://homeassistant.local:8123",
        token: str = "",
        *,
        client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = httpx.AsyncClient(
                base_url=base_url.rstrip("/"),
                headers={"Authorization": f"Bearer {token}"},
                timeout=timeout,
                transport=transport,
            )
            self._owns_client = True

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def call_service(
        self,
        domain: str,
        service: str,
        *,
        data: Mapping[str, Any] | None = None,
        target: Mapping[str, Any] | None = None,
    ) -> None:
        body = {**(data or {}), **(target or {})}
        resp = await self._client.post(f"/api/services/{domain}/{service}", json=body)
        resp.raise_for_status()

    async def get_areas(self) -> Sequence[Area]:
        rendered = await self._render(_AREAS_TEMPLATE)
        return [Area(id=item["id"], name=item["name"]) for item in json.loads(rendered)]

    async def list_entities(
        self, *, area: str | None = None, domain: str | None = None
    ) -> Sequence[Entity]:
        resp = await self._client.get("/api/states")
        resp.raise_for_status()
        entities = [
            Entity(
                entity_id=state["entity_id"],
                state=state.get("state"),
                attributes=state.get("attributes") or {},
            )
            for state in resp.json()
        ]
        if domain is not None:
            entities = [e for e in entities if e.entity_id.split(".", 1)[0] == domain]
        if area is not None:
            area_map = await self._entity_area_map()
            entities = [
                Entity(
                    entity_id=e.entity_id,
                    state=e.state,
                    attributes=e.attributes,
                    area_id=area_map.get(e.entity_id),
                )
                for e in entities
            ]
            entities = [e for e in entities if e.area_id == area]
        return entities

    async def _entity_area_map(self) -> dict[str, str | None]:
        rendered = await self._render(_ENTITY_AREA_TEMPLATE)
        return {item["e"]: item["a"] for item in json.loads(rendered)}

    async def _render(self, template: str) -> str:
        resp = await self._client.post("/api/template", json={"template": template})
        resp.raise_for_status()
        return resp.text
