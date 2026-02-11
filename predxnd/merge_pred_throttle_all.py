#!/usr/bin/env python3
import socket
import json
import subprocess
import os
import time
import numpy as np
import sys
import re
import joblib
import signal
import threading
import warnings
warnings.filterwarnings(action='ignore', category=UserWarning)

cpu_index_map = {}
metrics = [
    "cpu_clk_unhalted.ref_tsc", "cpu_clk_unhalted.thread_p", "LLC-load-misses", "instructions",
    "cpu-cycles", "cpu-clock", "cache-misses", "cache-references",
    "branches", "branch-misses", "bus-cycles", "ref-cycles",
    "context-switches", "cpu-migrations", "page-faults",
    "L1-dcache-loads", "L1-dcache-load-misses", "L1-icache-load-misses",
    "LLC-loads", "dTLB-loads", "dTLB-load-misses",
    "msr/aperf/", "msr/mperf/", "msr/pperf/", "fp_arith_inst_retired.scalar_double",
    "fp_arith_inst_retired.scalar_single", "fp_arith_inst_retired.128b_packed_double",
    "fp_arith_inst_retired.128b_packed_single", "fp_arith_inst_retired.256b_packed_double",
    "fp_arith_inst_retired.256b_packed_single", "fp_arith_inst_retired.512b_packed_double"
]

HOST, PORT = "0.0.0.0", 9999

def get_cpu_util_limit(cg_path):
    # read cpu.max
    qm = open(f"{cg_path}/cpu.max").read().split()
    if qm[0] == "max":
        return 100.0
    quota, period = float(qm[0]), float(qm[1])
    # read cpuset.cpus.effective
    cpustr = open(f"{cg_path}/cpuset.cpus.effective").read().strip()
    cores = []
    for part in cpustr.split(","):
        if "-" in part:
            lo, hi = map(int, part.split("-"))
            cores.extend(range(lo, hi+1))
        else:
            cores.append(int(part))
    n = len(cores)
    return (quota / period / n) * 100.0 if n > 0 else 100.0

def get_cgroup_cores(path):
    with open(f"{path}/cpuset.cpus", "r") as f:
        s = f.read().strip()
    out = []
    for p in s.split(","):
        if "-" in p:
            a,b = map(int,p.split("-"))
            out.extend(range(a,b+1))
        else:
            out.append(int(p))
    return out

with open('./topol_metric_size.dat','r') as f:
    perf_metric_index = int(f.read().split()[1])

def get_supported_metrics():
    r = subprocess.run(['perf','list'], capture_output=True, text=True)
    return r.stdout if r.returncode==0 else None

def filter_supported_metrics(metrics, sup):
    return [m for m in metrics if sup and m in sup]

def parse_perf_metrics():
    out = open('./perf_metrics.dat').read()
    t = float(re.search(r'(\d+\.\d+)\s+seconds', out).group(1))
    vals = [
        round(float(m.group(1).replace(',',''))/t,2)
        for line in out.split('\n')
        if (m := re.search(r'^ *([\d,\.]+)\s+([\w\-/]+)', line))
    ]
    temps = [float(l.strip()) for l in open('./core_temp.dat') if l.strip()]
    return temps + vals

def parse_power_consumption():
    o = open('./perf_energy.dat').read()
    pkg = float(re.search(r'(\d+\.\d+)\s+Joules', o).group(1))
    t   = float(re.search(r'(\d+\.\d+)\s+seconds', o).group(1))
    return round(pkg/t,2)

def parse_cpu_data(output, cpu_metrics):
    fields, ids = [], []
    c0 = None
    for line in output.splitlines():
        parts = [e.strip() for e in line.split("|") if e.strip()]
        if not parts: continue
        if c0 is None and 'C0' in parts:
            c0 = parts.index('C0'); continue
        if c0 is not None and parts[0].isdigit() and len(parts)>c0:
            cpu = int(parts[2]); ids.append(cpu)
            vals = parts[c0:]; fields.extend([float(x) for x in vals])
    global cpu_index_map
    cpu_index_map = {cpu: idx for idx,cpu in enumerate(ids)}
    fields.extend(cpu_metrics)
    return fields

def run_perf_metrics():
    sup = get_supported_metrics()
    fm  = filter_supported_metrics(metrics, sup)
    cmd = f"perf stat -e {','.join(fm)} -a -o ./perf_metrics.dat python3 ./coretemp_simp.py 1"
    subprocess.run(cmd, shell=True)

def run_perf_energy():
    subprocess.run('perf stat -e power/energy-pkg/ -a -o ./perf_energy.dat sleep 1', shell=True)

def predict_power_all(feature_map):
    arr   = np.array(feature_map).reshape(1,-1)
    model = joblib.load('../MLs/CatBoost_model.joblib')
    return model.predict(arr)[0]

def predict_power_all_one(feature_map):
    arr   = np.array(feature_map).reshape(1,-1)
    model = joblib.load('../MLs/CatBoost_model-v1.1.joblib')
    return model.predict(arr)[0]

def predict_power_all_two(feature_map):
    arr   = np.array(feature_map).reshape(1,-1)
    model = joblib.load('../MLs/CatBoost_model-v1.2.joblib')
    return model.predict(arr)[0]


