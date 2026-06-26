# scripts — on-box test helpers

Diagnostic tools run by hand on the host. They are **not** part of the conductor
package or CI (they need a logged-in `claude`, a mic, and optional heavy deps).

| Script | Issue | What it tests |
|--------|-------|---------------|
| `check_brain_billing.sh` | #18 | Whether headless `claude -p` draws from the subscription, and whether its JSON matches `ClaudeCodeBrain`. |
| `wakeword_test.py` | #19 | `hey_jarvis` true-accept / false-accept rate from the mic, with a tunable threshold. |

See `docs/laptop-e2e.md` for how these fit into the full e2e.
