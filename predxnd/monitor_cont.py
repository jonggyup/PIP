#!/usr/bin/env python3
"""
cgroup_monitor.py

Monitors core occupation, performance counters, per-core C-state/frequency, and
per-core temperature (mapped to logical cores) for a specified cgroup. Prints
one line per second with:
    <num_cores>,<flattened cpupower fields for each core>,<perf metrics>,<temps>

Usage:
    python3 cgroup_monitor.py <cgroup_name>
"""

import os
import sys
import time
import psutil
import subprocess
import numpy as np
from collections import Counter, defaultdict

METRICS = [
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
    "fp_arith_inst_retired.512b_packed_double"
]

CGROUP_BASE_PATH = "/sys/fs/cgroup"

def get_cgroup_pids(cgroup_name):
    procs_path = os.path.join(CGROUP_BASE_PATH, cgroup_name, "cgroup.procs")
    if not os.path.isfile(procs_path):
        return []
    with open(procs_path, "r") as f:
        return [int(line) for line in f.read().splitlines() if line.strip().isdigit()]

def get_core_occupation(pids):
    core_counts = Counter()
    for pid in pids:
        try:
            cpu = psutil.Process(pid).cpu_num()
            if cpu is not None:
                core_counts[cpu] += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return dict(core_counts)

def run_perf_for_cgroup(events, cgroup_name):
    events_str = ",".join(events)
    cmd = ["perf", "stat", "-a", "-e", events_str, "-G", cgroup_name, "-x,", "sleep", "1"]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, check=False)
    except Exception:
        return {}
    counts = {}
    for line in proc.stderr.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",")
        if len(parts) < 3:
            continue
        raw_val, event_printed = parts[0], parts[2]
        for ev in events:
            if event_printed.startswith(ev):
                try:
                    val = int(raw_val.replace(",", ""))
                except ValueError:
                    try:
                        val = float(raw_val.replace(",", ""))
                    except ValueError:
                        continue
                counts[ev] = val
                break
    return counts

def get_sensors_output():
    try:
        return subprocess.run(["sensors"], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True, check=False).stdout
    except Exception:
        return ""

def parse_sensors_output(output):
    """
    Parses 'sensors' output for per-physical-core temperatures.
    Returns {physical_core: [temps], ...}.
    """
    temps = defaultdict(list)
    socket = 0
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("Package id"):
            # Example: "Package id 1:  +74.0°C ..."
            parts = line.split()
            try:
                # parts[2] is like "1:"
                socket = int(parts[2].strip(":"))
            except Exception:
                socket = 0
        elif line.startswith("Core"):
            # Example: "Core 0:        +69.0°C  ..."
            parts = line.split(":")
            try:
                core_num = int(parts[0].split()[1])
                phys_id = core_num * 2 + socket
            except Exception:
                continue
            try:
                temp = float(parts[1].split("°")[0].strip().strip("+"))
            except Exception:
                continue
            temps[phys_id].append(temp)
    return temps

def average_temperatures(temp_dict):
    """
    Given {phys_core: [temps]}, returns {phys_core: avg_temp}.
    """
    return {core: sum(vals)/len(vals) for core, vals in temp_dict.items() if vals}

def get_core_mapping():
    """
    Returns {physical_core: [logical_core, ...], ...} using 'lscpu -p=cpu,core'.
    """
    result = subprocess.run(['lscpu', '-p=cpu,core'], stdout=subprocess.PIPE,
                            text=True, check=False)
    core_mapping = defaultdict(list)
    for line in result.stdout.splitlines():
        if line.startswith('#'):
            continue
        logical, physical = map(int, line.split(','))
        core_mapping[physical].append(logical)
    return core_mapping

def parse_cpu_data(output, cpu_metrics, temps_logical, occupied_cores):
    """
    Given cpupower-monitor output, a list of cpu_metrics (perf values),
    temps_logical {logical_core: temp}, and occupied_cores list,
    parse lines after header-to-'C0', concatenate per-core C-state/freq data,
    then append cpu_metrics, then append temperatures for each occupied core
    (ascending logical).
    """
    parsed = []
    tmp = []
    c0_index = None
    for line in output.split('\n'):
        elems = [e.strip() for e in line.strip().split("|") if e.strip()]
        if 'CPU' in elems and c0_index is None:
            if 'C0' in elems:
                c0_index = elems.index('C0')
            continue
        if elems and c0_index is not None:
            tmp.append(elems[c0_index:])
    if tmp:
        parsed = list(np.concatenate(tmp))
    parsed.extend(cpu_metrics)
    for core in sorted(occupied_cores):
        parsed.append(temps_logical.get(core, 0.0))
    return parsed

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 cgroup_monitor.py <cgroup_name>", file=sys.stderr)
        sys.exit(1)
    cgroup_name = sys.argv[1]
    if not os.path.isdir(os.path.join(CGROUP_BASE_PATH, cgroup_name)):
        print(f"Error: cgroup '{cgroup_name}' not found", file=sys.stderr)
        sys.exit(1)

    try:
        perf_list = subprocess.run(["perf", "list"], capture_output=True,
                                   text=True, check=False).stdout
    except Exception:
        perf_list = ""
    supported = [m for m in METRICS if m in perf_list]
    if not supported:
        print("Error: no perf metrics supported", file=sys.stderr)
        sys.exit(1)

    core_map = get_core_mapping()

    while True:
        pids = get_cgroup_pids(cgroup_name)
        core_occ = get_core_occupation(pids)
        occupied = list(core_occ.keys())
        num_cores = len(occupied)

        # 1) cpupower monitor
        try:
            cp = subprocess.run(["cpupower", "monitor", "sleep", "1"],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL,
                                text=True, check=False)
            cp_out = cp.stdout
        except Exception:
            cp_out = ""

        # 2) perf metrics
        perf_counts = run_perf_for_cgroup(supported, cgroup_name)
        cpu_metrics = [perf_counts.get(m, 0) for m in supported]

        # 3) sensors -> physical temps
        sensors_out = get_sensors_output()
        phys = parse_sensors_output(sensors_out)
        phys_avg = average_temperatures(phys)

        # 4) map to logical temps
        temp_logical = {}
        for phys_core, tval in phys_avg.items():
            for log_core in core_map.get(phys_core, []):
                temp_logical[log_core] = tval

        # 5) parse & combine
        parsed = parse_cpu_data(cp_out, cpu_metrics, temp_logical, occupied)

        # 6) print minimal
        if parsed:
            print(f"{num_cores}," + ",".join(str(x) for x in parsed))
        else:
            print("no_data")

        sys.stdout.flush()
        time.sleep(1)

if __name__ == "__main__":
    main()

