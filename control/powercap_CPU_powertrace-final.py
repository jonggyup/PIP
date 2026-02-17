#!/usr/bin/env python3
"""
Power Capping Controller

This program dynamically adjusts CPU bandwidth limits for two cgroups (“user” and “critical”)
so that the measured CPU power meets a target power budget. It uses an ML model (CatBoost)
to predict power based on a modified feature map that simulates CPU throttling.
If user cgroup throttling alone does not meet the budget, the critical cgroup is also throttled.

A calibration process is added: a global calibration_offset is updated (using an EWMA)
based on the difference between actual and predicted power. When actual power is below target,
the controller increases bandwidth. For small gaps (<10 Watts) it increases by a baby step,
but for larger gaps it uses the ML model to “recover” immediately by finding the highest throttle
(for the eligible cgroup) whose prediction is at or below the target.
"""

import os
import sys
import time
import signal
import subprocess
import threading
import re
import warnings
from datetime import datetime
import math
import numpy as np
import joblib

warnings.filterwarnings("ignore", category=UserWarning)

# -----------------------------
# Global Configuration & State
# -----------------------------
MODEL_PATH = "../MLs/CatBoost_model.joblib"
TOPOLOGY_FILE = "../estimation/topol_metric_size.dat"
IDLE_FILE = "../data/idle.dat"
BUDGET_FILE = "./budget"

# Tolerance in Watts for slight violations (used in strict recovery)
TOLERANCE = 5
ceiling = 0.03 # is adjusted based on prediction errors

# Global topology/metric parameters (set in load_topology_metrics)
topol_size = 0
direct_metrics_size = 0
max_freq = 0
core_info_count = 0
num_cores = os.cpu_count()
last_ratio = 1

# Global state for CPU throttling and calibration
current_bandwidth = 100    # For user cgroup throttle (%)
current_bandwidth2 = 100   # For critical cgroup throttle (%)
adjustment_ratio = {}        # Per-metric adjustment ratios
predictive_feature_map = []  # Last predicted feature map (list of floats/strings)
actual_power = 0
prev_prediction = 0
prev = 0                   # 1 for strict, 2 for relaxed
retry = 0
start_time = datetime.now()

# --- Calibration globals ---
calibration_offset = 0     # Offset to correct ML prediction error
smoothing_cal = 0.8        # EWMA smoothing factor for calibration
used_map = False

# Start in energy-only mode; flip to full mode once we exceed budget.
full_mode = False

# -----------------------------
# Utility Functions
# -----------------------------
def load_topology_metrics():
    """Load topology metrics (feature map sizes and max frequency) from file."""
    global topol_size, direct_metrics_size, max_freq, core_info_count
    try:
        with open(TOPOLOGY_FILE, 'r') as file:
            data = file.readline().split()
            topol_size = int(data[0])
            direct_metrics_size = int(data[1])
            max_freq = int(data[2])
            core_info_count = int(topol_size / num_cores) if num_cores else 0
    except Exception as e:
        print(f"Error loading topology metrics: {e}")
        topol_size, direct_metrics_size, max_freq, core_info_count = 0, 0, 0, 0

def read_cpuset(path):
    """Read available cores from a given cpuset file and expand ranges."""
    cores = []
    try:
        with open(path, 'r') as f:
            cpuset_str = f.read().strip()
        if cpuset_str:
            for part in cpuset_str.split(','):
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    cores.extend(range(start, end + 1))
                else:
                    cores.append(int(part))
        else:
            print(f"[DEBUG] No CPUs listed in {path}")
    except Exception as e:
        print(f"[ERROR] Failed to read from {path}: {e}")
    return sorted(cores)

def get_user_cores():
    """
    Get available cores for the 'user' cgroup.
    First try the effective file; if too few cores are returned, fallback to the non-effective file.
    """
    cores = read_cpuset('/sys/fs/cgroup/user/cpuset.cpus.effective')
    if len(cores) < 2:
        cores = read_cpuset('/sys/fs/cgroup/user/cpuset.cpus')
    return cores

