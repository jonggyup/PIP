import socket
import json
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
import signal
import threading

warnings.filterwarnings(action='ignore', category=UserWarning)
cpu_index_map = []
# Perf metrics to collect
metrics = [
    "cpu_clk_unhalted.ref_tsc", "cpu_clk_unhalted.thread_p", "LLC-load-misses", "instructions", "cpu-cycles", "cpu-clock", "cache-misses", "cache-references",
    "branches", "branch-misses", "bus-cycles", "ref-cycles",
    "context-switches", "cpu-migrations", "page-faults",
    "L1-dcache-loads", "L1-dcache-load-misses", "L1-icache-load-misses",
    "LLC-loads", "dTLB-loads", "dTLB-load-misses",
    "msr/aperf/", "msr/mperf/", "msr/pperf/", "fp_arith_inst_retired.scalar_double",
    "fp_arith_inst_retired.scalar_single", "fp_arith_inst_retired.128b_packed_double",
    "fp_arith_inst_retired.128b_packed_single", "fp_arith_inst_retired.256b_packed_double",
    "fp_arith_inst_retired.256b_packed_single", "fp_arith_inst_retired.512b_packed_double"
]

HOST = "0.0.0.0"
PORT = 9999


def get_cgroup_cores(cgroup_path):
    with open(f"{cgroup_path}/cpuset.cpus", "r") as f:
        cpus_str = f.read().strip()
    cpus = []
    for part in cpus_str.split(","):
        if "-" in part:
            start, end = map(int, part.split("-"))
            cpus.extend(range(start, end + 1))
        else:
            cpus.append(int(part))
    return cpus

# Read perf metric index from topology file
with open('./topol_metric_size.dat', 'r') as file:
    values = file.read().split()
    perf_metric_index = int(values[1])


