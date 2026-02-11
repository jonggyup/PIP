#!/bin/bash

# Get the directory of the script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p results
sudo cgcreate -g cpu:/user
./scripts/cgroup_init.sh

# Define the new application groups
group1=("hotel" "social")
group2=("bert" "cnn" "cnninf")
group3=("fileserver" "tfidvec")

# Run selected apps for a specific time and kill them after 5 minutes
run_benchmark() {
    local selected_apps=("$@")
    for app in "${selected_apps[@]}"; do
        case $app in
            fileserver)
                pushd "$SCRIPT_DIR/benchmark-suites/filebench" > /dev/null
                echo 0 > /proc/sys/kernel/randomize_va_space
                cgexec -g cpu:/user filebench -f ./workloads/fileserver.f &
                popd > /dev/null
                ;;
            hotel)
                pushd "$SCRIPT_DIR/benchmark-suites/DeathStarBench/hotelReservation" > /dev/null
                ./run-cgroup.sh &
                popd > /dev/null
                ;;
            social)
                pushd "$SCRIPT_DIR/benchmark-suites/DeathStarBench/socialNetwork" > /dev/null
                ./run-cgroup.sh &
                popd > /dev/null
                ;;
            cnninf)
                pushd "$SCRIPT_DIR/benchmark-suites/etc" > /dev/null
                cgexec -g cpu:/user python3 cnn-inf.py --duration 300 &
                popd > /dev/null
                ;;
            bert)
                pushd "$SCRIPT_DIR/benchmark-suites/ML-training" > /dev/null
                cgexec -g cpu:/user python3 bert_benchmark.py &
                popd > /dev/null
                ;;
            cnn)
                pushd "$SCRIPT_DIR/benchmark-suites/ML-training" > /dev/null
                cgexec -g cpu:/user python3 cnn2.py &
                popd > /dev/null
                ;;
            tfidvec)
                pushd "$SCRIPT_DIR/benchmark-suites/ML-training" > /dev/null
                cgexec -g cpu:/user python3 tfidvec.py &
                popd > /dev/null
                ;;
        esac
    done

    # Sleep for 5 minutes and then kill all running benchmark processes
    #wrapup period
    ./docker-cgroup.sh
    sleep 300
    for app in "${selected_apps[@]}"; do
        pkill -ef $(basename "${app}")
    done
    pkill -ef filebench

}

# Main loop to repeat process for a specified time (in seconds)
total_duration=1800  # Example: run for 30 minutes
end_time=$((SECONDS + total_duration))
seed=12345
while [ $SECONDS -lt $end_time ]; do
	# Randomly pick 0 or 1 application from each group using the seed

    # Increment the seed for each iteration to ensure variability
    seed=$((seed + 1000))
    # Function to generate a random number from the seed by hashing it
    # Function to generate a random number from the seed by hashing it
    generate_random_seed() {
	    # Generate a pseudo-random number and strip leading zeros
	    echo $((10#$(echo "$1" | md5sum | tr -cd '0-9' | head -c 10)))
    }
    # Generate pseudo-random seeds for each group
    seed_group1=$(generate_random_seed $((seed + 1)))
    seed_group2=$(generate_random_seed $((seed + 2)))
    seed_group3=$(generate_random_seed $((seed + 3)))
    # Randomly pick 0 or 1 application from each group using a unique seed for each group
    selected_apps=()

    # Use unique seed for each group's random selection
    selected_apps+=($(shuf -e "" "${group1[@]}" -n 1 --random-source=<(yes $seed_group1)))  # Group 1
    selected_apps+=($(shuf -e "" "${group2[@]}" -n 1 --random-source=<(yes $seed_group2)))  # Group 2
    selected_apps+=($(shuf -e "" "${group3[@]}" -n 1 --random-source=<(yes $seed_group3)))  # Group 3
    # Randomly pick 0 or 1 application from each group
#    selected_apps=()
#    selected_apps+=($(shuf -e "" "${group1[@]}" -n 1))  # May select 0 or 1
#    selected_apps+=($(shuf -e "" "${group2[@]}" -n 1))  # May select 0 or 1
#    selected_apps+=($(shuf -e "" "${group3[@]}" -n 1))  # May select 0 or 1

    # Filter out empty selections (if none are chosen)
    selected_apps=($(echo "${selected_apps[@]}" | tr -s ' '))

    # Run selected applications (if any were selected)
    if [ ${#selected_apps[@]} -gt 0 ]; then
        run_benchmark "${selected_apps[@]}"
    fi
done

pkill -ef budget_control
pkill -ef powercap

