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

pid_to_time_map = {}
period = sys.argv[1]
columns_to_parse = None
metrics_per_cpu = None
cpu_count = 0

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


# Function to get the current wall clock time in total seconds (hours + minutes + seconds)
def get_wall_clock_time_in_seconds():
    current_time = time.localtime()
    total_seconds = current_time.tm_hour * 3600 + current_time.tm_min * 60 + current_time.tm_sec
    return total_seconds

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


def read_cpu_info():
    try:
        cpu_count = 0
        with open("/proc/stat", "r") as fp:
            for line in fp.readlines():
                if re.match(r"cpu\d+", line):
                    cpu_count += 1
    except Exception as e:
        print(f"Failed to read /proc/stat: {e}")
        exit(1)
    return cpu_count

def read_command(pid):
    try:
        with open(f"/proc/{pid}/comm", 'r') as file:
            return file.read().replace('\0', ' ').strip()
    except Exception as e:
        return None


def cid_list_gen():
    total_time_per_core = [0] * cpu_count
    current_pid = [0] * cpu_count
    global cid_by_cgroup
    cid_by_cgroup = {}

    try:
        # Loop through cgroups in /sys/fs/cgroup
        for cgroup in os.listdir("/sys/fs/cgroup/"):
            if not cgroup.startswith("user"):
                continue  # Process only cgroups starting with 'user'

            cgroup_path = f"/sys/fs/cgroup/{cgroup}/cgroup.procs"
            if os.path.exists(cgroup_path):
                with open(cgroup_path, "r") as fp:
                    pids = fp.read().splitlines()

                    for pid in pids:
                        path = f"/proc/{pid}/stat"
                        try:
                            with open(path, "r") as stat_file:
                                data = stat_file.read()
                                parsed_data = data.split(' ')

                                # Only process running or sleeping tasks
                                if parsed_data[2] in ('R', 'S'):
                                    pid, cpu = int(parsed_data[0]), int(parsed_data[38])
                                    total_cpu_time = int(parsed_data[13]) + int(parsed_data[14])  # User time + System time

                                    if pid in pid_to_time_map:
                                        usage = total_cpu_time - pid_to_time_map[pid]
                                    else:
                                        usage = total_cpu_time

                                    pid_to_time_map[pid] = total_cpu_time  # Update total CPU time for this PID

                                    if 0 <= cpu < cpu_count and total_time_per_core[cpu] <= usage and usage != 0:
                                        current_pid[cpu] = pid
                                        total_time_per_core[cpu] = usage

                        except Exception:
                            continue

    except Exception as e:
        print(f"Failed to open /sys/fs/cgroup directory: {e}")
        exit(1)

    # Mapping CPU usage per cgroup instead of per command
    for i in range(cpu_count):
        pid = current_pid[i]
        if pid == 0:
            continue  # Skip if no PID assigned to this CPU

        # Find the cgroup for this PID
        for cgroup in os.listdir("/sys/fs/cgroup/"):
            if not cgroup.startswith("user"):
                continue  # Only process cgroups starting with 'user'

            cgroup_path = f"/sys/fs/cgroup/{cgroup}/cgroup.procs"
            if os.path.exists(cgroup_path):
                with open(cgroup_path, "r") as fp:
                    pids = fp.read().splitlines()
                    if str(pid) in pids:
                        if cgroup not in cid_by_cgroup:
                            cid_by_cgroup[cgroup] = []
                        cid_by_cgroup[cgroup].append(i)
                        break

    # Sort cgroups by number of CPUs
    cid_by_cgroup = dict(sorted(cid_by_cgroup.items(), key=lambda item: len(item[1]), reverse=True))
    return cid_by_cgroup


