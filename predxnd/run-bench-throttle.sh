#!/bin/bash

# ==============================================================================
#      Automated Power Prediction Engine Evaluation Script (Enhanced)
# ==============================================================================
#
# Description:
# This script automates the process of evaluating a power prediction engine.
# It systematically tests various combinations of applications, using the same
# pool of apps for both "target" and "background" roles on BOTH the source
# and target machines. This creates a challenging and realistic test environment.
#
# Includes a trap for Ctrl+C to ensure a clean shutdown.
#
# ==============================================================================


# --- Configuration ---
# Set the hostname or IP address of the source and target machines.
# SSH public key authentication should be configured for passwordless access
# from TARGET to SOURCE.
SOURCE_HOST="clnode201.clemson.cloudlab.us"
TARGET_HOST_IP="207" # The IP `send_print.py` should connect to

# Set the directory where this script is located.
# This ensures that relative paths to benchmarks work correctly on both machines,
# assuming an identical directory structure.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Application Definitions ---
# Define the pool of applications to be tested. This array will be used for
# the target app role AND for the background workload role on both machines.
# Each entry is a semicolon-separated string: "name;directory;target_command;background_command"
TARGET_APPS=(
    "fileserver;$SCRIPT_DIR/../benchmark-suites/filebench;./filebench -f ./workloads/fileserver.f;./filebench -f ./workloads/fileserver.f"
#    "hotel;$SCRIPT_DIR/../benchmark-suites/DeathStarBench/hotelReservation;./run-cgroup.sh;./run-bg.sh"
    "social;$SCRIPT_DIR/../benchmark-suites/DeathStarBench/socialNetwork;./run-cgroup.sh;./run-bg.sh"
    "cnn_inf;$SCRIPT_DIR/../benchmark-suites/etc;python3 cnninf.py --duration 300;python3 cnninf.py --duration 300"
    "bert;$SCRIPT_DIR/../benchmark-suites/ML-training;python3 bert_benchmark.py;python3 bert_benchmark.py"
    "cnn_train;$SCRIPT_DIR/../benchmark-suites/ML-training;python3 cnn2.py;python3 cnn2.py"
    "tfidvec;$SCRIPT_DIR/../benchmark-suites/ML-training;python3 tfidvec.py;python3 tfidvec.py"
)

# --- Timing Configuration ---
# Duration for each phase of the experiment. Adjust as needed.
DURATION=60 # seconds
# Grace period for applications to start up before measurement.
STARTUP_WAIT=100 # seconds


# --- Output Directory ---
OUTPUT_DIR="$SCRIPT_DIR/results-evaluation-throttle"
mkdir -p "$OUTPUT_DIR"
echo "Results will be saved in: $OUTPUT_DIR"

# ==============================================================================
#                              HELPER FUNCTIONS
# ==============================================================================

# Function to log messages with a timestamp
log() {
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] - $1"
}

# Function to clean up all relevant processes on the local (target) machine
cleanup_target() {
    log "Cleaning up processes on TARGET machine..."
    # Use sudo to ensure permissions to kill all processes
    sudo pkill -ef merge_pred > /dev/null 2>&1
    sudo pkill -f "filebench|run-cgroup.sh|run-bg.sh|cnninf.py|bert_benchmark.py|cnn2.py|tfidvec.py" > /dev/null 2>&1
    if [ -f /sys/fs/cgroup/user/cgroup.procs ]; then
        xargs -a /sys/fs/cgroup/user/cgroup.procs -r sudo kill -9 > /dev/null 2>&1
    fi
    if [ -f /sys/fs/cgroup/critical/cgroup.procs ]; then
        xargs -a /sys/fs/cgroup/critical/cgroup.procs -r sudo kill -9 > /dev/null 2>&1
    fi
    (cd /users/jonggyu/PowerTrace/benchmark-suites/DeathStarBench/socialNetwork && docker-compose down)
    (cd /users/jonggyu/PowerTrace/benchmark-suites/DeathStarBench/hotelReservation && docker-compose down)
    docker volume rm $(docker volume ls -q)


    log "Target machine cleanup complete."
}

