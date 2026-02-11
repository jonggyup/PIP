#!/bin/bash

# Get the directory of the script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE=20
LOCAL=20
OUTPUT_DIR=results-wbg-${REMOTE}-${LOCAL}
mkdir -p $OUTPUT_DIR

# Function to run power estimation using powercap
run_reporter() {
    local output_file=$1
    sleep 60
    pushd "$SCRIPT_DIR" > /dev/null
    python3 send_print.py user 207 | tee $SCRIPT_DIR/$OUTPUT_DIR/${output_file}.dat &
    popd > /dev/null
}

# Function to run benchmark and use both UIMD and powercap
run_benchmark() {
    local benchmark_dir=$1
    local benchmark_command=$2
    local output_file=$3

    pushd "$benchmark_dir" > /dev/null
    eval "cgexec -g cpu:/user $benchmark_command" &
    run_reporter "${output_file}"
    sleep 200
    pkill -ef send_print
    xargs -a /sys/fs/cgroup/user/cgroup.procs -r kill -9
    popd > /dev/null
}


cgexec -g cpu:critical stress-ng -c $LOCAL &

echo 0 > /proc/sys/kernel/randomize_va_space
# Fileserver benchmark (with kernel randomization setting)
run_benchmark "$SCRIPT_DIR/../benchmark-suites/filebench" \
    "filebench -f ./workloads/fileserver.f" \
    "fileserver"

# Hotel reservation benchmark
run_benchmark "$SCRIPT_DIR/../benchmark-suites/DeathStarBench/hotelReservation" \
    "./run-cgroup.sh" "hotel"

# Social network benchmark
run_benchmark "$SCRIPT_DIR/../benchmark-suites/DeathStarBench/socialNetwork" \
    "./run-cgroup.sh" "social"

# CNN infernece benchmark
run_benchmark "$SCRIPT_DIR/../benchmark-suites/etc" \
    "python3 cnninf.py --duration 300" "cnn-inf"

# BERT benchmark
run_benchmark "$SCRIPT_DIR/../benchmark-suites/ML-training" \
    "python3 bert_benchmark.py" "bert"

# CNN benchmark
run_benchmark "$SCRIPT_DIR/../benchmark-suites/ML-training" \
    "python3 cnn2.py" "cnn"

# tfidvec benchmark
run_benchmark "$SCRIPT_DIR/../benchmark-suites/ML-training" \
    "python3 tfidvec.py" "tfidvec"

pkill -ef stress-ng
