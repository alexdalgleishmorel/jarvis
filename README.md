# Jarvis — Whole-Home Voice Assistant on Claude Code

Wake word: **"Jarvis."** This is the knowledge base for the project — the vision, the architecture,
the component contracts, and the conventions Claude Code should follow when working in this repo.
Read it fully before making changes. When a decision isn't covered here, prefer the **design
principles** (§3) over ad-hoc choices, and update this document when you establish a new pattern.

---

## 1. Vision

A voice assistant that runs on the **local network**, listens in every room via cheap mic/speaker
satellites, and uses **Claude Code as its brain**. Say "Jarvis," ask anything, and the system
answers out loud — checking a calendar, searching the web, or kicking off real work in a code
project while you do the dishes.

The point of difference from a commercial assistant is open-endedness and extensibility:

- It can **reason and act**, not just match canned intents.
- It is **mine to extend** — new input surfaces, new output surfaces, new capabilities, and new
  configuration UIs should be additive, not rewrites.
- It is built from **simple, well-named components with clear contracts**, so it stays
  comprehensible as it grows.

This document describes the **whole architecture**, not a prototype. We build it incrementally
(see the roadmap), but every increment is a real vertical slice of the final system — nothing here
is throwaway scaffolding.

### Near-term capabilities
- Wake word → question → spoken answer, in any room.
- General Q&A, calendar, web search via Claude Code + MCP.
- Kick off async coding jobs by voice; get notified when they finish.

### Designed-for-from-day-one future capabilities
- **Speaker identification** — know *who* is talking, to load per-person context (their calendar,
  permissions, preferred voice). The data model and ingress carry a speaker slot now, even though
  the resolver is a stub today.
- **Configuration UI (the dashboard)** — a web app to configure satellites, speakers, mics, lights,
  scenes, and assistant behaviour. Devices are owned by the hub; the dashboard configures the
  *assistant* and commands devices *through* the hub.
- **New interface ideas** — a new surface (a wall tablet, a phone app, a Slack DM, a custom panel)
  is "just another adapter" plus, optionally, "just another dashboard module."

---

## 2. Component names

Names are chosen so it's obvious what each piece does. This is the canonical vocabulary — use these
names in code, comments, and conversation.

| Name | What it does | Underlying tech | Built or assembled |
|------|--------------|-----------------|--------------------|
| **mic** | Captures your voice in a room | Satellite microphone | assembled |
| **speaker** | Plays Jarvis's reply in the room | Satellite speaker | assembled |
| **listener** | Wakes on the word "Jarvis" | openWakeWord | assembled |
| **transcriber** | Turns your speech into text | faster-whisper | assembled |
| **voice** | Turns text answers into speech | Piper | assembled |
| **hub** | Connects room devices, routes audio to/from the right room, owns physical devices (lights, scenes) | Home Assistant | assembled |
| **conductor** | Decides how each request flows and coordinates everything | The Jarvis app (this repo) | **built** |
| **brain** | Reasons, searches the web, checks the calendar, writes code | Claude Code (behind the `Brain` port) | **built (adapter)** |
| **messenger** | Pings you when an async job finishes | `Notifier` port (Slack/push adapter) | **built** |
| **dashboard** | Future web UI to configure the system | React + Vite control plane | **built (future)** |

A room's **mic** and **speaker** usually live in one physical box (a "satellite"); we name them by
role for clarity. The **conductor** coordinates and decides how a request should flow; the **brain**
does the actual cognition.

---

## 3. Design principles

These are load-bearing. Follow them unless this document explicitly says otherwise.

1. **Ports and adapters (hexagonal).** A pure domain core depends on nothing external. Everything
   that touches the outside world — the hub, the brain, the voice, the messenger, the database,
   speaker ID — is an **adapter** behind a **port** (a Python `Protocol`/ABC). Swapping a vendor or
   engine is a new adapter, never a domain rewrite.

2. **Modular monolith, not microservices.** The conductor is a single deployable service with strict
   internal module boundaries — simple to run, easy to reason about, still cleanly splittable later.
   Resist premature distribution.

3. **The brain lives behind one port.** All cognition goes through the `Brain` port. Auth, billing
   mode, model selection, and the choice of `claude -p` CLI vs Agent SDK are *implementation details
   of one adapter*. The rest of the system never knows how Claude is reached. This matters doubly
   because the billing/auth landscape is volatile (§8). **Never name a component after the engine** —
   the component is the `brain`; Claude Code is today's adapter.

