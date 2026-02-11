#!/bin/bash
set -euo pipefail

# configuration
TARGET_URL=$(kubectl get svc frontend -o jsonpath='http://{.spec.clusterIP}:{.spec.ports[0].port}')

RATE=150000                       # wrk -R requests-per-second
RAMPRATE=300000                       # wrk -R requests-per-second
SCRIPT_DIR="/users/jonggyu/pwr-sched/pwr-sc/utils"
CAP_NODE="node1"
CAP_WATTS=$1
OUTDIR=./results-${1}
mkdir -p $OUTDIR

rm -f -- "${OUTDIR}"/* 2>/dev/null || true

kgd() { kubectl get deployments "$@"; }
ktn() { kubectl top nodes "$@"; }

./refresh_pods.sh
( cd "$SCRIPT_DIR" && ./sched_switch.sh disable )
( cd "$SCRIPT_DIR" && ./control_power.sh set all max )
sleep 30
# ───────── baseline load ─────────
../wrk -D exp -t 60 -c 80 -d 300 -L \
    -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
    "$TARGET_URL" -R "$RAMPRATE"

../wrk -D exp -t 60 -c 80 -d 300 -L \
    -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
    "$TARGET_URL" -R "$RATE"

kgd >> $OUTDIR/baseline.dat
../wrk -D exp -t 60 -c 80 -d 300 -L \
    -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
    "$TARGET_URL" -R "$RATE" >> $OUTDIR/baseline.dat

( cd "$SCRIPT_DIR" && ./control_power.sh monitor all ) >> $OUTDIR/baseline.dat
ktn >> $OUTDIR/baseline.dat
kgd >> $OUTDIR/baseline.dat

./refresh_pods.sh

sleep 30
# ───────── apply power cap ────────
( cd "$SCRIPT_DIR" && ./control_power.sh set "$CAP_NODE" "$CAP_WATTS" )
#( cd "$SCRIPT_DIR" && ./control_power.sh set node2 "$CAP_WATTS" )
sleep 5     # ensure cap is active

# ───────── capped load ────────────
../wrk -D exp -t 60 -c 80 -d 300 -L \
    -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
    "$TARGET_URL" -R "$RAMPRATE"

../wrk -D exp -t 60 -c 80 -d 300 -L \
    -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
    "$TARGET_URL" -R "$RATE"


kgd >> $OUTDIR/capped-baseline.dat
../wrk -D exp -t 60 -c 80 -d 300 -L \
    -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
    "$TARGET_URL" -R "$RATE" >> $OUTDIR/capped-baseline.dat

( cd "$SCRIPT_DIR" && ./control_power.sh monitor all ) >> $OUTDIR/capped-baseline.dat


ktn >> $OUTDIR/capped-baseline.dat
kgd >> $OUTDIR/capped-baseline.dat

./refresh_pods.sh
( cd "$SCRIPT_DIR" && ./sched_switch.sh enable )

sleep 30

# ───────── capped load ────────────
../wrk -D exp -t 60 -c 80 -d 300 -L \
    -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
    "$TARGET_URL" -R "$RAMPRATE"

../wrk -D exp -t 60 -c 80 -d 300 -L \
    -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
    "$TARGET_URL" -R "$RATE"


kgd >> $OUTDIR/capped-ours.dat
../wrk -D exp -t 60 -c 80 -d 300 -L \
    -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
    "$TARGET_URL" -R "$RATE" >> $OUTDIR/capped-ours.dat

( cd "$SCRIPT_DIR" && ./control_power.sh monitor all ) >> $OUTDIR/capped-ours.dat


ktn >> $OUTDIR/capped-ours.dat
kgd >> $OUTDIR/capped-ours.dat
( cd "$SCRIPT_DIR" && ./sched_switch.sh disable )
( cd "$SCRIPT_DIR" && ./control_power.sh set all max )
./refresh_pods.sh
