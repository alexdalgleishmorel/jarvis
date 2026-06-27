# Laptop end-to-end runbook

> For the always-on house deployment (dedicated Mac Mini), see
> [`deploy-mac-mini.md`](./deploy-mac-mini.md). This runbook is for dev/testing on
> your laptop; the production steps mirror it.

Goal: a full voice round-trip on your laptop — **say something → Jarvis answers out
loud** — using the laptop as both mic and speaker. Two tiers:

- **Tier 1 (do first):** Home Assistant **browser Assist** (click-to-talk). Exercises
  STT → conductor → brain → TTS through your laptop speakers. Skips the wake word.
- **Tier 2:** a native **Wyoming satellite** for the "jarvis" wake word.

> **macOS caveat:** Docker Desktop on macOS has no host-audio access, so the *mic*
> can't live in a container. Browser Assist (Tier 1) sidesteps this; the Tier-2
> satellite runs natively on the Mac, not in Docker.

---

## 1. Bring up the stack (echo brain — no tokens)

```bash
cp .env.example .env          # JARVIS_HA_TOKEN can stay blank for now
docker compose up -d --build  # conductor + Home Assistant + Wyoming (whisper/piper/porcupine)
docker compose ps             # all healthy?
curl -s localhost:8000/healthz   # {"status":"ok"}
```

