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
columns_to_parse = None
metrics_per_cpu = None
cpu_count = 0
global_start_time = int(time.time() * 1000)


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
                value = int(match.group(1).replace(',', ''))
                value = value / time_elapsed
                extracted_values.append(value)

        return calc_result, extracted_values

    except Exception as e:
        return None, f"Error: {str(e)}"

    except Exception as e:
        return None, f"Error: {str(e)}"


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

def predict_power(feature_map):
    try:
        features_array = np.array(feature_map).reshape(1, -1)

        # Load the model and make a prediction
        model = CatBoostRegressor()
        model.load_model('../MLs/CatBoost_model-new.joblib')

        prediction = model.predict(features_array)
        return prediction[0]
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# Function to run stress-ng
def run_stress_ng():
    try:
        global global_start_time
#        command = f'cpupower monitor perf stat -e cpu-cycles,instructions,cache-references,cache-misses,branches,branch-misses,bus-cycles,ref-cycles,context-switches,cpu-migrations,page-faults,L1-dcache-loads,L1-dcache-load-misses,L1-icache-load-misses,LLC-loads,LLC-load-misses,dTLB-loads,dTLB-load-misses,msr/aperf/,msr/mperf/,msr/pperf/,power/energy-pkg/,power/energy-ram/ -a -o ./perf-est-cpu.dat sleep {period}'
        command = f'cpupower monitor perf stat -e power/energy-pkg/,power/energy-ram/ -a -o ./perf-est-cpu.dat sleep {period}'
        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Calculate the current timestamp in milliseconds
        current_timestamp_ms = int(time.time() * 1000) - global_start_time

        # Parse the perf data
        truth, perf_metrics = parse_perf_data()
        metrics = parse_cpu_data(process.stdout)
        metrics.extend(perf_metrics)
        estimate_power = predict_power(metrics)

        error = abs(estimate_power - truth) / truth * 100
        # Read integer value from ./budget file
        with open('./budget', 'r') as file:
            budget_value = int(file.read().strip())
        
        print(f"Time(ms): {current_timestamp_ms}, Budget: {budget_value}, Est. Power: {estimate_power:.2f}, Truth: {truth:.2f}, Error(%): {error:.2f}", flush=True)


        
#        print(f"Est. Power: {estimate_power}, Truth: {truth}, Error(%): {error}", flush=True)
#        print(f"power: {truth}", flush=True)


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

    while True:
        stress_thread = threading.Thread(target=run_stress_ng)
        stress_thread.start()
        stress_thread.join()
