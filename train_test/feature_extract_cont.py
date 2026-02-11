import subprocess
import os
import psutil
import time
import numpy as np
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
output_file_name = "../data/new-data-chunk.csv"

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

def measure_power_consumption():
    try:
        file_path = f'./perf-training.dat'
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

# Function to run stress-ng
def run_stress_ng():
    try:
        command = f'cpupower monitor perf stat -e power/energy-pkg/,power/energy-ram/ -a -o ./perf-training.dat sleep {period}'
        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        truth, cpu_metrics = measure_power_consumption()
        metrics = parse_cpu_data(process.stdout, cpu_metrics)
        save_to_file(output_file_name, metrics, truth)

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
