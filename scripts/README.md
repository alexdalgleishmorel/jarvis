# scripts — on-box test helpers

Diagnostic tools run by hand on the host. They are **not** part of the conductor
package or CI (they need a logged-in `claude`, a mic, and optional heavy deps).

| Script | Issue | What it does |
|--------|-------|---------------|
| `check_brain_billing.sh` | #18 | Whether headless `claude -p` draws from the subscription, and whether its JSON matches `ClaudeCodeBrain`. |
| `wakeword_mic_test.py` | #19 | Stream your mic to the `wyoming-porcupine` service and print each "jarvis" detection — validate the wake word with your own voice (no satellite). |
| `provision_ha.py` | #67 | Apply `config/ha-provision.json` to Home Assistant via its API (integrations + Assist pipeline) — IaC, idempotent. Stops UI clicking; one-command Mac Mini setup. |

## Wake-word mic test (wakeword_mic_test.py)

Validate that the "jarvis" wake word fires on *your* voice, before buying a
satellite. It streams the mic to the running `wyoming-porcupine` service (the same
one HA uses).

```bash
python3 -m venv scripts/.venv
scripts/.venv/bin/pip install wyoming sounddevice
# stack must be up (Porcupine on localhost:10400):
scripts/.venv/bin/python scripts/wakeword_mic_test.py
```

Say "jarvis" a few times (each prints a detection); talk/play TV to check for
false-accepts; Ctrl-C for a summary. High false-accepts? Lower `--sensitivity` on
the `wyoming-porcupine` service in `docker-compose.yml`. (Use `--file some.wav` to
test without a mic.)

## Provisioning Home Assistant (provision_ha.py)

HA integrations and Assist pipelines are config-entry/UI things with no YAML or
Terraform support, so this applies the desired state in
[`config/ha-provision.json`](../config/ha-provision.json) via HA's REST (config-entry
flows) + WebSocket (pipeline) APIs. Idempotent — existing items are detected and
skipped/updated, never duplicated.

```bash
# Needs a long-lived HA token in .env as JARVIS_HA_TOKEN (Profile > Security).
# Secrets (ELEVENLABS_API_KEY, optional ELEVENLABS_VOICE) also from env.
.venv/bin/python scripts/provision_ha.py --dry-run   # preview
.venv/bin/python scripts/provision_ha.py             # apply
```

See `docs/laptop-e2e.md` for how these fit into the full e2e.
