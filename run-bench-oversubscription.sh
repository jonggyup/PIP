#!/bin/bash
set -euo pipefail
set +x

# ---------- Config ----------
MAX_POWER=300
OVERSUB_LEVELS=(0 10 20 30 40 50 60 70 80)
BUDGET_FILE="./control/budget"

# ---------- Prep ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_DIR="${SCRIPT_DIR}/control"
mkdir -p "${CONTROL_DIR}"
BUDGET_ABS="${CONTROL_DIR}/budget"
OUTPUT_DIR="${SCRIPT_DIR}/results-oversub-fluc"
mkdir -p "${OUTPUT_DIR}"

# Ensure cgroup exists
sudo cgcreate -g cpu:/user || true

# ---------- Helpers ----------
calc_budget() {
    local os_pct="$1"
    awk -v m="$MAX_POWER" -v os="$os_pct" 'BEGIN { printf "%.0f", m/(1+os/100.0) }'
}

set_budget() {
    local budget="$1"
    local bf="${BUDGET_ABS}"
    echo "Setting budget to ${budget}W -> ${bf}"
    printf "%s\n" "$budget" | sudo tee "$bf" >/dev/null
}

kill_controllers() {
    # Kill background python controllers
    pkill -f powercap_CPU_powertrace-final.py 2>/dev/null || true
    pkill -f powercap_CPU_google-ALL-v1.2.py 2>/dev/null || true
}

run_powertrace_logger() {
    local output_tag=$1
    ( cd "$CONTROL_DIR" && sleep 10 && \
      python3 powercap_CPU_powertrace-final.py 1 | tee "${OUTPUT_DIR}/${output_tag}-powertrace.dat" ) &
}

run_UIMD_logger() {
    local output_tag=$1
    ( cd "$CONTROL_DIR" && sleep 10 && \
      python3 powercap_CPU_google-ALL-v1.2.py 1 | tee "${OUTPUT_DIR}/${output_tag}-google.dat" ) &
}

# --- Budget fluctuation (Robust Version) ---
start_budget_fluctuation() {
    local base="$1"       
    local drop_pct="${2:-50}"   
    local period="${3:-20}"     
    local low_dur="${4:-15}"     
    local high_dur=$(( period - low_dur ))
    local low=$(( base * (100 + drop_pct) / 100 ))

    printf "%s\n" "$base" | sudo tee "$BUDGET_ABS" >/dev/null

    (
        while true; do
            sleep "$high_dur" || break
            printf "%s\n" "$low"  | sudo tee "$BUDGET_ABS" >/dev/null || break
            sleep "$low_dur" || break
            printf "%s\n" "$base" | sudo tee "$BUDGET_ABS" >/dev/null || break
        done
    ) &
    FLUCT_PID=$!
    disown $FLUCT_PID
}

stop_budget_fluctuation() {
    local base="$1"
    if [[ -n "${FLUCT_PID:-}" ]]; then
        kill "$FLUCT_PID" 2>/dev/null || true
        wait "$FLUCT_PID" 2>/dev/null || true
    fi
    printf "%s\n" "$base" | sudo tee "$BUDGET_ABS" >/dev/null
    unset FLUCT_PID
}

# Safety trap
trap '
  [[ -n "${FLUCT_PID:-}" ]] && stop_budget_fluctuation "${CURRENT_BUDGET:-${MAX_POWER}}"
  kill_controllers
' EXIT

run_one_baseline() {
    local benchmark_dir=$1
    local benchmark_command=$2
    local output_tag=$3
    local kernel_settings_command=${4:-}

    [[ -n "$kernel_settings_command" ]] && eval "$kernel_settings_command"

    ./control/rapl-recover.sh; ./scripts/cgroup_init.sh
    pushd "$benchmark_dir" >/dev/null
    cgexec -g cpu:/user $benchmark_command &> "${OUTPUT_DIR}/${output_tag}-baseline-result.dat"
    popd >/dev/null
    sleep 10
}

