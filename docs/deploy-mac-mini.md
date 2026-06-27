# Production deployment — Mac Mini (Apple Silicon)

The always-on host. A Mac Mini runs the **whole stack as-is**, including the fast
**local** MLX-Whisper STT, at ~7W idle and silent. Your laptop stays the dev
machine; the Mini is the "brain box" — it can live in a closet, because the
per-room mics/speakers are separate satellites that stream to it over the LAN.

What runs where:

| Component | Where | Notes |
|-----------|-------|-------|
| hub (Home Assistant) | Docker on the Mini | the conversation pipeline |
| listener (openWakeWord) | Docker on the Mini | "hey jarvis" |
| transcriber (STT) | **native** on the Mini | MLX-Whisper on the GPU (`native/whisper`) |
| voice (TTS) | ElevenLabs (cloud) | selected in HA; no local service needed |
| conductor | Docker on the Mini | this repo |
| brain | Anthropic cloud | `claude` CLI is a thin client |
| satellites (mic/speaker) | per room | cheap devices pointing at the Mini |

## 0. Hardware

- Any Apple Silicon Mac Mini (M1/M2/M4). **16 GB RAM recommended** — 8 GB is tight
  once Docker (HA + conductor) and the MLX model share memory.
- Wired Ethernet preferred for a always-on hub.

## 1. macOS server prep (headless)

Do these once (via a monitor or Screen Sharing), then you can run it headless.

```bash
# Remote management
sudo systemsetup -setremotelogin on                 # SSH
# (Screen Sharing: System Settings > General > Sharing > Screen Sharing)

# Never sleep + recover from power loss (the whole point of an always-on host)
sudo pmset -a sleep 0 disksleep 0 womp 1 autorestart 1
```

- **Auto-login:** System Settings → Users & Groups → *Automatically log in as* your
  user. This is required so the GUI user session (and the STT **LaunchAgent**)
  start at boot. Note: auto-login needs **FileVault off** (or the disk won't
  unlock unattended). Decide per your security needs.

## 2. Docker runtime

Docker Desktop is GUI-oriented; for a headless server **colima** is cleaner:

```bash
brew install colima docker docker-compose
colima start --cpu 4 --memory 6 --disk 60
brew services start colima        # autostart on boot
```

(Or use Docker Desktop with "Start Docker Desktop when you log in" + auto-login.)

## 3. Bring up the stack

```bash
git clone https://github.com/alexdalgleishmorel/jarvis.git
cd jarvis
cp .env.example .env               # set JARVIS_HA_TOKEN later (after HA onboarding)
docker compose up -d
# Using ElevenLabs (cloud TTS) + native MLX STT? Retire the local voice services:
docker compose stop wyoming-piper wyoming-whisper
```

## 4. Native STT (local, GPU)

```bash
native/whisper/install.sh          # LaunchAgent on :10301 (auto-login => starts at boot)
```

Then point HA at it: Add Integration → **Wyoming Protocol** → `host.docker.internal`
: `10301` → set the Jarvis assistant's Speech-to-text to MLX-Whisper. (See
`native/whisper/README.md` for the model dial.)

> For a truly login-free boot you can convert the LaunchAgent to a LaunchDaemon;
> auto-login + LaunchAgent is simpler and what `install.sh` sets up.

## 5. The brain (after the §8 billing check, #18)

On the Mini: authenticate Claude via the **subscription**, and keep
`ANTHROPIC_API_KEY` **unset** (README §8). For a headless box, the §8 guidance is a
portable token (`claude setup-token`) supplied to the brain adapter as a secret;
validate which pool headless draws from with `scripts/check_brain_billing.sh`
first. Then set `JARVIS_BRAIN_MODE=claude` (the conductor needs the `claude` CLI
available — run it natively, or add the CLI + token to the conductor image). Until
then it runs the tokenless echo brain.

## 6. Configure Home Assistant

Same as `docs/laptop-e2e.md` §2–3 (Wyoming services, the "Jarvis Conductor"
agent, ElevenLabs TTS, MLX STT, `hey_jarvis` wake word) — just done once on the
Mini. Generate the HA long-lived token and put it in `.env` as `JARVIS_HA_TOKEN`.

## 7. Per-room satellites

The Mini doesn't need to be near you. Each room gets a cheap satellite that
streams audio to the hub and plays replies — e.g. an ESP32-S3 "Atom Echo", the
Home Assistant **Voice PE** puck, or a Raspberry Pi running `wyoming-satellite`.
Point them at the Mini's IP; set their wake word to `hey_jarvis`.

## 8. Operate / update

```bash
cd jarvis && git pull
docker compose up -d --build       # update hub-side services + conductor
native/whisper/install.sh          # update the STT service
```

Logs: `docker compose logs -f conductor` · `/tmp/jarvis-whisper.log` (STT).
