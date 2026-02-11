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

warnings.filterwarnings(action='ignore', category=UserWarning)

powers = []
metrics = []
power_array = [None] * 5
period = sys.argv[1]
output_file_name = "../data/training-data.csv"


metrics = [
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

# Read the second value from the topol.dat file
with open('./topol_metric_size.dat', 'r') as file:
    values = file.read().split()  # Assuming the file contains space-separated or newline-separated values
    perf_metric_index = int(values[1])  # Get the second value and convert to an integer

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


def save_to_file(file_name, metric, power):
    file_exists = os.path.exists(file_name)

    with open(file_name, 'a', newline='') as csvfile:
        csvwrite = csv.writer(csvfile)

        if not file_exists:
            headers = [f'feature{i+1}' for i in range(len(metric))]
            headers.append('label')
            csvwrite.writerow(headers)

        data_line = metric + [power]
        csvwrite.writerow(data_line)


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
            # Match lines that start with numbers and contain performance metrics
            match = re.search(r'^ *([\d,\.]+)\s+([a-zA-Z\-/]+)', line)
            # Skip lines that contain "seconds" or other non-metric lines
            if 'seconds' in line:
                continue
            if match:
                # Extract the numeric value and remove commas
                value = float(match.group(1).replace(',', ''))
                value = value / time_elapsed  # Adjust by the elapsed time
                formatted_value = float(f"{value:.2f}")  # Format the value to 2 decimal places
                perf_extracted_values.append(formatted_value)

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

# Function to run stress-ng


def run_perf_metrics():
    try:
        supported_metrics_output = get_supported_metrics()
#        command = f'perf stat -e cpu-cycles,instructions,cache-references,cache-misses,branches,branch-misses,bus-cycles,ref-cycles,context-switches,cpu-migrations,page-faults,L1-dcache-loads,L1-dcache-load-misses,L1-icache-load-misses,LLC-loads,LLC-load-misses,dTLB-loads,dTLB-load-misses,msr/aperf/,msr/mperf/,msr/pperf/,fp_arith_inst_retired.scalar_double,fp_arith_inst_retired.scalar_single,fp_arith_inst_retired.128b_packed_double,fp_arith_inst_retired.128b_packed_single,fp_arith_inst_retired.256b_packed_double,fp_arith_inst_retired.256b_packed_single,fp_arith_inst_retired.512b_packed_double -a -o ./perf_metrics.dat python3 ./coretemp_simp.py 1'
        filtered_metrics = filter_supported_metrics(metrics, supported_metrics_output)
        filtered_metrics_str = ','.join(filtered_metrics)
#        print(filtered_metrics_str)
        command = f'perf stat -e {filtered_metrics_str} -a -o ./perf_metrics.dat python3 ./coretemp_simp.py 1'

        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Process the perf output if needed
        # Example: process.stdout, process.stderr
    except Exception as e:
        print(f"An error occurred while running perf: {e}")

def run_perf_energy():
    try:
        command = ('perf stat -e power/energy-pkg/ -a -o ./perf_energy.dat sleep 1')
        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception as e:
        print(f"An error occurred while running perf for energy: {e}")

def predict_power_all(feature_map):
    try:
        features_array = np.array(feature_map).reshape(1, -1)
        # Load the model and make a prediction
        model = joblib.load('../MLs/CatBoost_model.joblib') #Change the model name to what you want.
        prediction = model.predict(features_array)
        return prediction[0]
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def predict_power_all2(feature_map):
    try:
        features_array = np.array(feature_map).reshape(1, -1)
        # Load the model and make a prediction
        model = joblib.load('../MLs/CatBoost_model-v1.1.joblib') #Change the model name to what you want.
        prediction = model.predict(features_array)
        return prediction[0]
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
def predict_power_all3(feature_map):
    try:
        features_array = np.array(feature_map).reshape(1, -1)
        # Load the model and make a prediction
        model = joblib.load('../MLs/CatBoost_model-v1.2.joblib') #Change the model name to what you want.
        prediction = model.predict(features_array)
        return prediction[0]
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def predict_power_cpu(feature_map):
    try:
        features_array = np.array(feature_map[:448]).reshape(1, -1)

        # Load the model and make a prediction
        model = joblib.load('../MLs/CatBoost_model-cpu.joblib') #Change the model name to what you want.
        prediction = model.predict(features_array)
        return prediction[0]
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def predict_power_perf(feature_map):

    try:

        features_array = np.array(feature_map[perf_metric_index:]).reshape(1, -1)
        # Load the model and make a prediction
        model = joblib.load('../MLs/CatBoost_model-perf.joblib') #Change the model name to what you want.
        prediction = model.predict(features_array)
        return prediction[0]
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def predict_power_noperf(feature_map):

    try:

        features_array = np.array(feature_map[:448] + feature_map[478:]).reshape(1, -1)

        # Load the model and make a prediction
        model = joblib.load('../MLs/CatBoost_model-noperf.joblib') #Change the model name to what you want.
        prediction = model.predict(features_array)
        return prediction[0]
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def predict_power_powerapi(feature_map):
    try:
        #selected_indices = [520, 521, 522, 523]
        selected_indices = {perf_metric_index, perf_metric_index+1, perf_metric_index+2, perf_metric_index+3}

        features_array = np.array([feature_map[i] for i in selected_indices]).reshape(1, -1)

        # Load the model and make a prediction
        model = joblib.load('../MLs/Ridge_model-powerapi.joblib') #Change the model name to what you want.
        prediction = model.predict(features_array)
        return prediction[0]
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def predict_power_kepler(feature_map):
    try:
        #selected_indices = [523, 524, 525, 526]
        selected_indices = {perf_metric_index+3, perf_metric_index+4, perf_metric_index+5, perf_metric_index+6}

        features_array = np.array([feature_map[i] for i in selected_indices]).reshape(1, -1)

        # Load the model and make a prediction
        model = joblib.load('../MLs/GradientBoosting_model-kepler.joblib') #Change the model name to what you want.
        prediction = model.predict(features_array)
        return prediction[0]
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def run_stress_ng():
    try:
        fp_thread = threading.Thread(target=run_perf_metrics)
        energy_thread = threading.Thread(target=run_perf_energy)

        fp_thread.start()
        energy_thread.start()
        command = f'cpupower monitor sleep 1'
        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        fp_thread.join()
        energy_thread.join()

    
        # Measure power consumption and other metrics
        truth = parse_power_consumption()
        perf_metrics = parse_perf_metrics()

        metrics = parse_cpu_data(process.stdout, perf_metrics)
        estimate_power_all = predict_power_all(metrics)
        estimate_power_all2 = predict_power_all2(metrics)
        estimate_power_all3 = predict_power_all3(metrics)
#        estimate_power_cpu = predict_power_cpu(metrics)
        estimate_power_perf = predict_power_perf(metrics)
        estimate_power_powerapi = predict_power_powerapi(metrics)
        estimate_power_kepler = predict_power_kepler(metrics)

#        estimate_power_noperf = predict_power_noperf(metrics)

        error_all = abs(estimate_power_all - truth) / truth * 100
        error_all2 = abs(estimate_power_all2 - truth) / truth * 100
        error_all3 = abs(estimate_power_all3 - truth) / truth * 100
#        error_cpu = abs(estimate_power_cpu - truth) / truth * 100
        error_perf = abs(estimate_power_perf - truth) / truth * 100
        error_powerapi = abs(estimate_power_powerapi - truth) / truth * 100
        error_kepler = abs(estimate_power_kepler - truth) / truth * 100
#        error_noperf = abs(estimate_power_noperf - truth) / truth * 100
#        print(f"Est. Power-A: {estimate_power_all}, Power-C: {estimate_power_cpu}, Power-P: {estimate_power_perf}, Power-NP: {estimate_power_noperf}, Truth: {truth}, Error-A(%): {error_all}, Error-C: {error_cpu}, Error-P: {error_perf}, Error-NP: {error_noperf}", flush=True)

#        print(f"Power-A: {estimate_power_all:.2f}, Power-P: {estimate_power_perf:.2f}, Power-kepler: {estimate_power_kepler:.2f}, Power-papi: {estimate_power_powerapi:.2f}, Truth: {truth:.2f}, Error-A(%): {error_all:.2f}, Error-P(%): {error_perf:.2f}, Error-K(%): {error_kepler:.2f}, Error-papi(%): {error_powerapi:.2f}", flush=True)

        print(f"{estimate_power_all:.2f}, {estimate_power_all2:.2f}, {estimate_power_all3:.2f}, {estimate_power_perf:.2f}, {estimate_power_kepler:.2f}, {estimate_power_powerapi:.2f}, {truth:.2f}, {error_all:.2f}, {error_all2:.2f}, {error_all3:.2f}, {error_perf:.2f}, {error_kepler:.2f}, {error_powerapi:.2f}", flush=True)

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
