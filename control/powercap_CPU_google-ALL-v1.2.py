import subprocess
import os
import time
import sys
import re
import signal
from datetime import datetime
import random

# --- Configuration & State ---

# Default period for control loop
DEFAULT_PERIOD_SECONDS = 1.0

# Cgroup names
USER_CGROUP = 'user'
CRITICAL_CGROUP = 'critical'

# --- Constants from Paper (Table 2 & Implementation Details) ---
HARD_MULTIPLIER = 0.01   # Drastic reduction multiplier (Power > High Threshold)
SOFT_MULTIPLIER = 0.75   # Moderate reduction multiplier (Low < Power <= High)
THROTTLE_MIN = 1.0       # Minimum CPU bandwidth cap (1%)
THROTTLE_MAX = 100.0     # Maximum CPU bandwidth cap (100%)
HIGH_THRESHOLD = 0.98    # 98% of power limit
LOW_THRESHOLD = 0.96     # 96% of power limit

# --- RUMD Randomized Unthrottling Parameters ---
UNTHROTTLE_WAIT_MIN = 1  # 1s (Paper-aligned min wait)
UNTHROTTLE_WAIT_MAX = 10   # 10s  (Paper-aligned max wait)
UNTHROTTLE_STEP = 5.0       # 5% recovery increment

# --- Global State Variables ---
current_bandwidth_user = THROTTLE_MAX      
current_bandwidth_critical = THROTTLE_MAX  
target_power = 100.0               
start_time = None                    
available_cores_user = []            
available_cores_critical = []        
throttling_active_state = False      
next_unthrottle_time = 0.0  # Tracks the randomized timeout expiration

# --- Cgroup Core Discovery ---

def get_cgroup_available_cores(cgroup_name):
    """Retrieves a list of effective CPU cores for a given cgroup."""
    global available_cores_user, available_cores_critical
    cores = []
    cpuset_path = f'/sys/fs/cgroup/{cgroup_name}/cpuset.cpus.effective'
    try:
        with open(cpuset_path, 'r') as f:
            cpuset_cpus = f.read().strip()
        if cpuset_cpus:
            parts = cpuset_cpus.split(',')
            for part in parts:
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    cores.extend(range(start, end + 1))
                else:
                    cores.append(int(part))
    except FileNotFoundError:
         cores = list(range(os.cpu_count()))
    except Exception as e:
        cores = list(range(os.cpu_count()))

    if cgroup_name == USER_CGROUP:
        available_cores_user = sorted(cores)
    elif cgroup_name == CRITICAL_CGROUP:
        available_cores_critical = sorted(cores)
    return sorted(cores)

# --- Cgroup Throttling Implementation ---

def set_cpu_max(cgroup_name, percent_limit):
    """Sets the cpu.max for a given cgroup based on percentage."""
    cgroup_path_base = '/sys/fs/cgroup/'
    cpu_max_path = os.path.join(cgroup_path_base, cgroup_name, 'cpu.max')

    if cgroup_name == USER_CGROUP:
        cores_list = available_cores_user or get_cgroup_available_cores(USER_CGROUP)
    elif cgroup_name == CRITICAL_CGROUP:
        cores_list = available_cores_critical or get_cgroup_available_cores(CRITICAL_CGROUP)
    else: return

    num_available_cores = len(cores_list)
    if num_available_cores == 0: return

    period_us = 100000 
    quota_us = int(period_us * num_available_cores * percent_limit / 100.0)
    max_quota_us = period_us * num_available_cores

    if percent_limit > 0:
         quota_us = max(1000, quota_us)
    else:
         quota_us = 0
    quota_us = min(quota_us, max_quota_us)

    conf_str = f"{quota_us} {period_us}"
    try:
        with open(cpu_max_path, 'w') as f:
            f.write(conf_str)
    except Exception: pass

def apply_user_throttle(percent_limit):
    set_cpu_max(USER_CGROUP, percent_limit)

def apply_critical_throttle(percent_limit):
    set_cpu_max(CRITICAL_CGROUP, percent_limit)

# --- Power Measurement ---

def calculate_cpu_power():
    """Calculates average CPU package power using perf stat."""
    try:
        result = subprocess.run(
            ['perf', 'stat', '-e', 'power/energy-pkg/', '-a', 'sleep', '1'],
            capture_output=True, text=True, check=True, timeout=5
        )
        output = result.stderr
        pkg_energy_match = re.search(r'(\d+\.\d+)\s+Joules\s+power/energy-pkg', output)
        time_elapsed_match = re.search(r'(\d+\.\d+)\s+seconds\s+time\s+elapsed', output)

        if pkg_energy_match and time_elapsed_match:
            pkg_energy = float(pkg_energy_match.group(1))
            time_elapsed = float(time_elapsed_match.group(1))
            return pkg_energy / time_elapsed
    except Exception:
        return None
    return None

