### scripts to assets the overheads of \sys by comparing the power usage of \sys with rapl

#!/bin/bash

# Get the directory of the script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p results-overheads
sudo cgcreate -g cpu:/user

# Function to run power estimation using powercap
run_sys() {
    local output_file=$1

    pushd "$SCRIPT_DIR/estimation" > /dev/null
    sleep 10
    python3 estimate_CPU_power-powertrace.py 1 | tee $SCRIPT_DIR/results-overheads/${output_file}-powertrace.dat &
    popd > /dev/null
}

run_rapl() {
    local output_file=$1

    pushd "$SCRIPT_DIR/estimation" > /dev/null
    sleep 10
    python3 estimate_CPU_power-rapl.py 1 | tee $SCRIPT_DIR/results-overheads/${output_file}-rapl.dat &
    popd > /dev/null
}


# Function to run benchmark and use both UIMD and powercap
run_benchmark() {
    local benchmark_dir=$1
    local benchmark_command=$2
    local output_file=$3
    local kernel_settings_command=$4

    # Run kernel settings command if specified
    if [[ -n "$kernel_settings_command" ]]; then
        eval "$kernel_settings_command"
    fi

    ./control/rapl-recover.sh; ./scripts/cgroup_init.sh 
    # Run benchmark with rapl first
    run_rapl "${output_file}"
    pushd "$benchmark_dir" > /dev/null
    cgexec -g cpu:/user $benchmark_command &> "$SCRIPT_DIR/results-overheads/${output_file}-rapl-result.dat"
    sleep 10
    pkill -ef estimate_CPU_power-rapl.py
    popd > /dev/null

    ./control/rapl-recover.sh; ./scripts/cgroup_init.sh 
    # Run benchmark with sys next
    run_sys "${output_file}"
    pushd "$benchmark_dir" > /dev/null
    cgexec -g cpu:/user $benchmark_command &> "$SCRIPT_DIR/results-overheads/${output_file}-powertrace-result.dat"
    sleep 10
    pkill -ef estimate_CPU_power-powertrace.py
    popd > /dev/null

}
# Hotel reservation benchmark
run_benchmark "$SCRIPT_DIR/benchmark-suites/DeathStarBench/hotelReservation" \
    "./run-cgroup.sh" "hotel"

# Social network benchmark
run_benchmark "$SCRIPT_DIR/benchmark-suites/DeathStarBench/socialNetwork" \
    "./run-cgroup.sh" "social"

# Fileserver benchmark (with kernel randomization setting)
run_benchmark "$SCRIPT_DIR/benchmark-suites/filebench" \
    "filebench -f ./workloads/fileserver.f" \
    "fileserver" \
    "echo 0 > /proc/sys/kernel/randomize_va_space"

# CNN infernece benchmark
run_benchmark "$SCRIPT_DIR/benchmark-suites/etc" \
    "python3 cnn_inf.py --duration 300" "cnn-inf"

# BERT benchmark
run_benchmark "$SCRIPT_DIR/benchmark-suites/ML-training" \
    "python3 bert_benchmark.py" "bert"

# CNN benchmark
run_benchmark "$SCRIPT_DIR/benchmark-suites/ML-training" \
    "python3 cnn2.py" "cnn"

# tfidvec benchmark
run_benchmark "$SCRIPT_DIR/benchmark-suites/ML-training" \
    "python3 tfidvec.py" "tfidvec"