4. **The hub owns devices; the conductor owns the experience.** Home Assistant is the source of truth
   for satellites, mics, speakers, lights, and scenes. We read and command them via the hub's API. We
   never maintain a competing device registry. Our config store holds *assistant* configuration and
   the mappings/policies the hub doesn't know about.

5. **Config over code.** Anything a user might reasonably tune lives in the config store and is
   exposed through the config API — not hard-coded. New tunables ship with an API surface so the
   dashboard can reach them without backend changes.

6. **Events decouple everything.** Components communicate through an internal pub/sub event bus
   (in-process to start, swappable for Redis/NATS later). New interfaces and observers subscribe to
   events rather than being wired into the request path. This is the backbone of extensibility.

7. **Identity is first-class but pluggable.** Every request carries an optional `Speaker`. Today the
   resolver returns the household default; tomorrow a voice-embedding adapter fills it in. Code that
   depends on identity must degrade gracefully when the speaker is unknown.

8. **Local-first, fail-soft.** The voice path (listener/transcriber/voice) is fully local; only the
   text transcript leaves the network, to Anthropic. When the brain is slow or unavailable, the
   conductor gives immediate audio feedback and never hangs a room.

9. **Every port has a fake.** Each port ships an in-memory/stub adapter so use-cases are testable
   without the hub, without audio, and without spending tokens.

---

## 4. System architecture

The voice path is assembled, not built: satellites stream audio; the **listener** detects the wake
word; the **transcriber** converts speech to text; the **voice** speaks replies; the **hub** chains
these and tracks which room (HA *area*) originated an utterance. The hub handles native
device-control intents itself ("turn on the kitchen lights") — those never reach us. Everything the
hub can't handle locally is forwarded to **the conductor** (registered as the hub's conversation
agent).