def get_critical_cores():
    """
    Get available cores for the 'critical' cgroup.
    First try the effective file; if it returns unexpectedly few cores, fallback to the non-effective file.
    """
    cores = read_cpuset('/sys/fs/cgroup/critical/cpuset.cpus.effective')
    if len(cores) < (os.cpu_count() // 2):
        cores = read_cpuset('/sys/fs/cgroup/critical/cpuset.cpus')
    return cores

def read_cpu_max(cgroup):
    """
    Read the current cpu.max quota for a given cgroup and compute the throttle percentage.
    Throttle = (quota / (100000 * number_of_cores)) * 100.
    """
    path = os.path.join('/sys/fs/cgroup', cgroup, 'cpu.max')
    try:
        with open(path, 'r') as f:
            content = f.read().strip()
        parts = content.split()
        if len(parts) >= 2:
            quota = int(parts[0])
            cores = read_cpuset(f'/sys/fs/cgroup/{cgroup}/cpuset.cpus.effective')
            if not cores:
                cores = read_cpuset(f'/sys/fs/cgroup/{cgroup}/cpuset.cpus')
            if cores:
                throttle = int((quota / (100000 * len(cores))) * 100)
                return throttle
    except Exception as e:
        print(f"Error reading cpu.max for {cgroup}: {e}")
    return None

def set_cpu_limit(cgroup, throttle, available_cores):
    """
    Set the CPU bandwidth limit (cpu.max) for a given cgroup.
    
    The quota is computed as: quota = 100000 * (number of cores in cgroup) * (throttle / 100).
    After writing the new value, re-read the file to update the corresponding global throttle variable.
    """
    cgroup_path = os.path.join('/sys/fs/cgroup', cgroup)
    num_avail = len(available_cores)
    conf_str = f"{int(100000 * num_avail * throttle / 100)} 100000"
    try:
        with open(os.path.join(cgroup_path, 'cpu.max'), 'w') as f:
            f.write(conf_str)
        new_throttle = read_cpu_max(cgroup)
        if new_throttle is not None:
            if cgroup == "critical":
                global current_bandwidth2
                current_bandwidth2 = new_throttle
            elif cgroup == "user":
                global current_bandwidth
                current_bandwidth = new_throttle
    except Exception as e:
        print(f"Error setting CPU max for {cgroup}: {e}")

def calculate_cpu_power():
    """
    Run 'perf stat' to calculate CPU power consumption (Joules per second).
    """
    output = subprocess.run(
        ['perf', 'stat', '-e', 'power/energy-pkg/', 'sleep', '1'],
        stderr=subprocess.PIPE,
        text=True
    ).stderr
    pkg_match = re.search(r'(\d+\.\d+)\s+Joules\s+power/energy-pkg/', output)
    time_match = re.search(r'(\d+\.\d+)\s+seconds\s+time\s+elapsed', output)
    if pkg_match and time_match:
        pkg_power = float(pkg_match.group(1))
        time_elapsed = float(time_match.group(1))
        return pkg_power / time_elapsed
    else:
        raise ValueError("Failed to extract power or time from perf output.")

def run_perf_metrics():
    """
    Run perf stat to collect metric data and write to file.
    """
    try:
        metrics_list = [
        "cpu_clk_unhalted.ref_tsc", "cpu_clk_unhalted.thread_p", "LLC-load-misses", "instructions", "cpu-cycles", "cpu-clock", "cache-misses","cache-references",
        "branches", "branch-misses", "bus-cycles", "ref-cycles",
        "context-switches", "cpu-migrations", "page-faults",
        "L1-dcache-loads", "L1-dcache-load-misses", "L1-icache-load-misses",
        "LLC-loads", "dTLB-loads", "dTLB-load-misses",
        "msr/aperf/", "msr/mperf/", "msr/pperf/", "fp_arith_inst_retired.scalar_double",
        "fp_arith_inst_retired.scalar_single", "fp_arith_inst_retired.128b_packed_double",
        "fp_arith_inst_retired.128b_packed_single", "fp_arith_inst_retired.256b_packed_double",
        "fp_arith_inst_retired.256b_packed_single", "fp_arith_inst_retired.512b_packed_double"
        ]

        supported = subprocess.run(['perf', 'list'], capture_output=True, text=True).stdout
        filtered = [m for m in metrics_list if m in supported]
        metrics_str = ",".join(filtered)
        command = f'perf stat -e {metrics_str} -a -o ./perf_metrics.dat python3 ../estimation/coretemp_simp.py 1'
        subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception as e:
        print(f"Error running perf metrics: {e}")

def run_perf_energy():
    """Run perf stat to collect energy data."""
    try:
        command = 'perf stat -e power/energy-pkg/ -a -o ./perf_energy.dat sleep 1'
        subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception as e:
        print(f"Error running perf energy: {e}")

def parse_perf_metrics():
    try:
        perf_file_path = './perf_metrics.dat'
        core_temp_file_path = './core_temp.dat'

        # Read the perf_metrics.dat file
        with open(perf_file_path, 'r') as perf_file:
            perf_output = perf_file.read()

        # Split the perf file content into lines for processing
        perf_output_lines = perf_output.split('\n')

        # List to store the extracted values from perf_metrics.dat
        perf_extracted_values = []

        # Extract elapsed time from the file
        time_match = re.search(r'(\d+\.\d+)\s+seconds\s+time\s+elapsed', perf_output)
        if not time_match:
            raise ValueError("Elapsed time not found in perf_metrics.dat")
        time_elapsed = float(time_match.group(1))

        for line in perf_output_lines:
            # Stop processing further lines once the marker is reached.
            if "seconds time elapsed" in line:
                break
            # Match lines that start with numbers and a metric name
            match = re.search(r'^ *([\d,\.]+)\s+([a-zA-Z\-/]+)', line)
            if match:
                # Extract the numeric value, remove commas and normalize by elapsed time
                value = float(match.group(1).replace(',', ''))
                value = value / time_elapsed
                formatted_value = float(f"{value:.2f}")
                perf_extracted_values.append(formatted_value)

        # Read the core_temp.dat file
        with open(core_temp_file_path, 'r') as core_temp_file:
            core_temp_output = core_temp_file.read()

        # Process core_temp file content and collect values
        core_temp_values = []
        for line in core_temp_output.split('\n'):
            if line.strip():
                value = float(line.strip())
                core_temp_values.append(value)

        # Combine core temperature and perf extracted values
        combined_values = core_temp_values + perf_extracted_values

        return combined_values
    except Exception as e:
        return None, f"Error: {str(e)}"

def parse_power_consumption():
    try:
        file_path = './perf_energy.dat'
        with open(file_path, 'r') as file:
            perf_output = file.read()

        # Extract power and time data
        pkg_energy = float(re.search(r'(\d+\.\d+)\s+Joules\s+power/energy-pkg/', perf_output).group(1))
#        mem_energy = float(re.search(r'(\d+\.\d+)\s+Joules\s+power/energy-ram/', perf_output).group(1))
        time_elapsed = float(re.search(r'(\d+\.\d+)\s+seconds\s+time\s+elapsed', perf_output).group(1))
        calc_result = float(f"{(pkg_energy) / time_elapsed:.2f}")

        return calc_result
    except Exception as e:
        return None, f"Error: {str(e)}"

def parse_cpu_data(output, cpu_metrics):
    parsed_data = []
    tmp_data = []
    c0_index = None
    lines = output.split('\n')

    for line in lines:
        elements = [e.strip() for e in line.strip().split("|") if e.strip()]

        if not elements:
            continue

        # Detect header line containing 'C0'
        if c0_index is None and 'C0' in elements:
            c0_index = elements.index('C0')
            continue

        if c0_index is not None and len(elements) > c0_index:
            # Get all columns from C0 onwards for each data row
            tmp_data.append(elements[c0_index:])

    # Flatten and convert to float
    if tmp_data:
        flat = [item for sublist in tmp_data for item in sublist]
        parsed_data = [float(x) for x in flat]
        parsed_data.extend(cpu_metrics)

    return parsed_data

# -----------------------------
# Updated Metric Adjustment Functions
# -----------------------------
def update_feature_map_generic(feature_map, future_throttle, direct_size, available_cores, group):
    """
    Adjusts each metric in feature_map based on the ratio between the candidate (future_throttle)
    and the current throttle for the given cgroup, taking per-metric sensitivity into account.
    """
    global adjustment_ratio, current_bandwidth, current_bandwidth2, num_cores
    # Select the appropriate current bandwidth depending on the group.
    if group == "critical":
        curr_bandwidth = current_bandwidth2
    else:
        curr_bandwidth = current_bandwidth

    avail_ratio = available_cores / num_cores
    ratio = future_throttle / curr_bandwidth  # future/current throttle ratio
    for i in range(direct_size, len(feature_map)):
        base = float(feature_map[i])
        sensitivity = adjustment_ratio.get(i, 0.0)
        simulated = base * ((1 - avail_ratio) + avail_ratio * (1 + sensitivity * (ratio - 1)))
        feature_map[i] = simulated
    return feature_map

def update_adjustment(predictive_map, actual_map, direct_size, smoothing=0.8):
    """
    Updates per-metric sensitivity stored in adjustment_ratio.
    For each metric, sensitivity = (actual/predicted - 1), then smoothed over time.
    """
    global adjustment_ratio
    for i in range(direct_size, len(actual_map)):
        pred = float(predictive_map[i])
        if pred != 0:
            new_sens = (float(actual_map[i]) / pred)
            if i in adjustment_ratio:
                adjustment_ratio[i] = smoothing * adjustment_ratio[i] + (1 - smoothing) * new_sens
            else:
                adjustment_ratio[i] = new_sens
        else:
            adjustment_ratio[i] = 0.0
#    print(adjustment_ratio)
# -----------------------------
# New Recovery Function: recover_bandwidth
# -----------------------------
def recover_bandwidth(feature_map, group):
    """
    For the given group ("critical" or "user"), iterate from 100 down to current throttle +1.
    Return the highest throttle value for which (ML prediction + calibration_offset) is <= target_power.
    """
    global used_map
    if group == "critical":
        cpus = get_critical_cores()
        current_val = current_bandwidth2
    else:
        cpus = get_user_cores()
        current_val = current_bandwidth
    model = joblib.load(MODEL_PATH)
    core_count = 0
    for candidate in range(100, current_val, -5):
        new_map = feature_map.copy()
        for core in cpus:
            idx = core * core_info_count
            if idx < topol_size:
                if float(new_map[idx]) >= current_val:
                    new_map[idx] = max(float(new_map[idx]), candidate)
                    core_count = core_count + 1
                    new_map[idx + 1] = 100 - candidate
                    new_map[idx + 5] = 100 - candidate
                    new_map[idx + 2] = str(max_freq)
        new_map = update_feature_map_generic(new_map, candidate, direct_metrics_size, core_count, group)
        features_array = np.array(new_map).reshape(1, -1)
        prediction = float(model.predict(features_array)[0]) + calibration_offset
        prev_prediction = prediction
        predictive_feature_map = new_map
#        print(f"prediction {prediction} | candidate {candidate}")
        if prediction <= target_power + calibration_offset:
#            print(f"Debug: recover | target {target_power} | group {group} | prediction {prediction} | recover {candidate} | calibration {calibration_offset}", flush=True)
            used_map = True
            return candidate
    return current_val

def predict_featuremap(feature_map, group, candidate):
    global used_map
    used_map = True

    if group == "critical":
        cpus = get_critical_cores()
        current_val = current_bandwidth2
    else:
        cpus = get_user_cores()
        current_val = current_bandwidth
    model = joblib.load(MODEL_PATH)
    core_count=0
    throttle = candidate
    modified_map = feature_map.copy()
    if throttle > current_val:
        for core in cpus:
            idx = core * core_info_count
            if idx < topol_size:
                if float(modified_map[idx]) >= current_bandwidth:
                    modified_map[idx] = max(float(modified_map[idx]), throttle)
                    core_count = core_count + 1
                    modified_map[idx + 1] = 100 - throttle
                    modified_map[idx + 5] = 100 - throttle
                    modified_map[idx + 2] = str(max_freq)
    else:
        for core in cpus:
            idx = core * core_info_count
            if idx < topol_size:
                modified_map[idx] = min(float(modified_map[idx]), throttle)
                if idx + 1 < topol_size and float(modified_map[idx + 1]) < 100 - throttle:
                    core_count = core_count + 1
                    modified_map[idx + 1] = 100 - throttle
                if idx + 5 < topol_size and float(modified_map[idx + 5]) < 100 - throttle:
                    modified_map[idx + 5] = 100 - throttle
                    modified_map[idx + 2] = str(max_freq)

    modified_map = update_feature_map_generic(modified_map, candidate, direct_metrics_size, core_count, group)
    features_array = np.array(modified_map).reshape(1, -1)
    prediction = float(model.predict(features_array)[0]) + calibration_offset
    prev_prediction = prediction
    predictive_feature_map = modified_map

# -----------------------------
# New Function: Increase Bandwidth (Simplified Recovery)
# -----------------------------
def increase_bandwidth(feature_map, gap):
    """
    Increase bandwidth aggressively when actual power is below target.
    
    The critical cgroup is given priority. For critical, if the gap is small (<10W),
    a baby step (+1%) is taken; otherwise, the ML prediction (via recover_bandwidth) is used.
    If the ML recovery returns the current throttle (likely due to calibration error),
    then a fallback increment by 5 is forced.
    Only if the critical throttle is already 100 is the user throttle adjusted.
    
    Returns updated (current_bandwidth, current_bandwidth2).
    """
    global current_bandwidth, current_bandwidth2, used_map
    used_map = False
    if current_bandwidth2 < 100:
        current_bandwidth = 1
        set_cpu_limit("user",current_bandwidth , get_user_cores())
        predict_featuremap(feature_map, "user", current_bandwidth)

        if gap < 10:
#            print("Debug: babystep increase on critical")
            new_val = current_bandwidth2 + 1
        else:
#            print("Debug: high gap ML recovery for critical")
            candidate = recover_bandwidth(feature_map, "critical")
            if candidate == current_bandwidth2 or current_bandwidth2 < 10:
                new_val = min(current_bandwidth2 + 5, 100)
#                print(f"Debug: fallback increment on critical to {new_val} | candidate {candidate}")
            else:
                new_val = candidate
        new_val = min(new_val, 100)
        set_cpu_limit("critical", new_val, get_critical_cores())
        predict_featuremap(feature_map, "critical", new_val)
        current_bandwidth2 = new_val
    elif current_bandwidth < 100:
        if gap < 10:
 #           print("Debug: babystep on user")
            new_val = current_bandwidth + 1
        else:
#            print("Debug: high gap ML recovery for user")
            candidate = recover_bandwidth(feature_map, "user")
            if candidate == current_bandwidth or current_bandwidth < 10:
                new_val = min(current_bandwidth + 5, 100)
#                print(f"Debug: fallback increment on user to {new_val} | candidate {candidate}")
            else:
                new_val = candidate
        new_val = min(new_val, 100)
        set_cpu_limit("user", new_val, get_user_cores())
        predict_featuremap(feature_map, "user", new_val)
        current_bandwidth = new_val
    return current_bandwidth, current_bandwidth2

# -----------------------------
# Power Capping Strategies
# -----------------------------

def critical_power_capping(feature_map):
    """
    Apply throttling to the critical cgroup if user throttling alone cannot meet the budget.
    Uses calibrated predictions for decision.
    """
    global current_bandwidth2, prev_prediction, retry, predictive_feature_map, prev, calibration_offset, smoothing_cal, actual_power
    try:
        with open(IDLE_FILE, 'r') as f:
            _ = [float(x) for x in f.read().split(',') if x.strip()]
    except Exception as e:
        print(f"Error reading idle data: {e}")
    model = joblib.load(MODEL_PATH)
    if prev == 1:
        _ = max(0, current_bandwidth2 - retry * 10)
        retry += 1
    else:
        _ = 100
        retry = 0
    selected_throttle = 1
    if current_bandwidth2 < 5:
        current_bandwdith2 = 5
    success = False
    critical_cores = get_critical_cores()
    core_count = 0
    for throttle in range(current_bandwidth2, 0, -5):
        modified_map = feature_map.copy()
        for core in critical_cores:
            idx = core * core_info_count
            if idx < topol_size:
                modified_map[idx] = min(float(modified_map[idx]), throttle)
                if idx + 1 < topol_size and float(modified_map[idx + 1]) < 100 - throttle:
                    core_count = core_count + 1
                    modified_map[idx + 1] = 100 - throttle
                if idx + 5 < topol_size and float(modified_map[idx + 5]) < 100 - throttle:
                    modified_map[idx + 5] = 100 - throttle
                    modified_map[idx + 2] = str(max_freq)
        modified_map = update_feature_map_generic(modified_map, throttle, direct_metrics_size, core_count, 'critical')
        features_array = np.array(modified_map).reshape(1, -1)
        prediction = float(model.predict(features_array)[0])
        if (prediction + calibration_offset) <= float(target_power):
            selected_throttle = throttle
            success = True
            break
    set_cpu_limit('critical', selected_throttle, critical_cores)
    predictive_feature_map = modified_map
    prev_prediction = prediction
#    print(f"Debug: critical {int((datetime.now()-start_time).total_seconds())} | target {target_power} | critical throttle {selected_throttle} | prediction {prediction + calibration_offset:.2f}", flush=True)
    return selected_throttle

def strict_power_capping(feature_map):
    """
    When measured power is above target, apply a strict throttling policy.
    Uses calibrated predictions to decide on the throttle.
    For small violations, if the user throttle is above 1, reduce it by 5.
    If user throttle is already 1 (or 0), then reduce the critical throttle by 5.
    """
    global current_bandwidth, current_bandwidth2, prev_prediction, retry, predictive_feature_map, prev, calibration_offset, smoothing_cal, actual_power
#    update_adjustment(predictive_feature_map, feature_map, direct_metrics_size)
#    print(len(feature_map))
    if actual_power - target_power < TOLERANCE:
        if current_bandwidth > 1:
            if actual_power < target_power:
                new_throttle = max(current_bandwidth - 5, 1)
            else:
                new_throttle = max(current_bandwidth - 10, 1)
            set_cpu_limit('user', new_throttle, get_user_cores())
            current_bandwidth = new_throttle
#            print(f"Debug: strict (baby step) | target {target_power} | user throttle {new_throttle}", flush=True)
            return new_throttle, current_bandwidth2
        else:
            if current_bandwidth2 > 1:
                if actual_power < target_power:
                    new_throttle = max(current_bandwidth2 - 5, 1)
                else:
                    new_throttle = max(current_bandwidth2 - 10, 1)
                set_cpu_limit('critical', new_throttle, get_critical_cores())
                current_bandwidth2 = new_throttle
#                print(f"Debug: strict (baby step) | target {target_power} | critical throttle {new_throttle}", flush=True)
                return current_bandwidth, new_throttle
            else:
#                print(f"Debug: strict (baby step) | target {target_power} | both throttles at minimum", flush=True)
                return current_bandwidth, current_bandwidth2
    if prev == 1:
        _ = max(0, current_bandwidth - retry * 10)
        retry += 1
    else:
        _ = 100
        retry = 0
    selected_throttle = 1
    success = False
    user_cores = get_user_cores()
    core_count = 0
    model = joblib.load(MODEL_PATH)
    modified_map = feature_map.copy()
    if current_bandwidth > 5:
        for throttle in range(current_bandwidth-5, 0, -5):
            modified_map = feature_map.copy()
            for core in user_cores:
                idx = core * core_info_count
                if idx < topol_size:
                    modified_map[idx] = min(float(modified_map[idx]), throttle)
                    if idx + 1 < topol_size and float(modified_map[idx + 1]) < 100 - throttle:
                        core_count = core_count + 1
                        modified_map[idx + 1] = 100 - throttle
                    if idx + 5 < topol_size and float(modified_map[idx + 5]) < 100 - throttle:
                        modified_map[idx + 5] = 100 - throttle
                        modified_map[idx + 2] = str(max_freq)

            modified_map = update_feature_map_generic(modified_map, throttle, direct_metrics_size, core_count, 'user')
            features_array = np.array(modified_map).reshape(1, -1)
            prediction = float(model.predict(features_array)[0])
            if (prediction + calibration_offset) <= float(target_power):
                selected_throttle = throttle
                success = True
                predictive_feature_map = modified_map
                prev_prediction = prediction
                break

    if not success:
        modified_map = feature_map.copy()
        selected_throttle = 1
        for core in user_cores:
            idx = core * core_info_count
            if idx < topol_size:
                modified_map[idx] = str(selected_throttle)
                modified_map[idx + 1] = str(100 - selected_throttle)
                modified_map[idx + 5] = str(100 - selected_throttle)
                modified_map[idx + 2] = str(max_freq)

        crit_throttle = critical_power_capping(modified_map)
#        set_cpu_limit('critical', crit_throttle, get_critical_cores())

    set_cpu_limit('user', selected_throttle, user_cores)
#    print(f"Debug: strict {int((datetime.now()-start_time).total_seconds())} | target {target_power} | user throttle {selected_throttle} | prediction {prediction + calibration_offset:.2f}", flush=True)
    return selected_throttle, current_bandwidth2


# -----------------------------
# Main Control Loop
# -----------------------------
def run_stress_test():
    """
    Start energy-only. Once actual power is >= target (within 'ceiling'), switch to the
    original perf+energy control loop for the rest of the run.
    """
    global actual_power, current_bandwidth, current_bandwidth2, prev, retry
    global predictive_feature_map, target_power, calibration_offset, used_map, full_mode

    calibration_offset = 0
    current_bandwidth = 100  # Starting bandwidth value
    sample_sec = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0

    while True:
        # --- Read budget ---
        try:
            with open(BUDGET_FILE, 'r') as f:
                target_power = int(f.readline().strip())
        except Exception as e:
            print(f"Error reading power or budget: {e}", flush=True)
            time.sleep(sample_sec)
            continue

        if not full_mode:
            # --------------------------
            # ENERGY-ONLY SAMPLING MODE
            # --------------------------
            energy_thread = threading.Thread(target=run_perf_energy)
            energy_thread.start()
            # emulate the original sampling window
            time.sleep(sample_sec)
            energy_thread.join()

            try:
                actual_power = parse_power_consumption()
                timestamp = int((datetime.now() - start_time).total_seconds())
                # keep the same print format (bandwidths unchanged here)
                print(f"{timestamp} | {current_bandwidth} | {current_bandwidth2} | {target_power} | {actual_power:.0f}", flush=True)
            except Exception as e:
                print(f"Skipping iteration due to energy parse error: {e}", flush=True)
                continue

            # Flip to full mode once we are beyond/near the budget
            if actual_power >= target_power * (1 - ceiling):
                full_mode = True

            # stay in energy-only until the threshold is hit
            continue

        # ------------------------------------
        # FULL MODE: ORIGINAL PERF+ENERGY FLOW
        # ------------------------------------
        perf_thread = threading.Thread(target=run_perf_metrics)
        energy_thread = threading.Thread(target=run_perf_energy)
        perf_thread.start()
        energy_thread.start()

        command = f'cpupower monitor sleep {sample_sec}'
        proc = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        perf_thread.join()
        energy_thread.join()

        try:
            perf_metrics = parse_perf_metrics()
            actual_power = parse_power_consumption()
            timestamp = int((datetime.now() - start_time).total_seconds())
            print(f"{timestamp} | {current_bandwidth} | {current_bandwidth2} | {target_power} | {actual_power:.0f}", flush=True)

            metrics_data = parse_cpu_data(proc.stdout, perf_metrics)
            if not predictive_feature_map:
                predictive_feature_map = metrics_data.copy()
        except Exception as e:
            print(f"Skipping iteration due to perf metrics error: {e}", flush=True)
            continue

        if used_map is True:
            calibration_offset = smoothing_cal * calibration_offset + (1 - smoothing_cal) * (actual_power - prev_prediction)
            update_adjustment(predictive_feature_map, metrics_data, direct_metrics_size)

        used_map = False

        # Adjust throttling based on measured power (unchanged logic)
        if actual_power >= target_power * (1 - ceiling):
            current_bandwidth, current_bandwidth2 = strict_power_capping(metrics_data)
            prev = 1
            retry += 1
            used_map = True
        elif actual_power < target_power * (1 - ceiling * 2):
            gap = target_power - actual_power
            current_bandwidth, current_bandwidth2 = increase_bandwidth(metrics_data, gap)
            prev = 0
        else:
            retry = 0
            prev = 0
            used_map = False

def signal_handler(sig, frame):
    if os.path.exists("perf-training.dat"):
        os.remove("perf-training.dat")
    exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    load_topology_metrics()
    get_user_cores()
    get_critical_cores()
    while True:
        stress_thread = threading.Thread(target=run_stress_test)
        stress_thread.start()
        stress_thread.join()

