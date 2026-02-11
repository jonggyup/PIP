#!/usr/bin/env python3
import subprocess
import re
import json
import time
import os

# Path to the "user" cgroup cpu.max file (adjust if needed)
CGROUP_PATH = "/sys/fs/cgroup/user/cpu.max"
PERF_DURATION = 1       # Seconds for each perf measurement
PERIOD_US = 100000      # Fixed period in microseconds

def set_cpu_max(percent):
    """
    Sets the cpu.max value for the 'user' cgroup based on the provided percentage.
    Uses a fixed period (PERIOD_US) and computes quota accordingly.
    """
    num_cores = os.cpu_count() or 1
    if percent == 100:
        quota = "max"
    else:
        quota_val = int(PERIOD_US * num_cores * (percent / 100.0))
        quota = str(quota_val)
    conf_str = f"{quota} {PERIOD_US}"
    try:
        with open(CGROUP_PATH, "w") as f:
            f.write(conf_str)
    except Exception as e:
        print(f"Error setting cpu.max to '{conf_str}': {e}")
        exit(1)

def measure_power():
    """
    Uses perf to measure energy consumption (RAPL power/energy-pkg)
    and returns average power in Watts.
    """
    try:
        result = subprocess.run(
            ["perf", "stat", "-e", "power/energy-pkg/", "sleep", str(PERF_DURATION)],
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
    except Exception as e:
        print(f"Error running perf: {e}")
        return None

    output = result.stderr
    m = re.search(r'([\d\.]+)\s+Joules', output)
    if m:
        energy = float(m.group(1))
        return energy / PERF_DURATION
    else:
        print("Failed to parse energy from perf output.")
        return None

def main():
    power_data = {}  # Mapping: throttling percentage -> measured power (W)
    # Sweep from 100% down to 5% in 5% steps.
    for percent in range(100, 0, -5):  # 100, 95, ..., 5
        print(f"Setting CPU limit to {percent}%")
        set_cpu_max(percent)
        time.sleep(1)  # Allow time to stabilize
        power = measure_power()
        if power is not None:
            print(f"Measured power at {percent}%: {power:.2f} W")
            power_data[percent] = power
        else:
            print(f"Measurement failed for {percent}%.")
        time.sleep(1)
        
    # Save the mapping to a file.
    with open("power_info.json", "w") as f:
        json.dump(power_data, f, indent=2)
    print("Saved power information to power_info.json.")

if __name__ == "__main__":
    main()

