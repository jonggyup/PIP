#!/usr/bin/env bash
set -euo pipefail

# configuration
TARGET_URL="http://10.109.33.19:5000"
RATE=200000                       # wrk -R requests-per-second
SCRIPT_DIR="/users/jonggyu/pwr-sched/pwr-sc/utils"
CAP_NODE="node1"
CAP_WATTS=100

mkdir -p results

# ───────── capped load ────────────
for i in {1..3}; do
    ../wrk -D exp -t 60 -c 80 -d 100 -L \
      -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
      "$TARGET_URL" -R "$RATE"
done

../wrk -D exp -t 60 -c 80 -d 100 -L \
  -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
  "$TARGET_URL" -R "$RATE" > results/capped-ours.dat
