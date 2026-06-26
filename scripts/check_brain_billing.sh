#!/usr/bin/env bash
# #18 — Validate §8 subscription billing for headless `claude -p`.
#
# Answers two questions on THIS host:
#   1. Does headless `claude -p` draw from the Claude subscription (not the
#      per-token API account)?
#   2. Does its --output-format json match what ClaudeCodeBrain parses?
#
# It cannot read the billing pool itself (only /status + the API dashboard show
# that), so it standardizes the workload and tells you exactly what to compare.
#
# Usage: scripts/check_brain_billing.sh [num_calls] [prompt]
set -uo pipefail

N="${1:-5}"
PROMPT="${2:-Reply with one short sentence about latency.}"

command -v claude >/dev/null || { echo "ERROR: claude CLI not found (claude login first)."; exit 1; }
command -v jq >/dev/null || { echo "ERROR: jq not found (brew install jq)."; exit 1; }

echo "=== Preflight ==="
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  echo "!! ANTHROPIC_API_KEY is SET. Unset it before testing — a key bills the API"
  echo "   account instead of the subscription (README §8). Aborting."
  exit 1
fi
echo "ok: ANTHROPIC_API_KEY is not set"
echo
echo "BEFORE you continue, snapshot baselines:"
echo "  - run \`claude\` interactively -> /status  (note the usage window)"
echo "  - open the Anthropic Console usage/billing dashboard (the API account)"
read -r -p "Press enter to run $N headless calls... " _

first=$(claude -p "$PROMPT" --output-format json)
echo
echo "=== Raw JSON of first call ==="
echo "$first" | jq .

echo
echo "=== Schema check: keys ClaudeCodeBrain reads ==="
ok=1
for path in result session_id total_cost_usd is_error usage.input_tokens usage.output_tokens; do
  val=$(echo "$first" | jq -r "(.${path}) // \"MISSING\"")
  [ "$val" = "MISSING" ] && ok=0
  printf "  %-24s %s\n" ".$path" "$val"
done
if [ "$ok" -eq 1 ]; then
  echo "  -> schema OK: matches ClaudeCodeBrain._parse_result"
else
  echo "  -> schema MISMATCH: a key is missing/renamed; update ClaudeCodeBrain._parse_result"
fi

total=$(echo "$first" | jq -r '.total_cost_usd // 0')
for i in $(seq 2 "$N"); do
  c=$(claude -p "$PROMPT" --output-format json | jq -r '.total_cost_usd // 0')
  total=$(awk -v a="$total" -v b="$c" 'BEGIN{printf "%.6f", a+b}')
  echo "  call $i: total_cost_usd=$c"
done

echo
echo "Reported total_cost_usd over $N calls: $total"
echo
echo "=== Verdict (you read these) ==="
echo "Snapshot AFTER: /status and the API dashboard."
echo "  subscription window advanced + API usage UNCHANGED  -> subscription billing CONFIRMED"
echo "      => set JARVIS_BRAIN_MODE=claude and monitor spend for a while."
echo "  API usage moved                                     -> headless bills the API (the §8 risk)"
echo "      => stay on echo; only the brain adapter changes (billing_mode / setup-token)."