# Function to clean up all relevant processes on the remote (source) machine
cleanup_source() {
    log "Cleaning up processes on SOURCE machine ($SOURCE_HOST)..."
    # Use 'ssh -t' to force pseudo-terminal allocation, which is necessary for 'sudo'
    # to run non-interactively on many systems.
    # A 'heredoc' (<<'EOF') is used to pass the entire script block to the remote host.
    ssh  "$SOURCE_HOST" \
	    "cd '$SCRIPT_DIR' && \
	    sudo ./cleanup.sh" 
}

# This function is called when the script receives an interrupt signal (Ctrl+C)
trap_cleanup() {
    echo # Add a newline for better formatting after ^C
    log "--- INTERRUPT (Ctrl+C) RECEIVED, CLEANING UP ---"

    # Kill the local ssh client first to terminate the connection
    if [[ -n "$SOURCE_SSH_PID" ]]; then
        kill $SOURCE_SSH_PID >/dev/null 2>&1
    fi

    # Run the comprehensive cleanup functions. This is the most reliable way.
    cleanup_target
    cleanup_source

    log "Re-enabling kernel ASLR."
    sudo sysctl -w kernel.randomize_va_space=1 >/dev/null 2>&1

    log "Emergency cleanup complete. Exiting."
    exit 130 # Standard exit code for script termination via Ctrl+C
}

# ==============================================================================
#                                MAIN SCRIPT
# ==============================================================================

# --- Initial Setup ---
# Set the trap for INT (Ctrl+C) and TERM signals to call the cleanup function
trap trap_cleanup INT TERM

sudo sysctl -w kernel.randomize_va_space=0
log "Disabled kernel ASLR."
cleanup_target
cleanup_source


