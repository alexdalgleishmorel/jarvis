# CLAUDE.md — working in the Jarvis conductor

This is the day-to-day guide for Claude Code (and humans) working in this repo.
**The full project spec — vision, architecture, component contracts — lives in
[`README.md`](./README.md). Read it fully before making changes.** When a
decision isn't covered, prefer the design principles (README §3) over ad-hoc
choices, and update `README.md` when you establish a new pattern.

## What this repo is

The **conductor**: a Python modular monolith that coordinates a whole-home voice
assistant. It receives transcribed utterances from the hub (Home Assistant),
routes them, asks the **brain** (Claude Code, behind the `Brain` port), and
speaks replies back to the originating room.

## Layout (README §5, §11)

| Path | Role | May import |
|------|------|------------|
| `jarvis/domain/`   | Pure core: models, sessions, routing | **nothing external** |
| `jarvis/ports/`    | Interfaces (Protocol/ABC)             | `jarvis.domain` only |
| `jarvis/adapters/` | Port implementations                  | its port + libs; **never another adapter** |
| `jarvis/services/` | Use-cases (`handle_utterance`, `run_job`) | domain + ports |
| `jarvis/app/`      | Composition root, FastAPI, event bus, config | everything |
| `tests/`           | `domain/ services/ adapters/ fakes/`  | — |

## Conventions (README §13) — load-bearing

- Respect the boundaries above: `domain/` imports nothing from `adapters/` or
  `app/`; adapters depend on ports, never on each other.
- Add features as **adapters, events, or use-cases** — not by swelling existing
  modules. The default question is *"which adapter or event does this attach
  to?"*, not *"which module do I edit?"*
- The brain is reached **only** through the `Brain` port. Never call `claude`
  from domain or use-cases.
- **Never name a component after the engine.** The component is the `brain`;
  Claude Code is its current adapter.
- Anything user-tunable goes in the **config store + config API**, not constants.
- **Every port ships an in-memory fake**; use-cases are tested without the hub,
  audio, or token spend.
- Structured logging with a per-utterance **trace id**; capture cost and latency
  on every brain invocation.
- **Never set `ANTHROPIC_API_KEY`** in the conductor's environment — it makes the
  brain bill per-token to the API account instead of the subscription
  (README §8). The composition root guards against it.
- Keep components simple. If a change feels like it needs a new microservice,
  re-read principle #2 (modular monolith).
- When you establish a new pattern, **update `README.md`** in the same change.

## Dev workflow

Python 3.12. Tooling: ruff (lint + format), mypy (strict), pytest.

```bash
make install     # create .venv and install -e ".[dev]"
make check       # lint + format-check + typecheck + test (the CI gate)
make test        # pytest only
make fmt         # auto-format and autofix
```

CI (`.github/workflows/ci.yml`) runs the same `check` gate on every PR.

## Roadmap

Work is tracked as GitHub issues grouped by the README §12 milestones (M1–M5).
Each issue is one PR merged to `main`.
