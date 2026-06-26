"""Tests for the HA REST hub adapter — against an httpx mock transport."""

import json

import httpx
import pytest

from jarvis.adapters.ha import HaRestHub
from jarvis.ports import HomeAssistant

STATES = [
    {"entity_id": "light.kitchen", "state": "on", "attributes": {"brightness": 200}},
    {"entity_id": "light.den", "state": "off", "attributes": {}},
    {"entity_id": "sensor.kitchen_temp", "state": "21", "attributes": {}},
]
ENTITY_AREAS = [
    {"e": "light.kitchen", "a": "kitchen"},
    {"e": "light.den", "a": "den"},
    {"e": "sensor.kitchen_temp", "a": "kitchen"},
]


class Recorder:
    def __init__(self):
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/api/states":
            return httpx.Response(200, json=STATES)
        if path == "/api/template":
            template = json.loads(request.content)["template"]
            if "areas()" in template:
                return httpx.Response(200, text=json.dumps([{"id": "kitchen", "name": "Kitchen"}]))
            return httpx.Response(200, text=json.dumps(ENTITY_AREAS))
        if path.startswith("/api/services/"):
            return httpx.Response(200, json=[])
        return httpx.Response(404)


def _hub(recorder: Recorder, *, token="tok") -> HaRestHub:
    return HaRestHub(
        base_url="http://hub.local:8123",
        token=token,
        transport=httpx.MockTransport(recorder.handler),
    )


async def test_satisfies_port():
    assert isinstance(_hub(Recorder()), HomeAssistant)


async def test_call_service_posts_merged_body_with_auth():
    rec = Recorder()
    hub = _hub(rec, token="secret")
    await hub.call_service(
        "light", "turn_on", data={"brightness": 255}, target={"entity_id": "light.kitchen"}
    )
    await hub.aclose()

    req = rec.requests[-1]
    assert req.method == "POST"
    assert req.url.path == "/api/services/light/turn_on"
    assert req.headers["authorization"] == "Bearer secret"
    assert json.loads(req.content) == {"brightness": 255, "entity_id": "light.kitchen"}


async def test_get_areas_parses_template():
    hub = _hub(Recorder())
    areas = await hub.get_areas()
    await hub.aclose()
    assert [(a.id, a.name) for a in areas] == [("kitchen", "Kitchen")]


async def test_list_entities_filters_by_domain():
    hub = _hub(Recorder())
    lights = await hub.list_entities(domain="light")
    await hub.aclose()
    assert {e.entity_id for e in lights} == {"light.kitchen", "light.den"}
    assert next(e for e in lights if e.entity_id == "light.kitchen").state == "on"


async def test_list_entities_filters_by_area_via_template():
    hub = _hub(Recorder())
    kitchen = await hub.list_entities(area="kitchen")
    await hub.aclose()
    assert {e.entity_id for e in kitchen} == {"light.kitchen", "sensor.kitchen_temp"}
    assert all(e.area_id == "kitchen" for e in kitchen)


async def test_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    hub = HaRestHub(token="bad", transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        await hub.call_service("light", "turn_on")
    await hub.aclose()
