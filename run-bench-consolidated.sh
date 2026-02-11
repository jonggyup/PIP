#!/bin/bash

# Get the directory of the script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p results

# Function to start power estimation
start_estimation() {
    local output_file="$SCRIPT_DIR/results/consolidation.dat"

    pushd "$SCRIPT_DIR/estimation" > /dev/null
    python3 estimate_CPU_power-all.py 1 | tee "$output_file" &
    popd > /dev/null
}

# Function to stop power estimation
stop_estimation() {
    pkill -ef estimate_CPU_power
}

# Define the new application groups
group1=("hotel" "social")
group2=("fileserver" "kernelcomp")
group3=("bert" "cnn" "tfidvec")

# Run selected apps for a specific time and kill them after 5 minutes
run_benchmark() {
    local selected_apps=("$@")
    for app in "${selected_apps[@]}"; do
        case $app in
            fileserver)
                pushd "$SCRIPT_DIR/benchmark-suites/filebench" > /dev/null
                echo 0 > /proc/sys/kernel/randomize_va_space
                filebench -f ./workloads/fileserver.f &
                popd > /dev/null
                ;;
            hotel)
                pushd "$SCRIPT_DIR/benchmark-suites/DeathStarBench/hotelReservation" > /dev/null
                ./run.sh &
                popd > /dev/null
                ;;
            social)
                pushd "$SCRIPT_DIR/benchmark-suites/DeathStarBench/socialNetwork" > /dev/null
                ./run.sh &
                popd > /dev/null
                ;;
            kernelcomp)
                pushd "$SCRIPT_DIR/benchmark-suites/kcbench" > /dev/null
                ./run.sh &
                popd > /dev/null
                ;;
            bert)
                pushd "$SCRIPT_DIR/benchmark-suites/ML-training" > /dev/null
                python3 bert_benchmark.py &
                popd > /dev/null
                ;;
            cnn)
                pushd "$SCRIPT_DIR/benchmark-suites/ML-training" > /dev/null
                python3 cnn.py &
                popd > /dev/null
                ;;
            tfidvec)
                pushd "$SCRIPT_DIR/benchmark-suites/ML-training" > /dev/null
                python3 tfidvec.py &
                popd > /dev/null
                ;;
        esac
    done

    # Sleep for 5 minutes and then kill all running benchmark processes
    #wrapup period
    sleep 300
    for app in "${selected_apps[@]}"; do
        pkill -ef $(basename "${app}")
    done
    pkill -ef filebench
}

# Main loop to repeat process for a specified time (in seconds)
total_duration=1800  # Example: run for 30 minutes
end_time=$((SECONDS + total_duration))

# Start power estimation at the beginning
start_estimation "$SCRIPT_DIR/results/estimation_start.dat"

while [ $SECONDS -lt $end_time ]; do
    # Randomly pick 0 or 1 application from each group
    selected_apps=()
    selected_apps+=($(shuf -e "" "${group1[@]}" -n 1))  # May select 0 or 1
    selected_apps+=($(shuf -e "" "${group2[@]}" -n 1))  # May select 0 or 1
    selected_apps+=($(shuf -e "" "${group3[@]}" -n 1))  # May select 0 or 1

    # Filter out empty selections (if none are chosen)
    selected_apps=($(echo "${selected_apps[@]}" | tr -s ' '))

    # Run selected applications (if any were selected)
    if [ ${#selected_apps[@]} -gt 0 ]; then
        run_benchmark "${selected_apps[@]}"
    fi
done

# Stop power estimation at the end
stop_estimation

