#!/bin/bash
set -euo pipefail

# configuration
target_url=$(kubectl get svc frontend -o jsonpath='http://{.spec.clusterIP}:{.spec.ports[0].port}')
rate=300000                       # wrk -R requests-per-second
ramprate=300000                   # wrk -R requests-per-second
script_dir="/users/jonggyu/pwr-sched/pwr-sc/utils"
cap_node="node2"

# iterate over cap values and runs
for cap_watts in 100; do #120 140; do
  for run in {1..3}; do
    outdir="./results-hetero-${cap_watts}-${run}"
    mkdir -p "$outdir"
    rm -f -- "$outdir"/* 2>/dev/null || true

    kgd() { kubectl get deployments "$@"; }
    ktn() { kubectl top nodes "$@"; }

    ./refresh_pods.sh
    ( cd "$script_dir" && ./sched_switch.sh disable )
    ( cd "$script_dir" && ./control_power.sh set all max )
    sleep 30

    # ───────── baseline load ─────────
    ../wrk -D exp -t 60 -c 180 -d 300 -L \
        -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
        "$target_url" -R "$ramprate"

    ../wrk -D exp -t 60 -c 180 -d 300 -L \
        -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
        "$target_url" -R "$rate"

    kgd >> "$outdir/baseline.dat"
    ../wrk -D exp -t 60 -c 180 -d 300 -L \
        -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
        "$target_url" -R "$rate" >> "$outdir/baseline.dat"

    ( cd "$script_dir" && ./control_power.sh monitor all ) >> "$outdir/baseline.dat"
    ktn >> "$outdir/baseline.dat"
    kgd >> "$outdir/baseline.dat"

    ./refresh_pods.sh
    sleep 30

    # ───────── apply power cap ────────
    ( cd "$script_dir" && ./control_power.sh set "$cap_node" "$cap_watts" )
    ( cd "$script_dir" && ./control_power.sh set node3 140 )

    sleep 5

    # ───────── capped load ────────────
    ../wrk -D exp -t 60 -c 180 -d 300 -L \
        -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
        "$target_url" -R "$ramprate"

    ../wrk -D exp -t 60 -c 180 -d 300 -L \
        -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
        "$target_url" -R "$rate"

    kgd >> "$outdir/capped-baseline.dat"
    ../wrk -D exp -t 60 -c 180 -d 300 -L \
        -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
        "$target_url" -R "$rate" >> "$outdir/capped-baseline.dat"

    ( cd "$script_dir" && ./control_power.sh monitor all ) >> "$outdir/capped-baseline.dat"
    ktn >> "$outdir/capped-baseline.dat"
    kgd >> "$outdir/capped-baseline.dat"

    ./refresh_pods.sh
    ( cd "$script_dir" && ./sched_switch.sh enable )

    sleep 30

    # ───────── capped load (ours) ─────────
    ../wrk -D exp -t 60 -c 180 -d 300 -L \
        -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
        "$target_url" -R "$ramprate"

    ../wrk -D exp -t 60 -c 180 -d 300 -L \
        -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
        "$target_url" -R "$rate"

    kgd >> "$outdir/capped-ours.dat"
    ../wrk -D exp -t 60 -c 180 -d 300 -L \
        -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua \
        "$target_url" -R "$rate" >> "$outdir/capped-ours.dat"

    ( cd "$script_dir" && ./control_power.sh monitor all ) >> "$outdir/capped-ours.dat"
    ktn >> "$outdir/capped-ours.dat"
    kgd >> "$outdir/capped-ours.dat"

    ( cd "$script_dir" && ./sched_switch.sh disable )
    ( cd "$script_dir" && ./control_power.sh set all max )
    ./refresh_pods.sh

  done
done