def parse_perf_data():
    try:
        file_path = f'./perf-est.dat'

        with open(file_path, 'r') as file:
            perf_output = file.read()

        # Initialize variables for accumulated energy values
        pkg_energy_total = 0
        mem_energy_total = 0
        time_elapsed = 0

        # Split the file content into lines for further processing
        perf_output_lines = perf_output.split('\n')

        # Dictionary to store the extracted values for each CPU
        extracted_values = {}
        for line in perf_output_lines:
            # Skip header and start time lines
            if line.startswith('# started') or 'Performance counter stats' in line:
                continue

            # Extract and accumulate power/energy values
            if 'power/energy-pkg' in line:
                pkg_energy = float(re.search(r'(\d+\.\d+)\s+Joules\s+power/energy-pkg/', line).group(1))
                pkg_energy_total += pkg_energy

            elif 'power/energy-ram' in line:
                mem_energy = float(re.search(r'(\d+\.\d+)\s+Joules\s+power/energy-ram/', line).group(1))
                mem_energy_total += mem_energy

            elif 'seconds time elapsed' in line:
                time_elapsed = float(re.search(r'(\d+\.\d+)\s+seconds\s+time\s+elapsed', line).group(1))

            else:
                # Process CPU data
                match = re.search(r'CPU(\d+)\s+(\d+[\d,\.]*)', line)
                if match:
                    cpu_number = int(match.group(1))
                    value = int(match.group(2).replace(',', ''))

                    # Initialize the list for this CPU if it hasn't been already
                    if cpu_number not in extracted_values:
                        extracted_values[cpu_number] = []

                    extracted_values[cpu_number].append(value)

        # Calculate the combined result
        if time_elapsed > 0:
            calc_result = (pkg_energy_total) / time_elapsed
            for cpu, values in extracted_values.items():
                extracted_values[cpu] = [value / time_elapsed for value in values]
        else:
            calc_result = None

        return calc_result, extracted_values

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
        model = joblib.load('../MLs/CatBoost_model.joblib') #Change the model name to what you want.
        prediction = model.predict(features_array)
        return prediction[0]
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def run_perf_metrics():
    try:
        supported_metrics_output = get_supported_metrics()
        filtered_metrics = filter_supported_metrics(metrics, supported_metrics_output)
        filtered_metrics_str = ','.join(filtered_metrics)
        command = f'perf stat -e {filtered_metrics_str} -a -o ./perf_metrics.dat --no-aggr python3 ./coretemp_simp.py 1'

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


def parse_perf_metrics():
    try:
        perf_file_path = './perf_metrics.dat'
        core_temp_file_path = './core_temp.dat'

        with open(perf_file_path, 'r') as perf_file:
            perf_output = perf_file.read()

        perf_output_lines = perf_output.split('\n')
        extracted_values = {}

        time_elapsed_match = re.search(r'(\d+\.\d+)\s+seconds\s+time\s+elapsed', perf_output)
        time_elapsed = float(time_elapsed_match.group(1)) if time_elapsed_match else 1.0  # default to 1.0 if not found

        for line in perf_output_lines:
            match = re.match(r'CPU(\d+)\s+([\d,]+)', line)
            if match:
                cpu_number = int(match.group(1))
                raw_value = float(match.group(2).replace(',', ''))
                if cpu_number not in extracted_values:
                    extracted_values[cpu_number] = []
                extracted_values[cpu_number].append(raw_value / time_elapsed)

        with open(core_temp_file_path, 'r') as core_temp_file:
            core_temp_values = [float(line.strip()) for line in core_temp_file if line.strip()]

        return extracted_values, core_temp_values

    except Exception as e:
        return None, f"Error: {str(e)}"

def parse_power_consumption():
    try:
        file_path = './perf_energy.dat'
        with open(file_path, 'r') as file:
            perf_output = file.read()

        # Extract power and time data
        pkg_energy = float(re.search(r'(\d+\.\d+)\s+Joules\s+power/energy-pkg/', perf_output).group(1))
        time_elapsed = float(re.search(r'(\d+\.\d+)\s+seconds\s+time\s+elapsed', perf_output).group(1))
        calc_result = float(f"{(pkg_energy) / time_elapsed:.2f}")

        return calc_result
    except Exception as e:
        return None, f"Error: {str(e)}"