```
                         ┌───────────────────────── hub (Home Assistant, assembled) ────────────────────────┐
   mic ─────audio──────▶ │  listener → transcriber → Assist pipeline → (native device intent?)               │
    ▲                    │                                          │ no                                      │
    │ spoken reply       │                                          ▼                                         │
 speaker ◀──── voice ◀── │  conversation-agent call ◀──── conductor ────▶  voice → speaker (originating room) │
                         └──────────────────────────────────────────┬──────────────────────────────────────┘
                                                                     │ HTTP (transcript + area + speaker?)
   ┌─────────────────────────────────────── conductor (this repo) ──────────────────────────────────────────┐
   │  Ingress adapter ─▶ handle_utterance use-case                                                            │
   │        ├─ SpeakerIdentifier (port)        ── null today, voice-embedding adapter later                   │
   │        ├─ SessionManager (domain)         ── per (room, speaker), with idle timeout                      │
   │        ├─ RoutingPolicy (domain)          ── QUICK_QA | ASYNC_JOB                                         │
   │        ├─ Brain (port) ───────────────────── the brain: ClaudeCodeBrain adapter (claude -p / Agent SDK)  │
   │        │        └─▶ tools: MCP (calendar, gmail), web search, code repos, hub control                    │
   │        ├─ TextToSpeech (port) ────────────── the voice: hub/Piper adapter (speak to originating area)    │
   │        └─ Notifier (port) ────────────────── the messenger: Slack/push adapter (async job done)          │
   │  Event bus (in-proc pub/sub)  ◀── stages publish: utterance.received, response.ready, job.*               │
   │  Store (port) ─────────────────── SQLite adapter now, Postgres-ready (SQLAlchemy)                         │
   │  Config API (FastAPI) ◀────────── consumed by the dashboard; reads/writes config + proxies hub entities   │
   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                                     │ HTTP/JSON
   ┌─────────────────────────────────────── dashboard (this repo, future) ──────────────────────────────────┐
   │  React + Vite. Registry-driven panels. Configure satellites/speakers/mics/lights/scenes + assistant.    │
   │  Live event view. New interface ideas = new panel modules.                                               │
   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Components and contracts

The conductor is a modular monolith. Pure core in `jarvis/domain/`; interfaces in `jarvis/ports/`;
implementations in `jarvis/adapters/`; orchestration in `jarvis/services/`; wiring in `jarvis/app/`.

### Domain core (`jarvis/domain/`) — no external imports
- **Entities / value objects** (`models.py`): `Utterance`, `Request`, `Response`, `Room`, `Speaker`,
  `Session`, `Job`, `Capability`, `RoutingDecision`. Plain data; no I/O.
- **SessionManager** (`sessions.py`): conversation continuity, keyed by `(room_id, speaker_id)`. A
  new utterance within the idle timeout continues the same brain session (so "what about tomorrow?"
  works); otherwise it starts fresh. Holds the mapping to the brain's `session_id` for `--resume`.
  Knows nothing about how the brain is invoked.
- **RoutingPolicy** (`routing.py`): classifies a request as `QUICK_QA` or `ASYNC_JOB` (device
  commands are handled upstream by the hub). Explicit and testable; rule-driven first, can grow
  smarter behind the same interface.

### Ports (`jarvis/ports/`)
- **`Brain`** (the brain): `invoke(request, session, *, tools, model, budget) -> BrainResult`.
  `BrainResult` carries `text`, `brain_session_id`, `cost`, `usage`, tool-activity metadata. The
  single seam over cognition.
- **`SpeakerIdentifier`**: `identify(audio_or_ref, room) -> Speaker`. Null adapter returns the
  household default; future adapter resolves a voice embedding to a known profile.
- **`TextToSpeech`** (the voice): `speak(text, *, area) -> None`. Routes to the originating area.
- **`Notifier`** (the messenger): `notify(message, *, target) -> None`.
- **`HomeAssistant`** (the hub): `list_entities(...)`, `call_service(...)`, `get_areas(...)`. The only
  path to devices.
- **`Store`**: persistence for config, sessions, jobs, speaker profiles, capability registry.

### Adapters (`jarvis/adapters/`)
- **`brain/claude_code.py`** — `ClaudeCodeBrain`, the brain's current adapter. Shells `claude -p`
  (or uses the Agent SDK). Owns auth/billing/model policy (§8), session resume, allowed-tools, and
  budget/quota guards.
- **`ingress/ha_conversation.py`** — receives the hub's conversation-agent call, builds a domain
  `Request` (text, area→room, optional speaker, conversation id).
- **`tts/ha_piper.py`** (voice), **`notify/slack.py`** (messenger), **`speaker_id/null.py`**,
  **`store/sqlite.py`**, **`ha/rest.py`** (hub) — as named.

### Application wiring (`jarvis/app/`)
- **`api/`** — FastAPI routes: the ingress endpoint the hub calls, and the config API the dashboard
  calls.
- **`events/`** — the in-process event bus.
- **`config.py`**, **`main.py`** — composition root: instantiate adapters, inject into use-cases.

### Use-cases (`jarvis/services/`)
- **`handle_utterance.py`** — the request lifecycle (§6).
- **`run_job.py`** — async job execution + completion event.

---

## 6. Key flows

### Quick Q&A (synchronous, spoken back)
1. Hub does wake (listener) → speech-to-text (transcriber), tries native intents, and (not handled)
   calls our conversation-agent endpoint with `{text, area, conversation_id, speaker?}`.
2. Ingress adapter → `handle_utterance`.
3. `SpeakerIdentifier.identify(...)` → household default today.
4. `SessionManager` resolves/creates the `(room, speaker)` session and its brain `session_id`.
5. `RoutingPolicy` → `QUICK_QA`.
6. `Brain.invoke(...)` runs `claude -p --resume <id> --output-format json` with a scoped tool
   allow-list and model choice; returns `BrainResult`.
7. `TextToSpeech.speak(result.text, area=room.area)` → the voice → speaker in the originating room.
8. `response.ready` is published with trace id, cost, latency.

### Async coding job (fire-and-notify)
1–5. As above, but `RoutingPolicy` → `ASYNC_JOB`.
6. Immediately speak an acknowledgement ("on it — I'll let you know when it's done").
7. `run_job` executes a headless brain run against the target repo in the background.
8. On completion, publish `job.completed`; the messenger sends a Slack/push summary. Do **not** read
   code aloud.

Every stage publishes an event. Observers (logging, future dashboard live view) subscribe; they are
never in the request's critical path.

---

## 7. Identity and speaker ID (future, seam now)

- `Request.speaker` exists today, populated by `SpeakerIdentifier`. The null adapter returns
  `Speaker(id="household", profile=default)`.
- A `Speaker` profile binds: display name, calendar/Gmail account (which MCP context to load),
  permission scope (what tools/repos this person may trigger), and preferred voice.
- When the voice-embedding adapter lands (resolving an utterance to an enrolled profile), only that
  adapter and an enrolment flow are new. The session key already includes `speaker_id`; per-user
  context loading already hangs off the profile. Nothing downstream changes.
- **Rule:** code that uses identity must work when the speaker is `household`/unknown.

---

## 8. Auth, billing, and quota — read carefully

The system runs on the local network and uses a **Claude Pro or Max subscription** for tokens. This
area is genuinely volatile; treat the following as design guidance and **validate on the box before
relying on it**.

- **Authenticate via the subscription, not an API key.** Run `claude login` on the host so the brain
  uses the subscription OAuth credential (it auto-refreshes). **Do not set `ANTHROPIC_API_KEY` in the
  conductor's environment** — if present, Claude Code uses that key and bills per-token to the API
  account instead of the subscription. Make this an explicit, documented part of runtime config;
  guard against it leaking in from a shell profile, `.env`, or container config.
- **Known risk to validate early (gate):** there are reported cases where `claude -p` (headless)
  billed as API usage even under OAuth/subscription with no API key set. Before building on top of
  the brain adapter, verify with `/status` and the usage dashboard on this exact host that headless
  invocations draw from the subscription, and monitor spend for the first while. If they don't, the
  brain adapter is the *only* place that has to change.
- **Policy is in flux.** A 2026 proposal to move headless / Agent SDK usage off subscription pools
  onto separate credits was announced and then paused; for now headless draws from subscription
  limits, with advance notice promised before any future change. Because of this, the brain adapter
  must keep **billing mode a config flag** (subscription-OAuth vs API-key) so we can switch without
  touching the rest of the system.
- **Shared, capped quota.** Subscription usage is shared across Claude on web/desktop/mobile and
  Claude Code, under a rolling multi-hour session window plus weekly caps. An always-on assistant
  competes with interactive use. The brain adapter should implement:
  - **Model tiering** — a cheap fast model for quick Q&A; escalate to a stronger model only for
    coding jobs.
  - **Budget/quota guard** — per-invocation `--max-turns` and a budget ceiling; back off and speak a
    graceful "I'm at my limit right now" on rate-limit responses.
  - **Caching and coalescing** where applicable.
  - Plan for **Max** rather than Pro if usage is heavy; Pro's window is tight for always-on.
- **Detached operation:** if the conductor runs without an interactive login session, generate a
  portable OAuth token (`claude setup-token`) and supply it to the brain adapter as a secret, rather
  than falling back to an API key.

---

## 9. Extensibility playbook

How to add things without rewrites. Each of these is the intended path:

- **New input surface** (wall tablet, phone app, Slack, push-to-talk button): write an **ingress
  adapter** that produces a domain `Request`. The whole pipeline downstream is reused.
- **New output surface**: write an **egress adapter** that subscribes to `response.ready` /
  `job.completed`. No change to the request path.
- **New capability/tool**: register an MCP server or tool and expose a config toggle. Scope it per
  speaker via the permission model.
- **Speaker ID**: replace `speaker_id/null.py` with a voice adapter + enrolment flow (§7).
- **New device type**: it's a hub entity — read/command it via the `HomeAssistant` port; the
  dashboard's entity browser picks it up for free.
- **New dashboard panel / interface idea**: drop a registry-driven React panel that talks to the
  config or event API (§10). The backend usually needs only a new config field or event subscription.
- **Different engine/model**: a new `Brain` adapter. Nothing else changes.

When adding a feature, the default question is *"which adapter or event does this attach to?"* — not
*"which existing module do I edit?"*

---

## 10. Control plane and dashboard

- **Config store** (via `Store` port): rooms↔satellites mapping, speaker profiles and bindings,
  session policy (timeouts), routing policy parameters, model/tiering policy, capability registry and
  per-speaker permissions, interface/panel registry. Devices are **not** stored here — they're read
  live from the hub.
- **Config API** (FastAPI): typed CRUD over the config store, plus read/command proxies to hub
  entities (so the dashboard never needs hub credentials directly). Every backend tunable is
  reachable here.
- **Dashboard** (React + Vite, in `dashboard/`): registry-driven **panels**, each a self-contained
  module that declares its route and talks to the config/event API. Initial panels: satellites/rooms,
  assistant behaviour, capabilities/permissions, hub entity browser (speakers/mics/lights/scenes),
  and a live event view. New interface ideas are new panels — additive by construction.

---

## 11. Tech stack and repo layout

- **Conductor:** Python 3.12, **FastAPI**, Pydantic, SQLAlchemy (SQLite now, Postgres-ready), an
  async in-process event bus. `pytest` with port fakes.
- **Brain:** Claude Code via the `ClaudeCodeBrain` adapter.
- **Dashboard:** **React + Vite**, TypeScript.
- **Assembled (the hub and voice path):** Home Assistant + Wyoming (listener = openWakeWord,
  transcriber = faster-whisper, voice = Piper), per-room satellites.
- **Runtime:** Docker Compose on a single local host (hub and Wyoming containers may run on the same
  box or a separate one on the LAN).

```
jarvis/
  CLAUDE.md                 # this file
  README.md
  docker-compose.yml        # hub (HA), listener, transcriber, voice, conductor, dashboard, db
  pyproject.toml
  jarvis/
    domain/        models.py  sessions.py  routing.py
    ports/         brain.py  tts.py  notifier.py  speaker_id.py  store.py  home_assistant.py
    adapters/      brain/claude_code.py  ingress/ha_conversation.py  tts/ha_piper.py
                   notify/slack.py  speaker_id/null.py  store/sqlite.py  ha/rest.py
    app/           api/  events/  config.py  main.py
    services/      handle_utterance.py  run_job.py
  dashboard/       src/{panels,api,components}  vite.config.ts
  tests/           domain/  services/  adapters/  fakes/
