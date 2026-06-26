# Jarvis — Home Assistant conversation agent

A Home Assistant **custom component** that registers a conversation agent which
forwards each Assist turn to the Jarvis **conductor** (`/ingress/utterance`) and
speaks the reply. This is the bridge between HA's Assist pipeline and the
conductor (README §4–6).

> HA-runtime code (imports `homeassistant`), so it lives outside the conductor's
> Python package and CI gate. It's verified on the box.

## Install

**With docker-compose (recommended):** it's already mounted into the HA
container at `/config/custom_components/jarvis` — just restart HA.

**Manual:** copy `custom_components/jarvis/` into your HA `config/custom_components/`
directory and restart Home Assistant.

## Configure

1. **Settings → Devices & Services → Add Integration → "Jarvis Conductor".**
2. Enter the conductor URL (default `http://conductor:8000` inside compose; use
   `http://<host>:8000` otherwise) and an optional default area.
3. **Settings → Voice assistants →** your assistant **→ Conversation agent →
   "Jarvis".** Set STT to faster-whisper and TTS to Piper.

## How it works

Each turn HA sends `{text, area, conversation_id}` to the conductor; `area` is
resolved from the calling device's HA area (falling back to the default). The
conductor's reply text is spoken by HA's pipeline (Piper) — which is why the
conductor runs with `JARVIS_TTS_MODE=null` in this path (no double speech).

If the conductor is unreachable, the agent speaks a graceful error instead of
breaking the pipeline.