def parse_cpu_data(output):
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

    return parsed_data

# Function to run stress-ng
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
        perf_metrics, temp_metrics = parse_perf_metrics()
#        print(perf_metrics)
#        print(temp_metrics)

        core_metrics = parse_cpu_data(process.stdout)

        # Parse the perf data
        cid_by_command = cid_list_gen()
        command_power_pairs = []
        total_power = 0

        wall_clock_seconds = get_wall_clock_time_in_seconds()
        print(f"{wall_clock_seconds}", end=" | ")

        # Read and parse the idle.dat file
        with open('../data/idle.dat', 'r') as file:
            idle_data = file.read()
            # Splitting the data into values
            data_values = idle_data.split(',')
            # Extracting features without the last value and the power value
            base_idle_features = data_values[:-1]
            idle_power = float(data_values[-1])

            aggregated_perf_metrics = [0] * len(perf_metrics[0])
            ref_features = core_metrics.copy()
            for cpu in range(0, cpu_count):
                perf_metrics_list = [float(num) for num in perf_metrics[cpu]]
                for i in range(len(perf_metrics[0])):
                    aggregated_perf_metrics[i] += perf_metrics_list[i]
            ref_features.extend(temp_metrics)
            ref_features.extend(aggregated_perf_metrics)

        for command, cpus in cid_by_command.items():
            app_features = base_idle_features.copy()
            aggregated_perf_metrics = [0] * len(perf_metrics[0])
            for cpu in cpus:
                perf_metrics_list = [float(num) for num in perf_metrics[cpu]]
                feature_positions = cpu * metrics_per_cpu
                app_features[feature_positions:feature_positions + metrics_per_cpu] = core_metrics[feature_positions:feature_positions + metrics_per_cpu]
                for i in range(len(perf_metrics[0])):
                    aggregated_perf_metrics[i] += perf_metrics_list[i]

            start_index = metrics_per_cpu * cpu_count + cpu_count
            end_index = start_index + len(aggregated_perf_metrics)

            # Concatenate perf_metrics[core_id] to the updated features
            app_features[metrics_per_cpu * cpu_count: start_index] = temp_metrics
            app_features[start_index:end_index] = aggregated_perf_metrics

            power = predict_power(app_features)# - idle_power
            total_power += power

            # Append the command and power as a tuple to the list
            command_power_pairs.append((command, power))

        # Sort the list in descending order of power
        command_power_pairs.sort(key=lambda x: x[0], reverse=True)
        ref_power = predict_power(ref_features)

        # Now print each command and its relative power consumption
        for command, power in reversed(command_power_pairs): #command_power_pairs:
            relative_power = power * (ref_power - idle_power) / (total_power)
            #print(f"{command}: {relative_power:.2f}") # end = " | ")
            print(f"{relative_power:.2f}", end = " | ")

        error = abs(ref_power - truth) / truth * 100
        ref_power = ref_power - idle_power


#        print("---------------------------------------------", flush=True)
#        print("----------------- Summary -------------------", flush=True)
#        print(f"Active Power: {ref_power}, Idle Power: {idle_power}, Truth: {truth}, Error(%): {error}", flush=True)
        print(f"{ref_power} | {truth}", flush=True)
#        print("---------------------------------------------", flush=True)



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
    if os.path.exists("perf-est.dat"):
        os.remove("perf-est.dat")
    exit(0)

if __name__ == "__main__":
    # Register the signal handler for SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    cid_list_gen()
    cpu_count = read_cpu_info()
    columns_to_parse, metrics_per_cpu = parse_cpu_info()


    while True:
        stress_thread = threading.Thread(target=run_stress_ng)
        stress_thread.start()
        stress_thread.join()
