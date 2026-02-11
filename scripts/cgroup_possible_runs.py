import subprocess
import threading
import os
import psutil
import time
import numpy as np
import csv
import sys
import pandas as pd
import signal

import re
import joblib
from sklearn.exceptions import DataConversionWarning
import warnings
import time
from catboost import CatBoostRegressor


pid_to_time_map = {}
columns_to_parse = None
metrics_per_cpu = None
#cpu_index = [63,31, 61,29, 59,27, 57,25, 55,23, 53,21, 51,19, 49,17, 47,15, 45,13, 43,11, 9,41, 7,39, 5,37, 35,3, 33,1, 62,30, 60,28, 58,26, 56,24, 54,22, 52,20, 50,18, 48,16, 46,14, 44,12, 42,10, 8,40, 6,38, 4,36, 34,2, 32,0]
cpu_index = []
cpu_count = 0

def get_available_cores():
    """Retrieve the list of available cores from cpuset.cpus.effective in cgroup v2."""

    try:
        with open('/sys/fs/cgroup/user/cpuset.cpus.effective', 'r') as f:
            cpuset_cpus = f.read().strip()

        # Convert CPU set string to a list of cores
        for part in cpuset_cpus.split(','):
            if '-' in part:
                start, end = map(int, part.split('-'))
                available_cores.extend(range(start, end + 1))
            else:
                available_cores.append(int(part))

    except Exception as e:
        print(f"Error reading cpuset.cpus.effective: {e}")

    return list(set(available_cores))  # Remove duplicates just in case

def get_cpu_topology():
    global cpu_index
    try:
        result = subprocess.run(['./get_cpu_topology.sh'], capture_output=True, text=True)
        if result.returncode == 0:
            # Clean up the output by replacing commas with spaces and removing extra spaces
            cpu_topology_output = result.stdout.strip().replace(',', ' ').replace('  ', ' ')
            
            # Split the output by spaces and filter out any empty strings
            cpu_index = list(map(int, filter(None, cpu_topology_output.split())))
        else:
            print(f"Error executing get_cpu_topology.sh: {result.stderr}")
    except Exception as e:
        print(f"An error occurred while retrieving CPU topology: {e}")

def core_throttling(index):
    # Define the path to the cgroup v2
    cgroup_path = '/sys/fs/cgroup/'

    # Create a new cgroup for the application if it doesn't exist
    app_cgroup = os.path.join(cgroup_path, 'user')

    num_effective_cores = len(get_available_cores())
    
    # Calculate the cores to be used
    conf_str = str(int(100000 * num_effective_cores * index / 100)) + " 100000"

    # Set the cpuset.cpus for the application cgroup
    with open(os.path.join(app_cgroup, 'cpu.max'), 'w') as f:
        f.write(conf_str)

def core_parking(index):
    # Define the path to the cgroup v2
    cgroup_path = '/sys/fs/cgroup/'

    # Create a new cgroup for the application if it doesn't exist
    app_cgroup = os.path.join(cgroup_path, 'user')
    if not os.path.exists(app_cgroup):
        os.makedirs(app_cgroup)
        with open(os.path.join(app_cgroup, 'cpuset.cpus'), 'w') as f:
            f.write('0-{}'.format(os.cpu_count() - 1))
        with open(os.path.join(app_cgroup, 'cgroup.procs'), 'w') as f:
            f.write(str(os.getpid()))

    # Calculate the cores to be used
    all_cores = set(range(os.cpu_count()))
    excluded_cores = set(cpu_index[:index + 1])
    used_cores = all_cores - excluded_cores
    used_cores_str = ','.join(str(core) for core in used_cores)

    # Set the cpuset.cpus for the application cgroup
    with open(os.path.join(app_cgroup, 'cpuset.cpus'), 'w') as f:
        f.write(used_cores_str)

def throttle_power():
    try:
        time.sleep(3)
        for throttle in range(100, 0, -5):
            for disabled_cores in range(0, len(cpu_index)):
                core_parking(disabled_cores)
                core_throttling(throttle)
                time.sleep(3)

    except Exception as e:
        print(f"An error occurred: {e}")
        return None


# Function to run stress-ng
def run_stress_ng():
    try:
        throttle_power()

    except Exception as e:
        print(f"An error occurred while running stress-ng: {e}")

def signal_handler(sig, frame):
    if os.path.exists("perf-est-cpu.dat"):
        os.remove("perf-est-cpu.dat")
    exit(0)

if __name__ == "__main__":
    # Register the signal handler for SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    get_cpu_topology()

    stress_thread = threading.Thread(target=run_stress_ng)
    stress_thread.start()
    stress_thread.join()
