# native/whisper — Apple-Silicon STT (MLX-Whisper over Wyoming)

The transcriber, run **natively on macOS** so Whisper uses the Apple Silicon GPU
via [MLX](https://github.com/ml-explore/mlx) — far faster and more accurate than
the CPU-only Docker Whisper. Home Assistant's Assist pipeline reaches it over the
Wyoming protocol at `host.docker.internal:10301` (HA runs in Docker; this runs on
the host, which Docker can't accelerate).

> Host-run code with Apple-only deps (`mlx-whisper`), so it's outside the
> conductor's package and CI gate.

## Install (LaunchAgent, runs at login + restarts on crash)

```bash
native/whisper/install.sh            # default model: whisper-medium.en
# or pick a model:
native/whisper/install.sh mlx-community/whisper-small.en-mlx
```

macOS TCC blocks launchd from running files under `~/Desktop`, so `install.sh`
deploys the runtime to `~/Library/Application Support/jarvis-whisper` and writes a
LaunchAgent pointing there (the repo stays the source of truth).

- Logs: `/tmp/jarvis-whisper.log`
- Manage: `launchctl bootout gui/$(id -u)/com.jarvis.whisper` /
  `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jarvis.whisper.plist`
- Dev (foreground, from the repo): `native/whisper/run.sh --debug`

## Model dial (benchmarked on a base M1, fixed ~per-utterance cost)

| Model | Latency | Notes |
|-------|---------|-------|
| `whisper-small.en-mlx`        | ~0.6s | snappiest; great on clear speech |
| `whisper-medium.en-mlx` (default) | ~2s | best accuracy/latency balance for English |
| `whisper-large-v3-turbo`      | ~3s | multilingual, most robust on hard speech |

English-only (`.en`) models are faster *and* more accurate on English than the
multilingual ones at the same size. Latency is roughly fixed per utterance
(Whisper processes a 30s window), so it doesn't grow much with clip length.

## Point Home Assistant at it

1. HA → Settings → Devices & Services → **Add Integration → Wyoming Protocol** →
   host `host.docker.internal`, port `10301`. This adds a new STT entity.
2. Settings → **Voice assistants → Jarvis → Speech-to-text →** the new
   MLX-Whisper entity → Save.
3. You can then stop the Docker transcriber: `docker compose stop wyoming-whisper`.
