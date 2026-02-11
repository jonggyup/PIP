#!/bin/bash

# This script runs pairwise combinations of latency-sensitive (group1) and best-effort (group2) applications
# under two CPU power capping mechanisms: a custom system ('sys') and Google's UIMD ('google').
# For each combination, it:
#   - Launches group2 app in background
#   - Launches group1 app in foreground (monitored duration)
#   - Starts the corresponding power capping script in parallel
#   - Records performance outputs for both apps and power traces
#   - Cleans up processes after group1 completes
# Results are saved under results-qos-cap/ with descriptive filenames.


SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p results-qos-cap
sudo cgcreate -g cpu:/user

# Define application groups
group1=("hotel" "social" "fileserver" "cnninf")
group2=("bert" "cnn" "tfidfvec")
#group1=("social")

echo "190" > ./control/budget

# Measuring power
(cd ./estimation/ && python3 ./estimate_CPU_power-compare-all.py 1 ) &

# Run workloads
run_benchmark() {
    local app1=$1
    local app2=$2
    local suffix=$3

    case $app2 in
        bert)
            pushd "$SCRIPT_DIR/benchmark-suites/ML-training" > /dev/null
            cgexec -g cpu:/user python3 bert.py > "$SCRIPT_DIR/results-qos-cap/${app1}_${app2}_${suffix}_performance2.dat" 2>&1 &
            popd > /dev/null
            ;;
        cnn)
            pushd "$SCRIPT_DIR/benchmark-suites/ML-training" > /dev/null
            cgexec -g cpu:/user python3 cnn.py > "$SCRIPT_DIR/results-qos-cap/${app1}_${app2}_${suffix}_performance2.dat" 2>&1 &
            popd > /dev/null
            ;;
        tfidfvec)
            pushd "$SCRIPT_DIR/benchmark-suites/ML-training" > /dev/null
            cgexec -g cpu:/user python3 tfidfvec.py > "$SCRIPT_DIR/results-qos-cap/${app1}_${app2}_${suffix}_performance2.dat" 2>&1 &
            popd > /dev/null
            ;;
    esac
    sleep 30

    case $app1 in
        fileserver)
            pushd "$SCRIPT_DIR/benchmark-suites/filebench" > /dev/null
            echo 0 > /proc/sys/kernel/randomize_va_space
            cgexec -g cpu:/critical filebench -f ./workloads/fileserver.f > "$SCRIPT_DIR/results-qos-cap/${app1}_${app2}_${suffix}_performance1.dat" 2>&1
            popd > /dev/null
            ;;
        hotel)
            pushd "$SCRIPT_DIR/benchmark-suites/DeathStarBench/hotelReservation" > /dev/null
            ./run_critical.sh > "$SCRIPT_DIR/results-qos-cap/${app1}_${app2}_${suffix}_performance1.dat" 2>&1
	    docker volume prune -f
            popd > /dev/null
            ;;
        social)
            pushd "$SCRIPT_DIR/benchmark-suites/DeathStarBench/socialNetwork" > /dev/null
            ./run_critical.sh > "$SCRIPT_DIR/results-qos-cap/${app1}_${app2}_${suffix}_performance1.dat" 2>&1
	    docker volume prune -f
            popd > /dev/null
            ;;
        cnninf)
            pushd "$SCRIPT_DIR/benchmark-suites/etc" > /dev/null
            cgexec -g cpu:/critical python3 cnninf.py --duration 120 > "$SCRIPT_DIR/results-qos-cap/${app1}_${app2}_${suffix}_performance1.dat" 2>&1
            popd > /dev/null
            ;;
    esac
}

run_sys() {
    local output_file=$1
    pushd "$SCRIPT_DIR/control" > /dev/null
    sleep 10
    python3 powercap_CPU_powertrace-final.py 1 | tee "$SCRIPT_DIR/results-qos-cap/${output_file}_sys_power.dat" &
    CAP_PID=$!
    popd > /dev/null
}

run_google() {
    local output_file=$1
    pushd "$SCRIPT_DIR/control" > /dev/null
    sleep 10
    python3 powercap_CPU_google-ALL-v1.2.py 1 | tee "$SCRIPT_DIR/results-qos-cap/${output_file}_google_power.dat" &
    CAP_PID=$!
    popd > /dev/null
}

for app1 in "${group1[@]}"; do
    for app2 in "${group2[@]}"; do
        pair="${app1}_${app2}"

        sleep 30
        ./scripts/cgroup_ctl_setup.sh
        # Run with google
        run_google "$pair"
        run_benchmark "$app1" "$app2" "google"
        while read pid; do sudo kill -9 $pid; done < /sys/fs/cgroup/user/cgroup.procs || true
        kill $CAP_PID 2>/dev/null || true
        while read pid; do sudo kill -9 $pid; done < /sys/fs/cgroup/critical/cgroup.procs || true
        pkill -ef powercap_CPU_google
        sleep 30
        ./scripts/cgroup_ctl_setup.sh
        # Run with sys
        run_sys "$pair"
        run_benchmark "$app1" "$app2" "sys"
        while read pid; do sudo kill -9 $pid; done < /sys/fs/cgroup/user/cgroup.procs || true
        kill $CAP_PID 2>/dev/null || true
        while read pid; do sudo kill -9 $pid; done < /sys/fs/cgroup/critical/cgroup.procs || true
        pkill -ef powercap_CPU_powertrace

    done
done

pkill -ef estimate_CPU_power-compare-all

echo "300" > ./control/budget
