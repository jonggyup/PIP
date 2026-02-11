import subprocess
import os
import psutil
import time
import numpy as np
import pandas as pd
import csv
import sys
import re
import joblib
from sklearn.exceptions import DataConversionWarning
import warnings
import time
import signal
import threading
from datetime import datetime
import random


import statistics
from collections import deque

warnings.filterwarnings(action='ignore', category=UserWarning)

powers = []
metrics = []
power_array = [None] * 5
period = sys.argv[1]
output_file_name = "../data/training-data.csv"

calibration = 0
calibration_values = deque(maxlen=4)
calibration_weights = [0.05, 0.1, 0.15, 0.7]
current_bandwidth = 100
throttle_values = []
actual_power_values = []
prev = 0
num_cores = os.cpu_count()
start_time = datetime.now()

# Constants
HARD_MULTIPLIER = 0.1  # Hard multiplier for fast throttling
SOFT_MULTIPLIER = 0.9  # Soft multiplier for gradual unthrottling
THROTTLE_MIN = 0.01    # Minimum CPU cap (1%)
THROTTLE_MAX = 100     # Maximum CPU cap (100%)
HIGH_THRESHOLD = 0.98  # 98% of power limit
LOW_THRESHOLD = 0.90   # Example of low threshold value

metrics = [
    "cpu-cycles", "instructions", "cache-references", "cache-misses",
    "branches", "branch-misses", "bus-cycles", "ref-cycles",
    "context-switches", "cpu-migrations", "page-faults",
    "L1-dcache-loads", "L1-dcache-load-misses", "L1-icache-load-misses",
    "LLC-loads", "LLC-load-misses", "dTLB-loads", "dTLB-load-misses",
    "msr/aperf/", "msr/mperf/", "msr/pperf/", "fp_arith_inst_retired.scalar_double",
    "fp_arith_inst_retired.scalar_single", "fp_arith_inst_retired.128b_packed_double",
    "fp_arith_inst_retired.128b_packed_single", "fp_arith_inst_retired.256b_packed_double",
    "fp_arith_inst_retired.256b_packed_single", "fp_arith_inst_retired.512b_packed_double"
]

def core_throttling(index):
    # Define the path to the cgroup v2
    cgroup_path = '/sys/fs/cgroup/'

    # Create a new cgroup for the application if it doesn't exist
    app_cgroup = os.path.join(cgroup_path, 'user')

    # Calculate the cores to be used
    conf_str = str(int(100000 * num_cores * index / 100)) + " 100000"

    # Set the cpuset.cpus for the application cgroup
    with open(os.path.join(app_cgroup, 'cpu.max'), 'w') as f:
        f.write(conf_str)


def get_supported_metrics():
    try:
        result = subprocess.run(['perf', 'list'], capture_output=True, text=True)
        if result.returncode == 0:
            supported_metrics = result.stdout
            return supported_metrics
        else:
            print(f"Error retrieving perf metrics: {result.stderr}")
            return None
    except Exception as e:
        print(f"An error occurred while retrieving perf metrics: {e}")
        return None

def filter_supported_metrics(metrics, supported_metrics_output):
    supported_metrics = []
    for metric in metrics:
        # Check if the metric exists in the supported metrics output
        if metric in supported_metrics_output:
            supported_metrics.append(metric)
    return supported_metrics

def parse_perf_metrics():
    try:
        perf_file_path = './perf_metrics.dat'
        core_temp_file_path = './core_temp.dat'

        # Read the perf_fp.dat file
        with open(perf_file_path, 'r') as perf_file:
            perf_output = perf_file.read()

        # Split the perf file content into lines for further processing
        perf_output_lines = perf_output.split('\n')

        # List to store the extracted values from perf_fp.dat
        perf_extracted_values = []

        time_elapsed = float(re.search(r'(\d+\.\d+)\s+seconds\s+time\s+elapsed', perf_output).group(1))

        for line in perf_output_lines:
            match = re.search(r'(\d+[\d,\.]*)', line)
            if match:
                # Remove commas and convert to integer
                value = float(match.group(1).replace(',', ''))
            value = value / time_elapsed
            formatted_value = float(f"{value:.2f}")
            perf_extracted_values.append(formatted_value)
#            perf_extracted_values.append(value)

        # Read the core_temp.dat file
        with open(core_temp_file_path, 'r') as core_temp_file:
            core_temp_output = core_temp_file.read()

        # Process core_temp file content and append each value to the end of extracted values
        core_temp_values = []
        for line in core_temp_output.split('\n'):
            if line.strip():  # Skip empty lines
                value = float(line.strip())
                core_temp_values.append(value)

        # Combine perf and core_temp values
        combined_values = core_temp_values + perf_extracted_values

