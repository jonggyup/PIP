#!/bin/bash

# Get the directory of the script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir results-comp

# Function to run power estimation
run_estimation() {
    local output_file=$1

    pushd "$SCRIPT_DIR/estimation" > /dev/null
    sleep 10
    python3 estimate_CPU_power-compare-all.py 1 | tee "$output_file" &
    popd > /dev/null
}

sudo cgcreate -g cpu:/critical
CORES=$(nproc)
PERIOD=100000
QUOTA=$(( 70000 * CORES ))

#echo "$QUOTA $PERIOD" | sudo tee /sys/fs/cgroup/critical/cpu.max >/dev/null
# Fileserver benchmark
run_estimation "$SCRIPT_DIR/results-comp/fileserver.dat"
pushd "$SCRIPT_DIR/benchmark-suites/filebench" > /dev/null
echo 0 > /proc/sys/kernel/randomize_va_space
cgexec -g cpu:/critical filebench -f ./workloads/fileserver.f
sleep 10
pkill -ef estimate_CPU_power
popd > /dev/null

# Hotel reservation benchmark
run_estimation "$SCRIPT_DIR/results-comp/hotel.dat"
pushd "$SCRIPT_DIR/benchmark-suites/DeathStarBench/hotelReservation" > /dev/null
./run_critical.sh
sleep 10
pkill -ef estimate_CPU_power
popd > /dev/null

# Social network benchmark
run_estimation "$SCRIPT_DIR/results-comp/social.dat"
pushd "$SCRIPT_DIR/benchmark-suites/DeathStarBench/socialNetwork" > /dev/null
./run_critical.sh
sleep 10
pkill -ef estimate_CPU_power
popd > /dev/null

# CNN inference
run_estimation "$SCRIPT_DIR/results-comp/cnninf.dat"
pushd "$SCRIPT_DIR/benchmark-suites/etc" > /dev/null
cgexec -g cpu:/critical python3 cnninf.py --duration=120
sleep 10
pkill -ef estimate_CPU_power
popd > /dev/null

# BERT benchmark
run_estimation "$SCRIPT_DIR/results-comp/bert.dat"
pushd "$SCRIPT_DIR/benchmark-suites/ML-training" > /dev/null
cgexec -g cpu:/critical python3 bert2.py
sleep 10
pkill -ef estimate_CPU_power
popd > /dev/null

# CNN benchmark
run_estimation "$SCRIPT_DIR/results-comp/cnn.dat"
pushd "$SCRIPT_DIR/benchmark-suites/ML-training" > /dev/null
cgexec -g cpu:/critical python3 cnn.py
sleep 10
pkill -ef estimate_CPU_power
popd > /dev/null

# tfidfvec benchmark
run_estimation "$SCRIPT_DIR/results-comp/tfidfvec.dat"
pushd "$SCRIPT_DIR/benchmark-suites/ML-training" > /dev/null
cgexec -g cpu:/critical python3 tfidfvec.py
sleep 10
pkill -ef estimate_CPU_power
popd > /dev/null
echo "max 100000" | sudo tee /sys/fs/cgroup/critical/cpu.max >/dev/null