```

---

## 12. Roadmap — incremental slices of the real architecture

Each milestone is a working vertical slice. The ports/adapters skeleton is real from M1; later
milestones fill adapters in, they don't replace a hacked-together core.

- **M1 — Walking skeleton.** One room. Hub → conductor → brain (`claude -p`) → voice back to room.
  Null speaker, SQLite store, in-proc events, fakes for tests. Thin but architecturally complete.
  **Validate §8 billing on the box here.**
- **M2 — Multi-room + sessions + async jobs.** `(room, speaker)` sessions with timeout; `ASYNC_JOB`
  mode with ack + messenger. Multiple satellites, replies routed to the originating room.
- **M3 — Control plane + dashboard v1.** Config store + config API; React panels for rooms/satellites,
  assistant settings, and a hub entity browser.
- **M4 — Speaker ID.** Voice-embedding adapter + enrolment; per-user context bindings and permissions.
- **M5 — Dashboard expansion.** Device/scene configuration surfaces, custom interface panels, live
  event view; harden quota guards and model tiering.

---

## 13. Conventions for Claude Code in this repo

- Respect the boundaries: `domain/` imports nothing from `adapters/` or `app/`. Adapters depend on
  ports, never on each other.
- Add features as **adapters, events, or use-cases** — not by swelling existing modules.
- The brain is reached **only** through the `Brain` port. Never call `claude` from domain or
  use-cases.
- Anything user-tunable goes in the **config store + config API**, not constants.
- Every port gets an in-memory fake; use-cases are tested without the hub, audio, or token spend.
- Structured logging with a per-utterance **trace id**; capture cost and latency on every brain
  invocation.
- **Never** set `ANTHROPIC_API_KEY` in the conductor's environment (billing — see §8).
- **Never** name a component after the engine. The component is the `brain`; Claude Code is its
  adapter.
- Keep components simple. If a change feels like it needs a new microservice, re-read principle #2.
- When you establish a new pattern, **update this document** in the same change.

---

## 14. Glossary (plain English)

- **mic** — captures your voice in a room.
- **speaker** — plays Jarvis's reply in the room.
- **listener** (openWakeWord) — the always-listening ear; ignores everything until it hears "Jarvis."
- **transcriber** (faster-whisper) — turns your speech into the text sent to the brain.
- **voice** (Piper) — turns the brain's answer into speech, played on the speaker.
- **hub** (Home Assistant) — connects the room devices, routes audio to/from the right room, owns
  physical devices, and handles native device commands.
- **conductor** (this repo) — decides how each request flows and coordinates everything.
- **brain** (Claude Code, behind the `Brain` port) — reasons, searches, checks the calendar, writes
  code.
- **messenger** (`Notifier`) — pings you when an async job finishes.
- **dashboard** (future React app) — configures the system.
- **ports & adapters** — interfaces vs implementations; how we keep the core clean and swappable.

---

## 15. Open questions to resolve early

- Confirm headless `claude -p` (the brain) draws from the subscription on this host (§8) — gates
  everything.
- Acceptable latency budget for the Q&A path, and whether always-on contention with interactive
  Claude usage is tolerable in practice.
- Wake word: a custom "Jarvis" openWakeWord model vs an existing community model — pick during M1.