#        combined_values = {
#            'perf_values': perf_extracted_values,
#            'core_temp_values': core_temp_values
#        }

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
        elements = line.strip().split("|")
        elements = [e.strip() for e in elements if e.strip()]

        # Find the index of 'C0' in the line that contains 'CPU'
        if 'CPU' in elements and c0_index is None:
            c0_index = elements.index('C0')
            continue  # Skip this header line

        # Start collecting data from the next line after 'CPU'
        if elements and c0_index is not None:
            tmp_data.append(elements[c0_index:])
    
    if tmp_data:
        parsed_data = list(np.concatenate(tmp_data))
        parsed_data.extend(cpu_metrics)

    return parsed_data


def calculate_cpu_power():
    # Run the perf stat command and capture its output
    output = subprocess.run(['perf', 'stat', '-e', 'power/energy-pkg/', 'sleep', '1'], stderr=subprocess.PIPE, text=True).stderr

    # Use regular expressions to extract the total package power, memory power, and time elapsed
    pkg_power_match = re.search(r'(\d+\.\d+) Joules power/energy-pkg/', output)
    time_elapsed_match = re.search(r'(\d+\.\d+) seconds time elapsed', output)

    if pkg_power_match and time_elapsed_match:
        pkg_power = float(pkg_power_match.group(1))
        time_elapsed = float(time_elapsed_match.group(1))

        # Calculate the CPU power
        cpu_power = pkg_power / time_elapsed

        return cpu_power
    else:
        raise ValueError("Failed to extract power or time data from perf stat output.")


# Function to run stress-ng


def run_perf_metrics():
    try:
        supported_metrics_output = get_supported_metrics()
        filtered_metrics = filter_supported_metrics(metrics, supported_metrics_output)
        filtered_metrics_str = ','.join(filtered_metrics)
        command = f'perf stat -e {filtered_metrics_str} -a -o ./perf_metrics.dat python3 ./coretemp_simp.py 1'

        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    except Exception as e:
        print(f"An error occurred while running perf: {e}")

def run_perf_energy():
    try:
        command = ('perf stat -e power/energy-pkg/ -a -o ./perf_energy.dat sleep 1')
        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception as e:
        print(f"An error occurred while running perf for energy: {e}")


def relaxed_power_capping(feature_map):
    try:
        global calibration
        global calibration_weights
        global current_bandwidth
        global throttle_values, actual_power_values


        # Calculate the median of throttle values if repetitive
        if len(set(throttle_values)) == 2:
            median_throttle = statistics.median(throttle_values)
            core_throttling(median_throttle)
            return
    

        with open('../data/idle.dat', 'r') as file:
            idle_data = file.read()
            idle_values = idle_data.split(',')
            idle_map = [float(value) for value in idle_values[:-1]]

        model = joblib.load('../MLs/CatBoost_model.joblib') #Change the model name to what you want.

#        model = CatBoostRegressor()
#        model.load_model('../MLs/CatBoost_model.joblib')

        success = 0
        with open('topol_metric_size.dat', 'r') as file:
            data = file.readline().split()
            topol_size = int(data[0])  # First value to be used
            direct_metrics_size = int(data[1])  # Second value to be saved in variable
            max_freq = int(data[2])


        for throttle in range(100, 0, -5):
            modified_feature_map = feature_map.copy()

            # Apply throttling
            for i in range(topol_size):
                if i % 7 == 0 and float(modified_feature_map[i]) > throttle:
                    modified_feature_map[i] = throttle
                elif (i % 7 == 1 or i % 7 == 5) and float(modified_feature_map[i]) < 100 - throttle:
                    modified_feature_map[i] = 100 - throttle

            for i in range(direct_metrics_size, len(modified_feature_map)):
                modified_feature_map[i] = modified_feature_map[i] * throttle / 100

            features_array = np.array(modified_feature_map).reshape(1, -1)
            prediction = float(model.predict(features_array)[0])

            if prediction <= float(target_power):
                success = 1
                break

        if success == 0:
            calibration = 0
#            print("Cannot meet the target power with any configuration.")

        core_throttling(throttle)
        actual = calculate_cpu_power()
        calibration = actual - prediction

        # Add the new calibration value to the deque
        calibration_values.append(actual - prediction)
        n = len(calibration_values)

        # Generate dynamic weights that emphasize the most recent value more
        # For example, using a linear weighting scheme
        weights = np.arange(1, n+1)
        weights = weights / weights.sum()  # Normalize to sum to 1

        # Compute the weighted average
        calibration = sum(value * weight for value, weight in zip(calibration_values, weights))

        # Save the throttle value and actual power to global variables
        throttle_values.append(throttle)
        actual_power_values.append(actual)

        # Keep only the last 6 values
        if len(throttle_values) > 8:
            throttle_values = throttle_values[-8:]
            actual_power_values = actual_power_values[-8:]

        # Get the current time
        current_time = datetime.now()

        # Calculate the elapsed time in seconds
        timestamp = (current_time - start_time).total_seconds()

        print(f"{int(timestamp)} | relaxed | {target_power} | {throttle} | {prediction} | {actual}", flush=True)

        return int(throttle)


    except Exception as e:
        print(f"An error occurred: {e}")
        return None



