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
period = sys.argv[1]
target_power = sys.argv[2]
columns_to_parse = None
metrics_per_cpu = None
cpu_index = [63,31, 61,29, 59,27, 57,25, 55,23, 53,21, 51,19, 49,17, 47,15, 45,13, 43,11, 9,41, 7,39, 5,37, 35,3, 33,1, 62,30, 60,28, 58,26, 56,24, 54,22, 52,20, 50,18, 48,16, 46,14, 44,12, 42,10, 8,40, 6,38, 4,36, 34,2, 32,0]
cpu_count = 0

def parse_perf_data():
    try:
        file_path = f'./perf-est-cpu.dat'
        with open(file_path, 'r') as file:
            perf_output = file.read()

        # Extract power and time data
        pkg_energy = float(re.search(r'(\d+\.\d+)\s+Joules\s+power/energy-pkg/', perf_output).group(1))
        mem_energy = float(re.search(r'(\d+\.\d+)\s+Joules\s+power/energy-ram/', perf_output).group(1))
        time_elapsed = float(re.search(r'(\d+\.\d+)\s+seconds\s+time\s+elapsed', perf_output).group(1))
        calc_result = (pkg_energy - mem_energy) / time_elapsed

        # Split the file content into lines for further processing
        perf_output_lines = perf_output.split('\n')

        # List to store the extracted values
        extracted_values = []

        for line in perf_output_lines:
            # Skip lines containing power data or time data
            if 'power/energy-pkg' in line or 'power/energy-ram' in line or 'seconds time elapsed' in line or line.startswith('# started'):
                continue

            match = re.search(r'(\d+[\d,\.]*)', line)
            if match:
                # Remove commas and convert to integer
                value = int(matoh.group(1).replace(',', ''))
                value = value / time_elapsed
                extracted_values.append(value)

        return calc_result, extracted_values


    except Exception as e:
        return None, f"Error: {str(e)}"

def calculate_cpu_power():
    time.sleep(1)
    # Run the perf stat command and capture its output
    output = subprocess.run(['perf', 'stat', '-e', 'power/energy-pkg/,power/energy-ram/', 'sleep', '1'], stderr=subprocess.PIPE, text=True).stderr

    # Use regular expressions to extract the total package power, memory power, and time elapsed
    pkg_power_match = re.search(r'(\d+\.\d+) Joules power/energy-pkg/', output)
    mem_power_match = re.search(r'(\d+\.\d+) Joules power/energy-ram/', output)
    time_elapsed_match = re.search(r'(\d+\.\d+) seconds time elapsed', output)

    if pkg_power_match and mem_power_match and time_elapsed_match:
        pkg_power = float(pkg_power_match.group(1))
        mem_power = float(mem_power_match.group(1))
        time_elapsed = float(time_elapsed_match.group(1))

        # Calculate the CPU power
        cpu_power = (pkg_power - mem_power) / time_elapsed

        return cpu_power
    else:
        raise ValueError("Failed to extract power or time data from perf stat output.")

def parse_cpu_data(output):
    global parsed_data_a
    global parsed_data_b
    global metrics
    parsed_data = []
    tmp_data = []
    elements = []
    parsing_start = 0
    lines = output.split('\n')

    for line in lines:
        elements = line.strip().split("|")
        elements = [e.strip() for e in elements if e.strip()]

        if parsing_start == 0:
            if 'CPU' in elements:
                parsing_start = 1
                continue
            continue

        elements = [e.strip() for e in elements if e.strip()]
        if elements:
                tmp_data.append(elements[columns_to_parse:])
    if tmp_data:
        parsed_data = list(np.concatenate(tmp_data))
    return parsed_data

def core_throttling(index):
    # Define the path to the cgroup v2
    cgroup_path = '/sys/fs/cgroup/'

    # Create a new cgroup for the application if it doesn't exist
    app_cgroup = os.path.join(cgroup_path, 'user')

    # Calculate the cores to be used
    conf_str = str(int(100000 * 64 * index / 100)) + " 100000"

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

def throttle_power(feature_map):
    try:
        with open('../data/idle.dat', 'r') as file:
            idle_data = file.read()
            idle_values = idle_data.split(',')
            idle_map = [float(value) for value in idle_values[:-1]]

        for throttle in range(100, 0, -5):
            for disabled_cores in range(0, len(cpu_index)):
                modified_feature_map = feature_map.copy()

                core_parking(disabled_cores)
                core_throttling(throttle)

    except Exception as e:
        print(f"An error occurred: {e}")
        return None


# Function to run stress-ng
def run_stress_ng():
    try:
        throttle_power(metrics)

    except Exception as e:
        print(f"An error occurred while running stress-ng: {e}")


def parse_cpu_info():
    output = subprocess.run(["cpupower", "monitor", "sleep", "0"], capture_output=True, text=True).stdout
    lines = output.split('\n')
    for line in lines:
        elements = line.strip().split("|")
        elements = [e.strip() for e in elements if e.strip()]

        if 'C0' in elements:
            c0_index = elements.index('C0')
            return c0_index, len(elements) - c0_index

    raise ValueError("Error: This architecture is not supported.")

def signal_handler(sig, frame):
    if os.path.exists("perf-est-cpu.dat"):
        os.remove("perf-est-cpu.dat")
    exit(0)

if __name__ == "__main__":
    # Register the signal handler for SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    columns_to_parse, metrics_per_cpu = parse_cpu_info()

    stress_thread = threading.Thread(target=run_stress_ng)
    stress_thread.start()
    stress_thread.join()
