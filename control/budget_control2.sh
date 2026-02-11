#!/usr/bin/env bash
# random_power_budget.sh
set -euo pipefail

# --- Config --------------------------------------------------------------
BUDGET_FILE="${1:-./budget}"     # optional arg: path to budget file
BASE=250                          # nominal (100%) power budget, in W

LOW_PCT_MIN=${LOW_PCT_MIN:-15}    # reduction percent range (inclusive)
LOW_PCT_MAX=${LOW_PCT_MAX:-25}
HIGH_PCT_MIN=${HIGH_PCT_MIN:-90}  # high-phase percent range (inclusive)
HIGH_PCT_MAX=${HIGH_PCT_MAX:-100}

DUR_MIN_S=${DUR_MIN_S:-5}         # phase duration range (seconds, inclusive)
DUR_MAX_S=${DUR_MAX_S:-20}

LOG=${LOG:-1}                     # set LOG=0 to silence stderr logs
# ------------------------------------------------------------------------

rand_range() { # inclusive integer range: rand_range MIN MAX
  local min=$1 max=$2
  echo $(( min + RANDOM % (max - min + 1) ))
}

log() { [[ "$LOG" -eq 1 ]] && echo "[$(date +%T)] $*" >&2 || true; }

# Restore BASE on exit (SIGINT/SIGTERM included)
cleanup() { echo "$BASE" > "$BUDGET_FILE" || true; }
trap cleanup EXIT INT TERM

# Initialize
echo "$BASE" > "$BUDGET_FILE"
log "Initialized budget to BASE=${BASE}W (file: $BUDGET_FILE)"

while true; do
  # Pick a random HIGH between 90–100% of BASE
  HIGH_PCT=$(rand_range "$HIGH_PCT_MIN" "$HIGH_PCT_MAX")
  HIGH=$(( BASE * HIGH_PCT / 100 ))

  # Pick a random reduction between 15–25%, compute LOW
  REDUCE_PCT=$(rand_range "$LOW_PCT_MIN" "$LOW_PCT_MAX")
  LOW=$(( BASE * (100 - REDUCE_PCT) / 100 ))

  # Random durations for each phase between 5–20s
  D_LOW=$(rand_range "$DUR_MIN_S" "$DUR_MAX_S")
  D_HIGH=$(rand_range "$DUR_MIN_S" "$DUR_MAX_S")

  # --- Low phase ---
  echo "$LOW" > "$BUDGET_FILE"
  log "LOW phase: ${LOW}W (−${REDUCE_PCT}% of BASE) for ${D_LOW}s"
  sleep "$D_LOW"

  # --- High phase ---
  echo "$HIGH" > "$BUDGET_FILE"
  log "HIGH phase: ${HIGH}W (${HIGH_PCT}% of BASE) for ${D_HIGH}s"
  sleep "$D_HIGH"
done
