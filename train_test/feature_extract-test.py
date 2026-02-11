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

warnings.filterwarnings(action="ignore", category=UserWarning)

powers = []
metrics = []
power_array = [None] * 5
period = sys.argv[1]
output_file_name = "../data/test-data.csv"
metrics = [
    "cpu_clk_unhalted.ref_tsc",
    "cpu_clk_unhalted.thread_p",
    "LLC-load-misses",
    "instructions",
    "cpu-cycles",
    "cpu-clock",
    "cache-misses",
    "cache-references",
    "branches",
    "branch-misses",
    "bus-cycles",
    "ref-cycles",
    "context-switches",
    "cpu-migrations",
    "page-faults",
    "L1-dcache-loads",
    "L1-dcache-load-misses",
    "L1-icache-load-misses",
    "LLC-loads",
    "dTLB-loads",
    "dTLB-load-misses",
    "msr/aperf/",
    "msr/mperf/",
    "msr/pperf/",
    "fp_arith_inst_retired.scalar_double",
    "fp_arith_inst_retired.scalar_single",
    "fp_arith_inst_retired.128b_packed_double",
    "fp_arith_inst_retired.128b_packed_single",
    "fp_arith_inst_retired.256b_packed_double",
    "fp_arith_inst_retired.256b_packed_single",
    "fp_arith_inst_retired.512b_packed_double",
]


def get_supported_metrics():
    try:
        result = subprocess.run(["perf", "list"], capture_output=True, text=True)
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

    with open(file_name, "a", newline="") as csvfile:
        csvwrite = csv.writer(csvfile)

        if not file_exists:
            headers = [f"feature{i+1}" for i in range(len(metric))]
            headers.append("label")
            csvwrite.writerow(headers)

        data_line = metric + [power]
        csvwrite.writerow(data_line)


def parse_perf_metrics():
    try:
        perf_file_path = "./perf_metrics.dat"
        core_temp_file_path = "./core_temp.dat"

        # Read the perf_metrics.dat file
        with open(perf_file_path, "r") as perf_file:
            perf_output = perf_file.read()

        # Split the perf file content into lines for processing
        perf_output_lines = perf_output.split("\n")

        # List to store the extracted values from perf_metrics.dat
        perf_extracted_values = []

        # Extract elapsed time from the file
        time_match = re.search(r"(\d+\.\d+)\s+seconds\s+time\s+elapsed", perf_output)
        if not time_match:
            raise ValueError("Elapsed time not found in perf_metrics.dat")
        time_elapsed = float(time_match.group(1))

        for line in perf_output_lines:
            # Stop processing further lines once the marker is reached.
            if "seconds time elapsed" in line:
                break
            # Match lines that start with numbers and a metric name
            match = re.search(r"^ *([\d,\.]+)\s+([a-zA-Z\-/]+)", line)
            if match:
                # Extract the numeric value, remove commas and normalize by elapsed time
                value = float(match.group(1).replace(",", ""))
                value = value / time_elapsed
                formatted_value = float(f"{value:.2f}")
                perf_extracted_values.append(formatted_value)

        # Read the core_temp.dat file
        with open(core_temp_file_path, "r") as core_temp_file:
            core_temp_output = core_temp_file.read()

        # Process core_temp file content and collect values
        core_temp_values = []
        for line in core_temp_output.split("\n"):
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
        file_path = "./perf_energy.dat"
        with open(file_path, "r") as file:
            perf_output = file.read()

        # Extract power and time data
        pkg_energy = float(
            re.search(r"(\d+\.\d+)\s+Joules\s+power/energy-pkg/", perf_output).group(1)
        )
        #        mem_energy = float(re.search(r'(\d+\.\d+)\s+Joules\s+power/energy-ram/', perf_output).group(1))
        time_elapsed = float(
            re.search(r"(\d+\.\d+)\s+seconds\s+time\s+elapsed", perf_output).group(1)
        )
        calc_result = float(f"{pkg_energy / time_elapsed:.2f}")

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
        filtered_metrics_str = ",".join(filtered_metrics)
        #        print(filtered_metrics_str)
        command = f"perf stat -e {filtered_metrics_str} -a -o ./perf_metrics.dat python3 ./coretemp_simp.py 1"

        process = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Process the perf output if needed
        # Example: process.stdout, process.stderr
    except Exception as e:
        print(f"An error occurred while running perf: {e}")


def run_perf_energy():
    try:
        command = "perf stat -e power/energy-pkg/ -a -o ./perf_energy.dat sleep 1"
        process = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception as e:
        print(f"An error occurred while running perf for energy: {e}")


def run_stress_ng():
    try:

        fp_thread = threading.Thread(target=run_perf_metrics)
        energy_thread = threading.Thread(target=run_perf_energy)

        fp_thread.start()
        energy_thread.start()
        command = f"cpupower monitor sleep 1"
        process = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        fp_thread.join()
        energy_thread.join()

        # Measure power consumption and other metrics
        truth = parse_power_consumption()
        perf_metrics = parse_perf_metrics()

        metrics = parse_cpu_data(process.stdout, perf_metrics)
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