def get_local_feature_map():
    t1 = threading.Thread(target=run_perf_metrics)
    t2 = threading.Thread(target=run_perf_energy)
    t1.start(); t2.start()
    out = subprocess.run('cpupower monitor sleep 1', shell=True, stdout=subprocess.PIPE, text=True).stdout
    t1.join(); t2.join()
    return parse_cpu_data(out, parse_perf_metrics()), parse_power_consumption()

def merge_remote_data(local_list, remote_data, cgroup_cpus, local_limit):
    remote_num = remote_data['num_cores']
    rp_cp       = remote_data['cpupower_fields'].copy()
    rp_perf     = remote_data['perf_counts']
    rp_temps    = remote_data.get('temperatures', [])
    remote_lim  = remote_data['cpu_limit_remote']
    throttle    = local_limit

    feats_per  = len(rp_cp)//remote_num
    perf_cnt   = len(rp_perf)
    total_len  = len(local_list)
    cores_loc  = (total_len - perf_cnt)//(feats_per+1)
    cp_end     = feats_per*cores_loc
    temps_st   = cp_end
    temps_en   = temps_st+cores_loc
    perf_st    = temps_en

    lc = local_list[:cp_end]
    lt = local_list[temps_st:temps_en]
    lp = local_list[perf_st:perf_st+perf_cnt]

    # per-core throttle logic on rp_cp
    """
    for i, c in enumerate(cgroup_cpus):
        idex = cpu_index_map[c]
        idx = core*feats_per
        if idx>=len(rp_cp): continue
        rp_cp[idx]     = throttle
        rp_cp[idx+1]   = 100-throttle
        rp_cp[idx+5]   = 100-throttle
        rp_cp[idx+2]   = rp_cp[idx+2]
        print("yes")


        if throttle>remote_lim:
            if rp_cp[idx]>=remote_lim:
                rp_cp[idx]     = max(rp_cp[idx], throttle)
                rp_cp[idx+1]   = 100-throttle
                rp_cp[idx+5]   = 100-throttle
                rp_cp[idx+2]   = rp_cp[idx+2]
        else:
            rp_cp[idx] = min(rp_cp[idx], throttle)
            if idx+1<len(rp_cp) and rp_cp[idx+1]<100-throttle:
                rp_cp[idx+1]=100-throttle
            if idx+5<len(rp_cp) and rp_cp[idx+5]<100-throttle:
                rp_cp[idx+5]=100-throttle
                rp_cp[idx+2]=rp_cp[idx+2]
    """

    # merge adjusted cp fields
    for i,c in enumerate(cgroup_cpus):
        idx = cpu_index_map[c]
        lidx = idx * feats_per
        ridx = i * feats_per

#        lc[ridx*feats_per:(ridx+1)*feats_per] = rp_cp[start:start+feats_per]
        if rp_cp[ridx] > throttle:
            lc[lidx]     = throttle
            lc[lidx+1]   = 100-throttle
            lc[lidx+5]   = 100-throttle
            lc[lidx+2]   = rp_cp[ridx+2]
        else:
            lc[lidx]     = rp_cp[ridx]
            lc[lidx+1]   = rp_cp[ridx+1]
            lc[lidx+5]   = rp_cp[ridx+5]
            lc[lidx+2]   = rp_cp[ridx+2]


        if rp_temps:
            lt[c] = rp_temps[i]

    # scale perf and add
    ratio = (throttle/remote_lim) if remote_lim>0 else 1.0
    mp    = [a + b*ratio for a,b in zip(lp, rp_perf)]

    return lc + lt + mp

def signal_handler(sig, frame):
    if os.path.exists('perf-training.dat'):
        os.remove('perf-training.dat')
    sys.exit(0)

def server_loop(cgroup_name):
    cg_path = f"/sys/fs/cgroup/{cgroup_name}"
    signal.signal(signal.SIGINT, signal_handler)
    sock = socket.socket(); sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
    sock.bind((HOST,PORT)); sock.listen(); sock.settimeout(1)
    print(f"Listening on {HOST}:{PORT}...")

    while True:
        local_map, truth = get_local_feature_map()
        cpus = get_cgroup_cores(cg_path)
        fmap = local_map

        try:
            conn, addr = sock.accept()
            with conn:
                buf = ""
                while True:
                    local_map, truth = get_local_feature_map()
                    data = conn.recv(4096).decode()
                    if not data: break
                    buf += data
                    while "\n" in buf:
                        line, buf = buf.split("\n",1)
                        if not line.strip(): continue
                        payload    = json.loads(line)
                        local_lim  = get_cpu_util_limit(cg_path)
                        fmap       = merge_remote_data(local_map, payload, cpus, local_lim)
                        print(fmap)
                        est        = predict_power_all(fmap)
                        est_one    = predict_power_all_one(fmap)
                        est_two    = predict_power_all_two(fmap)
                        conn.sendall((json.dumps({"estimated_power": est})+"\n").encode())
                        print(f"Truth: {truth:.2f} Estimated Power: {est:.2f} Estimated Power: {est_one:.2f} Estimated Power: {est_two:.2f}")
            print(f"Disconnected {addr}")

        except socket.timeout:
            pass
        except Exception as e:
            print(f"Socket error: {e}")

        print(f"Truth: {truth:.2f}")

if __name__ == "__main__":
    if len(sys.argv)!=2:
        print("Usage: python3 thisfile.py <cgroup_name>"); sys.exit(1)
    server_loop(sys.argv[1])