def strict_power_capping(feature_map):
    try:
        global calibration
        global calibration_weights
        global current_bandwidth

        with open('../data/idle.dat', 'r') as file:
            idle_data = file.read()
            idle_values = idle_data.split(',')
            idle_map = [float(value) for value in idle_values[:-1]]


        model = joblib.load('../MLs/CatBoost_model.joblib') #Change the model name to what you want.
#        model = CatBoostRegressor()
#        model.load_model('../MLs/CatBoost_model.joblib')
        if prev == 1:
            start = current_bandwidth
        else:
            start = 100

        success = 0
        with open('topol_metric_size.dat', 'r') as file:
            data = file.readline().split()
            topol_size = int(data[0])  # First value to be used
            direct_metrics_size = int(data[1])  # Second value to be saved in variable
            max_freq = int(data[2])


        for throttle in range(100, 0, -5):
            modified_feature_map = feature_map.copy()

            # Apply throttling
            for i in range(topol_size):
                if i % 7 == 0:
                    modified_feature_map[i] = throttle + 0.5
                elif i % 7 == 1 or i % 7 == 5:
                    modified_feature_map[i] = 100 - throttle - 0.5
                elif i % 7 == 2:
                    modified_feature_map[i] = max_freq

            for i in range(direct_metrics_size, len(modified_feature_map)):
                modified_feature_map[i] = modified_feature_map[i] * throttle / 100

            features_array = np.array(modified_feature_map).reshape(1, -1)
            prediction = float(model.predict(features_array)[0])

            if prediction + 5 <= float(target_power): # - calibration * 2:
                success = 1
                break

        if success == 0:
            calibration = 0
#            print("Cannot meet the target power with any configuration.")

#        core_parking(int(best_config['cores']))
        core_throttling(throttle)

        actual = calculate_cpu_power()
        calibration = actual - prediction

        # Add the new calibration value to the deque
        calibration_values.append(actual - prediction)
        n = len(calibration_values)

        # Generate dynamic weights that emphasize the most recent value more
        # For example, using a linear weighting scheme
        weights = np.arange(1, n+1)
        weights = weights / weights.sum()  # Normalize to sum to 1

        # Compute the weighted average
        calibration = sum(value * weight for value, weight in zip(calibration_values, weights))

        # Get the current time
        current_time = datetime.now()

        # Calculate the elapsed time in seconds
        timestamp = (current_time - start_time).total_seconds()

        print(f"{int(timestamp)} | strict | {target_power} | {throttle} | {prediction} | {actual}", flush=True)

        return int(throttle)


    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def ms_control(actual_power, target_power, current_bandwidth):
    if actual_power > target_power:  # If power exceeds the limit
        current_bandwidth = 5
    else:
        current_bandwidth = min(current_bandwidth + 1, THROTTLE_MAX)

    # Apply the new throttling cap
    core_throttling(current_bandwidth)

    # Return the updated bandwidth
    return current_bandwidth

def run_stress_ng():
    try:
        global target_power
        global current_bandwidth
        global prev
        current_bandwidth = 100
        
        while True:
            actual_power = float(calculate_cpu_power())
            with open('./budget', 'r') as file:
                # Read the first line of the file
                line = file.readline()
                # Convert the line to an integer
                target_power = int(line.strip())

#            print(f"power = {actual_power:.2f} | bugdet = {target_power:.2f} | bandwidth = {current_bandwidth}", flush=True)
            fp_thread = threading.Thread(target=run_perf_metrics)
            energy_thread = threading.Thread(target=run_perf_energy)

            
            fp_thread.start()
#            energy_thread.start()
            command = f'cpupower monitor sleep {period}'
            process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            fp_thread.join()
#            energy_thread.join()

            perf_metrics = parse_perf_metrics()
            metrics = parse_cpu_data(process.stdout, perf_metrics)

            # Apply RUMD control for CPU bandwidth
            current_bandwidth = ms_control(actual_power, target_power, current_bandwidth)

            # Get the current time
            current_time = datetime.now()

            # Calculate the elapsed time in seconds
            timestamp = (current_time - start_time).total_seconds()
            print(f"{int(timestamp)} | {current_bandwidth} | {target_power} | 0 | 0 | {actual_power:.0f}", flush=True)


    except Exception as e:
        print(f"An error occurred while running stress-ng: {e}")

def signal_handler(sig, frame):
    if os.path.exists("perf-training.dat"):
        os.remove("perf-training.dat")
    exit(0)

if __name__ == "__main__":
    # Register the signal handler for SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    while True:
        stress_thread = threading.Thread(target=run_stress_ng)
        stress_thread.start()
        stress_thread.join()