def get_supported_metrics():
    try:
        result = subprocess.run(['perf', 'list'], capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else None
    except Exception:
        return None


def filter_supported_metrics(metrics, supported_output):
    return [m for m in metrics if m in supported_output] if supported_output else []


def save_to_file(file_name, metric, power):
    exists = os.path.exists(file_name)
    with open(file_name, 'a', newline='') as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow([f'feature{i+1}' for i in range(len(metric))] + ['label'])
        writer.writerow(metric + [power])


def parse_perf_metrics():
    try:
        with open('./perf_metrics.dat','r') as pf:
            out = pf.read()
        lines = out.split('\n')
        vals = []
        t = float(re.search(r'(\d+\.\d+)\s+seconds', out).group(1))
        for line in lines:
            if 'seconds' in line: continue
            m = re.search(r'^ *([\d,\.]+)\s+([\w\-/]+)', line)
            if m:
                v = float(m.group(1).replace(',',''))/t
                vals.append(round(v,2))
        temps = []
        with open('./core_temp.dat','r') as cf:
            for l in cf:
                if l.strip(): temps.append(float(l.strip()))
        return temps + vals
    except Exception:
        return []


def parse_power_consumption():
    try:
        out = open('./perf_energy.dat','r').read()
        pkg = float(re.search(r'(\d+\.\d+)\s+Joules', out).group(1))
        t = float(re.search(r'(\d+\.\d+)\s+seconds', out).group(1))
        return round(pkg/t,2)
    except Exception:
        return None

def parse_cpu_data(output, cpu_metrics):
    """
    Parses `cpupower monitor` output.
    Returns (cpupower_fields, cpu_ids, cpu_index_map), where:
      - cpupower_fields is a flat list of floats (all C0/Cx/Freq/POLL/C1/C1E/C6 values, in order).
      - cpu_ids is the list of CPU IDs, in the same order.
      - cpu_index_map maps each CPU ID to its index in cpu_ids (i.e., feature‐map index).
    cpu_metrics is just passed through to be appended if you need it here; for local parsing you can pass [].
    """
    cpupower_fields = []
    cpu_ids = []
    c0_index = None
    global cpu_index_map

    for line in output.splitlines():
        parts = [e.strip() for e in line.split("|") if e.strip()]
        if not parts:
            continue
        # detect header
        if c0_index is None and 'C0' in parts:
            c0_index = parts.index('C0')
            continue
        # only data lines start with a digit (the PKG field)
        if c0_index is not None and parts[0].isdigit() and len(parts) > c0_index:
            # CPU id is the 3rd column (index 2)
            cpu_id = int(parts[2])
            cpu_ids.append(cpu_id)
            # grab all fields from C0 onward
            vals = parts[c0_index:]
            cpupower_fields.extend([float(x) for x in vals])

    # build inverse mapping: CPU ID → index in feature map
    cpu_index_map = {cpu: idx for idx, cpu in enumerate(cpu_ids)}

    # tack on any extra metrics
    cpupower_fields.extend(cpu_metrics)
    return cpupower_fields

'''

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



def parse_cpu_data(output, cpu_metrics):
    lines = output.split('\n')
    c0 = None
    tmp = []
    for l in lines:
        els = [e.strip() for e in l.split('|') if e.strip()]
        if 'CPU' in els and c0 is None:
            c0 = els.index('C0'); continue
        if c0 is not None and els:
            tmp.extend(els[c0:])
    return tmp + cpu_metrics

'''
def run_perf_metrics():
    supp = get_supported_metrics()
    fm = filter_supported_metrics(metrics, supp)
    cmd = f"perf stat -e {','.join(fm)} -a -o ./perf_metrics.dat python3 ./coretemp_simp.py 1"
    subprocess.run(cmd, shell=True)


def run_perf_energy():
    subprocess.run('perf stat -e power/energy-pkg/ -a -o ./perf_energy.dat sleep 1', shell=True)


def predict_power_all(feature_map):
    arr = np.array(feature_map).reshape(1,-1)
    model = joblib.load('../MLs/CatBoost_model.joblib')
    return model.predict(arr)[0]


def get_local_feature_map():
    t1 = threading.Thread(target=run_perf_metrics)
    t2 = threading.Thread(target=run_perf_energy)
    t1.start(); t2.start()
    out = subprocess.run('cpupower monitor sleep 1', shell=True, stdout=subprocess.PIPE, text=True).stdout
    t1.join(); t2.join()
    truth = parse_power_consumption()
    perf = parse_perf_metrics()
    return parse_cpu_data(out, perf), truth


def merge_remote_data(local_list, remote_data, cgroup_cpus):
    remote_num   = remote_data['num_cores']
    rp_cp        = remote_data['cpupower_fields']
    rp_perf      = remote_data['perf_counts']
    rp_temps     = remote_data.get('temperatures', [])
    feats_per    = len(rp_cp) // remote_num
    perf_count   = len(rp_perf)
    total_len    = len(local_list)
    cores_local  = (total_len - perf_count) // (feats_per + 1)
    cp_end       = feats_per * cores_local
    temps_start  = cp_end
    temps_end    = temps_start + cores_local
    perf_start   = temps_end

    # Slice local data
    lc = local_list[:cp_end]
    lt = local_list[temps_start:temps_end]
    lp = local_list[perf_start:perf_start + perf_count]

    # Merge
    for i, c in enumerate(cgroup_cpus):
        remote_idx = cpu_index_map[c]
        lc[remote_idx * feats_per:(remote_idx + 1) * feats_per] = rp_cp[i * feats_per:(i + 1) * feats_per]
        lt[c] = rp_temps[i]

    mp = [a + b for a, b in zip(lp, rp_perf)]
    return lc + lt + mp

def signal_handler(sig, frame):
    if os.path.exists('perf-training.dat'): os.remove('perf-training.dat')
    sys.exit(0)


def server_loop(cgroup_path):
    signal.signal(signal.SIGINT, signal_handler)
    last = None
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
    sock.bind((HOST, PORT)); sock.listen(); sock.settimeout(1)
    print(f"Listening on {HOST}:{PORT}...")
    while True:
        local_map, truth = get_local_feature_map()
        cpus = get_cgroup_cores(cgroup_path)
        fmap = None
        try:
            conn, addr = sock.accept()
            with conn:
                buf = ''
                while True:
                    local_map, truth = get_local_feature_map()
                    cpus = get_cgroup_cores(cgroup_path)
                    fmap = None

                    data = conn.recv(4096).decode()
                    if not data: break
                    buf += data
                    while '\n' in buf:
                        line, buf = buf.split('\n',1)
                        if not line.strip(): continue
                        payload = json.loads(line)
                        last = payload
                        fmap = merge_remote_data(local_map, payload, cpus)
 #                       print(f"[{addr}] Remote merged.")
                        est = predict_power_all(fmap)
                        print(f"Truth: {truth:.2f} Estimated Power: {est:.2f}")
                        response = {"estimated_power": est}
                        conn.sendall((json.dumps(response) + '\n').encode())

            print(f"Disconnected {addr}")
        except socket.timeout:
            fmap = local_map
        except Exception as e:
            print(f"Socket error: {e}"); fmap = local_map
        try:
#            est = predict_power_all(fmap)
            print(f"Truth: {truth:.2f}")
        except Exception as e:
            print(f"Inference failed: {e}")

if __name__ == '__main__':
    if len(sys.argv)!=2:
        print("Usage: python3 thisfile.py <cgroup_path>"); sys.exit(1)
    server_loop(f"/sys/fs/cgroup/{sys.argv[1]}")

