#!/bin/bash
echo 0 > /proc/sys/kernel/randomize_va_space

python3 ../train_test/feature_extract_test.py 1 &

hotelReservation() {
    pushd ../benchmarks/DeathStarBench/hotelReservation
    ./run.sh
    popd
}
socialNetwork() {
    pushd ../benchmarks/DeathStarBench/socialNetwork
    ./run.sh
    popd
}
fileserver() {
    pushd ../benchmarks/filebench/workloads
    filebench -f ./fileserver.f
    popd
}
webserver() {
    pushd ../benchmarks/filebench/workloads
    filebench -f ./webserver.f
    popd
}
varmail() {
    pushd ../benchmarks/filebench/workloads
    filebench -f ./varmail.f
    popd
}
redis() {
    pushd ../benchmarks/redis
    ./run.sh
    popd
}
kcbench() {
    pushd ../benchmarks/kcbench
    ./run.sh
    popd
}


$hotelReservation
sleep 10
$socialNetwork
sleep 10
$fileserver
sleep 10
$varmail
sleep 10
$redis
sleep 10
$kcbench



# Add other applications similarly...
# Array of all functions
app1=('hotelReservation' 'socialNetwork') # Group 1
app2=('fileserver' 'varmail') # Group 2
app3=('redis' 'kcbench') # Group 3
# Time limit in seconds
TIME_LIMIT=3600
end=$((SECONDS+TIME_LIMIT))

# Function to get a random element from an array
get_random_app() {
    local -n array=$1
    if (( ${#array[@]} > 0 )); then
        local random_index=$((RANDOM % ${#array[@]}))
        echo "${array[random_index]}"
    fi
}

while [ $SECONDS -lt $end ]; do
    # Array to store PIDs of the apps started in this iteration
    app_pids=()

    # Process each group in sequence
    for group in "app1" "app2" "app3"; do
        # Select one or zero application from the current group
        if (( RANDOM % 2 )); then
            app=$(get_random_app "$group")
            if [ ! -z "$app" ]; then
                # Run selected app from the current group and store its PID
                echo $app
                $app &
                app_pids+=($!)
                sleep 30
            fi
        fi
    done

    echo "wait start"
    # Wait only for the app(s) started in this iteration
    for pid in "${app_pids[@]}"; do
        wait $pid
    done
    echo "wait finished"

    # Optional: delay before next iteration
    sleep 10
done

pkill -ef feature_extract_test.py
