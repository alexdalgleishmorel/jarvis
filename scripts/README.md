# scripts — on-box test helpers

Diagnostic tools run by hand on the host. They are **not** part of the conductor
package or CI (they need a logged-in `claude`, a mic, and optional heavy deps).

| Script | Issue | What it does |
|--------|-------|---------------|
| `check_brain_billing.sh` | #18 | Whether headless `claude -p` draws from the subscription, and whether its JSON matches `ClaudeCodeBrain`. |
| `wakeword_test.py` | #19 | `hey_jarvis` true-accept / false-accept rate from the mic, with a tunable threshold. |
| `provision_ha.py` | #67 | Apply `config/ha-provision.json` to Home Assistant via its API (integrations + Assist pipeline) — IaC, idempotent. Stops UI clicking; one-command Mac Mini setup. |

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