# --- Main Control Loop ---

def run_power_capping_loop(loop_period_sec):
    global target_power, current_bandwidth_user, current_bandwidth_critical
    global start_time, throttling_active_state, next_unthrottle_time

    start_time = datetime.now()

    get_cgroup_available_cores(USER_CGROUP)
    get_cgroup_available_cores(CRITICAL_CGROUP)
    apply_user_throttle(current_bandwidth_user)
    apply_critical_throttle(current_bandwidth_critical)

    while True:
        loop_start_time = time.monotonic()

        # 1. Read Power Budget
        try:
            with open('./budget', 'r') as f:
                target_power = float(f.readline().strip())
        except Exception: pass

        # 2. Measure Actual Power
        actual_power = calculate_cpu_power()
        if actual_power is None:
            time.sleep(0.5)
            continue

        # 3. State Update: Low Threshold Activation
        if actual_power > target_power * LOW_THRESHOLD:
             throttling_active_state = True
        elif actual_power <= target_power * 0.90: # Hysteresis/Stability zone
             throttling_active_state = False

        # 4. Core RUMD Throttling Logic
        original_user_bw = current_bandwidth_user
        original_critical_bw = current_bandwidth_critical

        if actual_power > target_power * LOW_THRESHOLD:
            # --- Throttle Phase ---
            apply_hard_throttle = actual_power > target_power * HIGH_THRESHOLD
            apply_soft_throttle = (actual_power > target_power * LOW_THRESHOLD and
                                   not apply_hard_throttle and
                                   throttling_active_state)

            if current_bandwidth_user > THROTTLE_MIN:
                if apply_hard_throttle:
                    current_bandwidth_user *= HARD_MULTIPLIER
                elif apply_soft_throttle:
                    current_bandwidth_user *= SOFT_MULTIPLIER
                current_bandwidth_user = max(THROTTLE_MIN, current_bandwidth_user)

            elif current_bandwidth_critical > THROTTLE_MIN:
                if apply_hard_throttle:
                    current_bandwidth_critical *= HARD_MULTIPLIER
                elif apply_soft_throttle:
                    current_bandwidth_critical *= SOFT_MULTIPLIER
                current_bandwidth_critical = max(THROTTLE_MIN, current_bandwidth_critical)

        else: # actual_power <= target_power
            # --- Recovery Phase (Randomized Timeout Unthrottling) ---
            now = time.monotonic()
            
            # Check if the randomized wait period has passed
            if now >= next_unthrottle_time:
                # Priority 1: Recover Critical cgroup
                if current_bandwidth_critical < THROTTLE_MAX:
                    current_bandwidth_critical = min(THROTTLE_MAX, current_bandwidth_critical + UNTHROTTLE_STEP)
                    # Reset randomized timeout for next step
                    next_unthrottle_time = now + random.uniform(UNTHROTTLE_WAIT_MIN, UNTHROTTLE_WAIT_MAX)

                # Priority 2: Recover User cgroup (only if Critical is already max)
                elif current_bandwidth_user < THROTTLE_MAX:
                    current_bandwidth_user = min(THROTTLE_MAX, current_bandwidth_user + UNTHROTTLE_STEP)
                    # Reset randomized timeout for next step
                    next_unthrottle_time = now + random.uniform(UNTHROTTLE_WAIT_MIN, UNTHROTTLE_WAIT_MAX)

        # 5. Apply Throttling Changes
        if abs(current_bandwidth_user - original_user_bw) > 0.01:
             apply_user_throttle(current_bandwidth_user)
        if abs(current_bandwidth_critical - original_critical_bw) > 0.01:
             apply_critical_throttle(current_bandwidth_critical)

        # 6. Original Logging Format
        timestamp = (datetime.now() - start_time).total_seconds()
        print(f"{int(timestamp)} | {current_bandwidth_user} | {current_bandwidth_critical} | {target_power} | {actual_power:.0f}", flush=True)

        time.sleep(0.1)

# --- Signal Handling for Graceful Exit ---

def signal_handler(sig, frame):
    apply_user_throttle(THROTTLE_MAX)
    apply_critical_throttle(THROTTLE_MAX)
    exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        run_power_capping_loop(DEFAULT_PERIOD_SECONDS)
    except Exception as e:
        apply_user_throttle(THROTTLE_MAX)
        apply_critical_throttle(THROTTLE_MAX)
        exit(1)