# --- Main Loop ---
# Iterate over each application to act as the TARGET background workload
for bg_target_info in "${TARGET_APPS[@]}"; do
    # Read the name, directory, and the specific BACKGROUND command
    IFS=';' read -r bg_target_name bg_target_dir _ bg_target_command <<< "$bg_target_info"

    # Iterate over each application to act as the SOURCE background workload
    for bg_source_info in "${TARGET_APPS[@]}"; do
        # Read the name, directory, and the specific BACKGROUND command
        IFS=';' read -r bg_source_name bg_source_dir _ bg_source_command <<< "$bg_source_info"

        # Iterate over each application to act as the main TARGET application
        for target_app_info in "${TARGET_APPS[@]}"; do
            # Read the name, directory, and the specific TARGET command
            IFS=';' read -r app_name app_dir app_command _ <<< "$target_app_info"

            # --- Skip redundant tests ---
            if [[ "$app_name" == "$bg_target_name" ]] || [[ "$app_name" == "$bg_source_name" ]]; then
                log "SKIPPING: Test where target app '$app_name' is the same as a background app. Moving to next combo."
                continue
	    fi
	    # Reset PIDs for this new test run to ensure the trap doesn't kill old processes
	    TARGET_BG_PID=""; PRED_PID=""; SOURCE_SSH_PID=""; APP_PID=""; MEASURE_PID=""
	    tg_limit=$(( (RANDOM % 10 + 1) * 10 ))
	    src_limit=$(( (RANDOM % 10 + 1) * 10 ))
	    log "Setting CPU limits: target=${tg_limit}% source=${src_limit}%"
	    ./set_cpus.sh user 20 $tg_limit;

	    log "--- TESTING: App:'$app_name', Target BG:'$bg_target_name', Source BG:'$bg_source_name' ---"

	    RESULT_FILE="$OUTPUT_DIR/app-${app_name}_tgt-bg-${bg_target_name}-${tg_limit}_src-bg-${bg_source_name}-${src_limit}.log"
	    {
                echo "## Test Configuration"
                echo "## Target App: $app_name"
                echo "## Target BG:  $bg_target_name"
                echo "## Source BG:  $bg_source_name"
                echo "## Timestamp:  $(date)"
                echo "--------------------------------------------------------"
            } > "$RESULT_FILE"

            # --- 1. PREDICTION PHASE ---
            log "[PHASE 1/2] Prediction for $app_name"
            echo -e "\n--- PREDICTION RESULTS ---" >> "$RESULT_FILE"

            log "Starting background workload '$bg_target_name' on TARGET."
            (cd "$bg_target_dir" && cgexec -g cpu:critical $bg_target_command) &
            TARGET_BG_PID=$!

            log "Starting prediction engine 'merge_pred.py' on TARGET."
            # Use nohup to make the process immune to hangups, -u for unbuffered output,
            # and redirect stdin from /dev/null to prevent terminal interaction.
            nohup python3 -u "./merge_pred_throttle.py" user < /dev/null >> "$RESULT_FILE" 2>&1 &
            PRED_PID=$!

            log "Starting workloads on SOURCE ($SOURCE_HOST)."
            # This SSH session will run in the background. The 'while true' loop makes send_print.py resilient.
            ssh "$SOURCE_HOST" "
                echo '[REMOTE] Starting source background workload: $bg_source_name';
                # The command variable MUST NOT be quoted here, so the remote shell can split it into a command and arguments for cgexec.
                (cd '$bg_source_dir' && exec cgexec -g cpu:critical $bg_source_command) &

                echo '[REMOTE] Starting target app: $app_name';
                # This is the line that was fixed. The quotes around $app_command were removed.
                (cd '$app_dir' && exec cgexec -g cpu:/user $app_command) &

                echo '[REMOTE] Waiting for apps to initialize on source...';
                sleep $STARTUP_WAIT;

                # Loop to make the metric sender resilient to network drops
                while true; do
                    echo '[REMOTE] Starting/Restarting send_print_throttle.py...';
                    cd '$SCRIPT_DIR';
                    ./set_cpus.sh user 20 $src_limit;
                    python3 -u './send_print_throttle.py' user $TARGET_HOST_IP;
                    echo '[REMOTE] send_print_throttle.py exited. Restarting in 1 second...';
                    sleep 1;
                done                
            " &

            SOURCE_SSH_PID=$!

            sleep $STARTUP_WAIT

            log "Prediction phase running for $DURATION seconds..."
            sleep "$DURATION"

            # --- Cleanup after Prediction Phase ---
            log "Stopping prediction phase processes."
            kill $PRED_PID $TARGET_BG_PID > /dev/null 2>&1
            wait $PRED_PID $TARGET_BG_PID 2>/dev/null
            
            log "Terminating remote SSH session and workloads..."
            kill $SOURCE_SSH_PID > /dev/null 2>&1
            wait $SOURCE_SSH_PID 2>/dev/null

            cleanup_source
	    cleanup_target
            log "[PHASE 1/2] Prediction phase complete."
            sleep 5


            # --- 2. GROUND TRUTH PHASE ---
            log "[PHASE 2/2] Ground Truth for $app_name"
            echo -e "\n--- GROUND TRUTH RESULTS ---" >> "$RESULT_FILE"

            log "Starting background workload '$bg_target_name' on TARGET."
            (cd "$bg_target_dir" && cgexec -g cpu:critical $bg_target_command) &
            TARGET_BG_PID=$!

            log "Starting target app '$app_name' on TARGET."
            (cd "$app_dir" && cgexec -g cpu:/user $app_command) &
            APP_PID=$!

            log "Allowing apps to warm up for $STARTUP_WAIT seconds..."
            sleep "$STARTUP_WAIT"

            log "Measuring ground truth power for $DURATION seconds..."
            # Use nohup here as well for consistency and robustness.
	    nohup python3 -u "./merge_pred_throttle.py" user < /dev/null >> "$RESULT_FILE" 2>&1 &

            MEASURE_PID=$!

            sleep "$DURATION"

            # --- Cleanup after Ground Truth Phase ---
            log "Stopping ground truth phase processes."
            kill $MEASURE_PID $APP_PID $TARGET_BG_PID > /dev/null 2>&1
            wait $MEASURE_PID $APP_PID $TARGET_BG_PID 2>/dev/null
            cleanup_target

            log "[PHASE 2/2] Ground truth phase complete."
            echo "========================================================" >> "$RESULT_FILE"
            log "--- Test complete. Results are in $RESULT_FILE ---"
            sleep 10

        done
    done
done

# --- Final Cleanup on Normal Exit ---
log "All tests completed successfully."
# Remove the trap so the script can exit normally
trap - INT TERM
sudo sysctl -w kernel.randomize_va_space=1
log "Re-enabled kernel ASLR."

echo "Evaluation script finished. All results are in the '$OUTPUT_DIR' directory."

