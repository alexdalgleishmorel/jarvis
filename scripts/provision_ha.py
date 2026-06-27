#!/usr/bin/env python3
"""Provision Home Assistant config from code (lightweight IaC).

HA's integrations (Wyoming, ElevenLabs, our Jarvis agent) and Assist pipelines are
config-entry / UI things with no YAML or Terraform support. This applies the
desired state in ``config/ha-provision.json`` via HA's APIs instead — so we stop
clicking the UI while troubleshooting, and a fresh host (the Mac Mini) is one
command. Idempotent: existing integrations/pipeline are detected and skipped or
updated, never duplicated.

Two APIs are used because HA splits them: **REST** for config-entry flows,
**WebSocket** for the entity registry + Assist pipeline.

Needs ``JARVIS_HA_TOKEN`` (a long-lived HA token) in env/.env. Secrets like
``ELEVENLABS_API_KEY`` / ``ELEVENLABS_VOICE`` also come from env.

Usage:
    .venv/bin/python scripts/provision_ha.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

import httpx
import websockets

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "config" / "ha-provision.json"


def load_dotenv() -> None:
    env_path = REPO / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def substitute(obj: object) -> object:
    if isinstance(obj, str):
        return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), obj)
    if isinstance(obj, dict):
        return {k: substitute(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute(v) for v in obj]
    return obj


class HARest:
    def __init__(self, base: str, token: str) -> None:
        self._client = httpx.Client(
            base_url=base.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )

    def entries(self) -> list[dict]:
        r = self._client.get("/api/config/config_entries/entry")
        r.raise_for_status()
        return r.json()

    def flow_start(self, handler: str) -> dict:
        r = self._client.post(
            "/api/config/config_entries/flow",
            json={"handler": handler, "show_advanced_options": False},
        )
        r.raise_for_status()
        return r.json()

    def flow_configure(self, flow_id: str, user_input: dict) -> dict:
        r = self._client.post(f"/api/config/config_entries/flow/{flow_id}", json=user_input)
        r.raise_for_status()
        return r.json()

    def options_start(self, entry_id: str) -> dict:
        r = self._client.post(
            "/api/config/config_entries/options/flow", json={"handler": entry_id}
        )
        r.raise_for_status()
        return r.json()

    def options_configure(self, flow_id: str, user_input: dict) -> dict:
        r = self._client.post(
            f"/api/config/config_entries/options/flow/{flow_id}", json=user_input
        )
        r.raise_for_status()
        return r.json()


def drive_flow(start: dict, steps: dict, configure) -> str:
    """Walk a config/options flow to completion, submitting `steps[step_id]`."""
    result = start
    while True:
        kind = result.get("type")
        if kind == "create_entry":
            return "created"
        if kind == "abort":
            return f"abort:{result.get('reason')}"
        if kind == "form":
            step_id = result.get("step_id")
            if step_id not in steps:
                raise SystemExit(
                    f"    flow needs step '{step_id}' not in config; "
                    f"schema={result.get('data_schema')}"
                )
            result = configure(result["flow_id"], steps[step_id])
            continue
        raise SystemExit(f"    unexpected flow result type {kind!r}: {result}")


def ensure_integrations(ha: HARest, desired: dict, dry_run: bool) -> list[dict]:
    existing = ha.entries()
    have = {(e["domain"], e.get("title")) for e in existing}
    for item in desired["integrations"]:
        key = (item["domain"], item["title"])
        if key in have:
            print(f"  ok (exists): {item['domain']} / {item['title']}")
            continue
        if dry_run:
            print(f"  would create: {item['domain']} / {item['title']}")
            continue
        print(f"  creating: {item['domain']} / {item['title']}")
        status = drive_flow(ha.flow_start(item["domain"]), item.get("steps", {}), ha.flow_configure)
        print(f"    -> {status}")
        if item.get("options"):
            entry_id = next(
                e["entry_id"] for e in ha.entries() if (e["domain"], e.get("title")) == key
            )
            ostatus = drive_flow(ha.options_start(entry_id), item["options"], ha.options_configure)
            print(f"    options -> {ostatus}")
    return ha.entries()


# ──────────────────────────── WebSocket (pipeline) ────────────────────────────


class HAWs:
    def __init__(self, conn: websockets.WebSocketClientProtocol) -> None:
        self._conn = conn
        self._id = 0

    @classmethod
    async def connect(cls, base: str, token: str) -> HAWs:
        url = base.rstrip("/").replace("http", "ws", 1) + "/api/websocket"
        conn = await websockets.connect(url, max_size=None)
        await conn.recv()  # auth_required
        await conn.send(json.dumps({"type": "auth", "access_token": token}))
        if json.loads(await conn.recv()).get("type") != "auth_ok":
            raise SystemExit("WebSocket auth failed (check JARVIS_HA_TOKEN)")
        return cls(conn)

    async def cmd(self, payload: dict, *, soft: bool = False):
        self._id += 1
        msg_id = self._id
        await self._conn.send(json.dumps({**payload, "id": msg_id}))
        while True:
            msg = json.loads(await self._conn.recv())
            if msg.get("id") == msg_id and msg.get("type") == "result":
                if not msg.get("success"):
                    if soft:
                        return None
                    raise SystemExit(f"WS {payload['type']} failed: {msg.get('error')}")
                return msg.get("result")

    async def close(self) -> None:
        await self._conn.close()


def resolve_entity(entities: list[dict], entries: list[dict], spec: dict) -> str:
    entry_id = next(
        e["entry_id"]
        for e in entries
        if e["domain"] == spec["domain"] and e.get("title") == spec["title"]
    )
    return next(
        e["entity_id"]
        for e in entities
        if e.get("config_entry_id") == entry_id and e["entity_id"].startswith(spec["prefix"])
    )


async def ensure_pipeline(base: str, token: str, desired: dict, entries: list[dict], dry: bool):
    ws = await HAWs.connect(base, token)
    try:
        entities = await ws.cmd({"type": "config/entity_registry/list"})
        p = desired["pipeline"]
        fields = {
            "name": p["name"],
            "language": p["language"],
            "conversation_engine": resolve_entity(entities, entries, p["conversation_engine_from"]),
            "conversation_language": p["language"],
            "stt_engine": resolve_entity(entities, entries, p["stt_engine_from"]),
            "stt_language": p["language"],
            "tts_engine": resolve_entity(entities, entries, p["tts_engine_from"]),
            "tts_language": p["language"],
            "tts_voice": p.get("tts_voice") or None,
            "wake_word_entity": p.get("wake_word_entity"),
            "wake_word_id": p.get("wake_word_id"),
        }
        listing = await ws.cmd({"type": "assist_pipeline/pipeline/list"})
        pipelines = listing.get("pipelines", [])
        existing = next((x for x in pipelines if x["name"] == p["name"]), None)

        if dry:
            print(f"  pipeline '{p['name']}': would {'update' if existing else 'create'} -> "
                  f"conv={fields['conversation_engine']} stt={fields['stt_engine']} "
                  f"tts={fields['tts_engine']} voice={fields['tts_voice']}")
            return

        if existing:
            await ws.cmd({"type": "assist_pipeline/pipeline/update",
                          "pipeline_id": existing["id"], **fields})
            pid = existing["id"]
            print(f"  pipeline '{p['name']}': updated")
        else:
            created = await ws.cmd({"type": "assist_pipeline/pipeline/create", **fields})
            pid = created["id"]
            print(f"  pipeline '{p['name']}': created")

        if p.get("preferred"):
            res = await ws.cmd(
                {"type": "assist_pipeline/pipeline/set_preferred", "pipeline_id": pid}, soft=True
            )
            print("  set preferred" if res is not None else
                  "  (could not set preferred via API — set the star in the UI once)")
    finally:
        await ws.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision Home Assistant from config/ha-provision.json")
    parser.add_argument("--dry-run", action="store_true", help="show what would change, make no changes")
    args = parser.parse_args()

    load_dotenv()
    token = os.environ.get("JARVIS_HA_TOKEN")
    if not token:
        sys.exit("JARVIS_HA_TOKEN is not set (add a long-lived HA token to .env)")

    desired = substitute(json.loads(CONFIG.read_text()))
    base = os.environ.get("JARVIS_HA_URL") or desired.get("ha_url") or "http://localhost:8123"
    print(f"Provisioning {base} ({'dry-run' if args.dry_run else 'apply'})")

    ha = HARest(base, token)
    entries = ensure_integrations(ha, desired, args.dry_run)
    asyncio.run(ensure_pipeline(base, token, desired, entries, args.dry_run))
    print("Done.")


if __name__ == "__main__":
    main()