# ---------- Benchmark runners ----------
run_one_with_controllers() {
    local benchmark_dir=$1
    local benchmark_command=$2
    local output_tag=$3
    local kernel_settings_command=${4:-}

    [[ -n "$kernel_settings_command" ]] && eval "$kernel_settings_command"

    # --- UIMD Run ---
    ./control/rapl-recover.sh || true
    ./scripts/cgroup_init.sh || true
    run_UIMD_logger "${output_tag}"
    start_budget_fluctuation "${CURRENT_BUDGET}" "${FLUC}"
    
    pushd "$benchmark_dir" >/dev/null
    # We use '|| true' here so a single benchmark failure doesn't kill the whole sweep
    cgexec -g cpu:/user $benchmark_command &> "${OUTPUT_DIR}/${output_tag}-google-result.dat" || echo "Warning: $output_tag (UIMD) failed"
    popd >/dev/null
    
    stop_budget_fluctuation "${CURRENT_BUDGET}"
    sleep 10
    kill_controllers

    # --- Powertrace Run ---
    ./control/rapl-recover.sh || true
    ./scripts/cgroup_init.sh || true
    run_powertrace_logger "${output_tag}"
    start_budget_fluctuation "${CURRENT_BUDGET}" "${FLUC}"
    
    pushd "$benchmark_dir" >/dev/null
    cgexec -g cpu:/user $benchmark_command &> "${OUTPUT_DIR}/${output_tag}-powertrace-result.dat" || echo "Warning: $output_tag (Powertrace) failed"
    popd >/dev/null
    
    stop_budget_fluctuation "${CURRENT_BUDGET}"
    sleep 10
    kill_controllers
}
<<END
# ---------- Baseline (run once per workload) ----------
# Hotel reservation
run_one_baseline "${SCRIPT_DIR}/benchmark-suites/DeathStarBench/hotelReservation" \
    "./run-cgroup.sh" "hotel"

# Social network
run_one_baseline "${SCRIPT_DIR}/benchmark-suites/DeathStarBench/socialNetwork" \
    "./run-cgroup.sh" "social"

# Fileserver (with kernel randomization off)
run_one_baseline "${SCRIPT_DIR}/benchmark-suites/filebench" \
    "filebench -f ./workloads/fileserver.f" "fileserver" \
    "echo 0 | sudo tee /proc/sys/kernel/randomize_va_space >/dev/null"

# CNN inference
run_one_baseline "${SCRIPT_DIR}/benchmark-suites/etc" \
    "python3 cnninf.py --duration 300" "cnninf"
# BERT training
run_one_baseline "${SCRIPT_DIR}/benchmark-suites/ML-training" \
    "python3 bert.py" "bert"

# CNN training
run_one_baseline "${SCRIPT_DIR}/benchmark-suites/ML-training" \
    "python3 cnn.py" "cnn"

# tfidfvec
run_one_baseline "${SCRIPT_DIR}/benchmark-suites/ML-training" \
    "python3 tfidfvec.py" "tfidfvec"

END
# Social network
run_one_baseline "${SCRIPT_DIR}/benchmark-suites/DeathStarBench/socialNetwork" \
    "./run-cgroup.sh" "social"


# ---------- Sweep over oversubscription levels ----------
for os in "${OVERSUB_LEVELS[@]}"; do
    for fluc in 0 25 50; do
        budget=$(calc_budget "$os")
        CURRENT_BUDGET="$budget"
        FLUC="$fluc"
        
        set_budget "$budget"
        docker volume prune -f || true # Prevent script exit if docker is busy
<<END        
        echo "------------------------------------------------"
        echo "LOG: Starting Loop - OS: $os, Fluctuation: $fluc"
        echo "------------------------------------------------"
        # List of benchmarks to run
        run_one_with_controllers "${SCRIPT_DIR}/benchmark-suites/DeathStarBench/hotelReservation" \
            "./run-cgroup.sh" "hotel-os${os}-f${fluc}"
END
        run_one_with_controllers "${SCRIPT_DIR}/benchmark-suites/DeathStarBench/socialNetwork" \
            "./run-cgroup.sh" "social-os${os}-f${fluc}"
<<END
        run_one_with_controllers "${SCRIPT_DIR}/benchmark-suites/filebench" \
            "filebench -f ./workloads/fileserver.f" \
            "fileserver-os${os}-f${fluc}" \
            "echo 0 | sudo tee /proc/sys/kernel/randomize_va_space >/dev/null"

        run_one_with_controllers "${SCRIPT_DIR}/benchmark-suites/etc" \
            "python3 cnninf.py --duration 300" "cnninf-os${os}-f${fluc}"

        run_one_with_controllers "${SCRIPT_DIR}/benchmark-suites/ML-training" \
            "python3 bert.py" "bert-os${os}-f${fluc}"

        run_one_with_controllers "${SCRIPT_DIR}/benchmark-suites/ML-training" \
            "python3 cnn.py" "cnn-os${os}-f${fluc}"

        run_one_with_controllers "${SCRIPT_DIR}/benchmark-suites/ML-training" \
            "python3 tfidfvec.py" "tfidfvec-os${os}-f${fluc}"
END
        echo "LOG: Finished Loop - OS: $os, Fluctuation: $fluc"
    done
done
echo "Sweep Complete."
