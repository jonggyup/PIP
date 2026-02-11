#!/usr/bin/env python3
import json
import time
import os
import sys
import signal
import subprocess
import re

# --- Configuration ---
USER_CGROUP_PATH = "/sys/fs/cgroup/user/cpu.max"   # Adjust as needed
PERIOD_US = 100000                                  # Fixed period in microseconds
CONTROL_INTERVAL = 1.0                              # Loop period in seconds
CRITICAL_BW = 100.00                                # Critical cgroup is not limited

def set_user_cpu_max(percent):
    """
    Sets the cpu.max for the 'user' cgroup based on the given percentage.
    For 100%, quota is set to "max"; otherwise, computes quota = PERIOD_US * cores * (percent/100).
    """
    num_cores = os.cpu_count() or 1
    if percent == 100.0:
        quota = "max"
    else:
        quota_val = int(PERIOD_US * num_cores * (percent / 100.0))
        quota = str(quota_val)
    conf_str = f"{quota} {PERIOD_US}"
    try:
        with open(USER_CGROUP_PATH, "w") as f:
            f.write(conf_str)
    except Exception as e:
        print(f"Error setting user cpu.max to '{conf_str}': {e}", flush=True)
        sys.exit(1)

def read_budget():
    """
    Reads and returns the target power budget (in Watts) from the file './budget'.
    """
    try:
        with open("./budget", "r") as f:
            return float(f.read().strip())
    except Exception as e:
        print(f"Error reading budget file: {e}", flush=True)
        return None

def load_power_info():
    """
    Loads the preanalyzed power info from 'power_info.json'.
    Expects a JSON mapping: { throttle_percentage (int): measured power (W) }.
    """
    try:
        with open("power_info.json", "r") as f:
            data = json.load(f)
            return {int(k): v for k, v in data.items()}
    except Exception as e:
        print(f"Error loading power_info.json: {e}", flush=True)
        sys.exit(1)

def select_throttle(power_info, target_power):
    """
    Selects the highest throttle level (largest percentage)
    from the preanalyzed info whose predicted power is <= target_power.
    If none qualifies, returns the lowest available level.
    """
    for level in sorted(power_info.keys(), reverse=True):
        if power_info[level] <= target_power:
            return level
    return min(power_info.keys())

def measure_power():
    """
    Uses perf to measure actual average power consumption (Watts) over a 1‑second interval.
    Returns the measured power or None on error.
    """
    try:
        result = subprocess.run(
            ['perf', 'stat', '-e', 'power/energy-pkg/', 'sleep', '1'],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            check=True,
            timeout=5
        )
    except Exception as e:
        print(f"Error running perf: {e}", flush=True)
        return None

    output = result.stderr
    m = re.search(r'([\d\.]+)\s+Joules', output)
    if m:
        try:
            energy = float(m.group(1))
            # For a 1-second measurement, the average power is approximately 'energy' (Watts)
            return energy
        except Exception as e:
            print(f"Error parsing energy: {e}", flush=True)
            return None
    else:
        print("Failed to parse energy from perf output.", flush=True)
        return None

def signal_handler(sig, frame):
    """Resets user cgroup throttle to 100% and exits."""
    print("\nReceived termination signal. Resetting user cgroup throttle to 100% and exiting.", flush=True)
    set_user_cpu_max(100.0)
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    power_info = load_power_info()
    start_time = time.monotonic()

    while True:
        elapsed = int(time.monotonic() - start_time)
        target_power = read_budget()
        if target_power is None:
            time.sleep(CONTROL_INTERVAL)
            continue
        
        selected_level = select_throttle(power_info, target_power)
        # Apply the selected user cgroup throttle
        set_user_cpu_max(selected_level)
        # Measure actual power consumption (via perf stat)
        actual_power = measure_power()
        if actual_power is None:
            actual_power = 0.0

        # Log format: timestamp | user throttle | critical throttle | budget | actual power
        print(f"{elapsed:4d} | {selected_level:6.2f} | {CRITICAL_BW:6.2f} | {target_power:6.2f} | {actual_power:6.2f}", flush=True)
        time.sleep(CONTROL_INTERVAL)