The conductor defaults to `JARVIS_BRAIN_MODE=echo` (tokenless) and
`JARVIS_TTS_MODE=null` (HA's pipeline speaks the reply).

## 2. Configure Home Assistant

Open `http://localhost:8123`, finish onboarding, then:

1. **Wyoming services** — Settings → Devices & Services → **Add Integration → Wyoming
   Protocol**, once each:
   - `wyoming-whisper` : `10300`  (speech-to-text)
   - `wyoming-piper`   : `10200`  (text-to-speech)
   - `wyoming-porcupine` : `10400`  (wake word — "jarvis")
2. **Jarvis agent** — Add Integration → **"Jarvis Conductor"** → URL `http://conductor:8000`.
3. **Assistant** — Settings → **Voice assistants** → (create/edit one):
   - Conversation agent → **Jarvis**
   - Speech-to-text → faster-whisper · Text-to-speech → Piper
   - Wake word (optional, Tier 2) → **jarvis**

## 3. Tier-1 e2e (echo brain)

Click the **Assist** icon (top of the HA sidebar) → microphone → say *"is this thing on?"*.
Expect it spoken back: **"You said: is this thing on?"** That's the full chain
(STT → conductor → voice) minus the real brain and wake word.

---

## 3b. Natural voice — ElevenLabs (optional, cloud)

Piper is local and fast but synthetic. For a natural, Claude-grade voice, swap the
hub's TTS engine to **ElevenLabs**. This is a Home Assistant change only — the
conductor is untouched (it runs `TTS_MODE=null`; HA speaks the reply).

> **Local-first opt-out (README §3.8):** with a cloud voice, the *response text*
> leaves your network (to ElevenLabs). The audio path (your speech) stays local.

1. **Get a key** — sign up at elevenlabs.io → Profile → **API Keys** → create one
   (free tier available). **Enter it in Home Assistant only — never commit it.**
2. **Add the integration** — HA → Settings → Devices & Services → **Add Integration
   → "ElevenLabs"** → paste the API key →
   - **Model:** `eleven_flash_v2_5` or `eleven_turbo_v2_5` for low latency (best for
     an assistant); `eleven_multilingual_v2` for max quality (slower).
   - **Voice:** pick from the list (browse/preview voices at elevenlabs.io; you can
     tune stability/similarity in the integration's *Configure* options later).
3. **Use it** — Settings → **Voice assistants → Jarvis → Text-to-speech → ElevenLabs**
   → choose the voice → **Save**.
4. **Test** — Assist → 🎤 → the reply is now spoken in the ElevenLabs voice.

Latency note (README §15): cloud TTS adds round-trip time; the flash/turbo models
keep it low. If a room feels sluggish, prefer those over `multilingual_v2`.

## 3c. Faster, accurate STT — native Apple-Silicon Whisper (recommended)

The Docker transcriber runs Whisper on CPU (slow + inaccurate). On Apple Silicon,
run it **natively** so it uses the GPU via MLX — ~2s and accurate on a base M1,
fully local. See `native/whisper/README.md`:

```bash
native/whisper/install.sh     # installs a launchd service on :10301
```

Then HA → Add Integration → **Wyoming Protocol** → `host.docker.internal` : `10301`
→ set the **Jarvis** assistant's Speech-to-text to the new MLX-Whisper entity →
`docker compose stop wyoming-whisper` to retire the CPU one.

## 4. Box task #18 — validate subscription billing (gates the real brain)

Do this **on the laptop, outside Docker** (the conductor image has no `claude` CLI):

```bash
echo "$ANTHROPIC_API_KEY"     # must be EMPTY. If set, unset it (it would bill the API account)
claude login                  # subscription OAuth
claude -p "say hello in five words" --output-format json   # note total_cost_usd, that it succeeds
```

Then confirm the headless call drew from the **subscription**, not per-token API:
- run `claude` interactively and check `/status` (plan + usage window), and
- check the Anthropic usage dashboard for this host.

Watch it over several calls. **If it draws from the subscription → proceed.** If it
bills the API, the *only* thing to change is the brain adapter (`billing_mode`); stay
on echo and tell me.

## 5. Switch on the real brain

Easiest path that has `claude` logged in: run the **conductor natively** (HA + Wyoming
stay in Docker):

```bash
docker compose stop conductor          # free the port
JARVIS_BRAIN_MODE=claude \
JARVIS_TTS_MODE=null \
  .venv/bin/uvicorn jarvis.app.main:create_app --factory --host 0.0.0.0 --port 8000
```

In HA, change the **Jarvis Conductor** integration URL to `http://host.docker.internal:8000`
(so the HA container reaches the conductor on the host). Now Assist answers real
questions ("what's on my calendar tomorrow?" once MCP tools are added).

> Running the real brain *inside* Docker instead needs the `claude` CLI + an OAuth
> token (`claude setup-token`) baked/mounted into the image — a later hardening step.

## 6. Tier-2 — wake word ("jarvis")

The wake word is **"jarvis"**, served by the `wyoming-porcupine` service (a built-in
Porcupine keyword; openWakeWord only offers "hey jarvis"). Porcupine v1 has no arm64
build, so on Apple Silicon it runs under x86 emulation (`platform: linux/amd64`).

The wake word only fires from a **continuously-listening satellite** — browser Assist
is click-to-talk, so it never exercises the wake word. For a real "jarvis → …" loop you
need a satellite streaming audio to the hub:

- **Hardware (recommended):** an ESP32-S3 "Atom Echo" (~$13) or the Home Assistant
  **Voice PE** (~$59), flashed with the HA voice-assistant firmware → point at the hub,
  set its wake word to "jarvis".
- **Raspberry Pi:** run [wyoming-satellite](https://github.com/rhasspy/wyoming-satellite)
  on a Pi with a mic/speaker, pointed at the hub.

> A Mac is a poor satellite: `wyoming-satellite` expects Linux ALSA audio, so use
> hardware (or a Pi) for the voice-activation test. You *can* validate the wake-word
> *detection* itself on the Mac without a satellite (see "Testing" below).

If "jarvis" gives too many false triggers (a short word is harder than "hey jarvis"),
lower `--sensitivity` on the `wyoming-porcupine` service in `docker-compose.yml`.

---

## Troubleshooting

- **Assist says it can't reach Jarvis** → check the integration URL and `curl
  localhost:8000/healthz`; container-to-container uses `http://conductor:8000`,
  host-to-container uses `http://host.docker.internal:8000`.
- **No audio in the browser** → grant the browser mic permission; check the HA
  assistant's TTS engine is Piper.
- **Conductor won't start** → if it exits complaining about `ANTHROPIC_API_KEY`, unset
  it (subscription billing guard, README §8).
