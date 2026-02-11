#!/usr/bin/env python3
"""
cgroup_monitor.py

Monitors core occupation, performance counters, per‐core C‐state/frequency, and
per‐core temperature (mapped to logical cores) for a specified cgroup. Prints
one JSON object per second with:
  - num_cores
  - cpupower_fields   (num_cores × 7 floats)
  - perf_counts       (one value per supported metric)
  - temperatures      (num_cores floats)

Usage:
    python3 cgroup_monitor.py <cgroup_name>
"""

import os
import sys
import time
import psutil
import subprocess
import json
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
        return [int(line)
                for line in f.read().splitlines()
                if line.strip().isdigit()]


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
    cmd = [
        "perf", "stat", "-a", "-e", events_str,
        "-G", cgroup_name, "-x,", "sleep", "1"
    ]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
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
        raw_val = parts[0]
        event_printed = parts[2]
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
        return subprocess.run(
            ["sensors"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False
        ).stdout
    except Exception:
        return ""


def parse_sensors_output(output):
    """
    Parses 'sensors' output for per‐physical‐core temperatures.
    Returns {physical_core: [temperatures], …}.
    """
    temps = defaultdict(list)
    socket = 0
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("Package id"):
            parts = line.split()
            try:
                socket = int(parts[2].strip(":"))
            except Exception:
                socket = 0
        elif line.startswith("Core"):
            parts = line.split(":")
            try:
                core_num = int(parts[0].split()[1])
                phys_id = core_num * 2 + socket
            except Exception:
                continue
            try:
                tval = float(parts[1].split("°")[0].strip().strip("+"))
            except Exception:
                continue
            temps[phys_id].append(tval)
    return temps


def average_temperatures(temp_dict):
    """
    Given {phys_core: [temps…]}, return {phys_core: avg_temp}.
    """
    return {core: sum(vals) / len(vals)
            for core, vals in temp_dict.items() if vals}


def get_core_mapping():
    """
    Returns {physical_core: [logical_core, …], …} via `lscpu -p=cpu,core`.
    """
    result = subprocess.run(
        ["lscpu", "-p=cpu,core"],
        stdout=subprocess.PIPE,
        text=True,
        check=False
    ).stdout

    mapping = defaultdict(list)
    for line in result.splitlines():
        if line.startswith("#"):
            continue
        logical, physical = map(int, line.split(","))
        mapping[physical].append(logical)
    return mapping

def parse_cpu_data(output, cpu_metrics, temps_logical, cpuset_cores):
    """
    Parse `cpupower monitor` output; for each cpuset core, collect exactly
    seven floats [C0, Cx, Freq, POLL, C1, C1E, C6]. Then append
    cpu_metrics + temperatures. Returns one flat list of length
    (num_cores×7 + len(cpu_metrics) + num_cores), and the ordered list of CPU IDs.
    """
    parsed = []
    lines = output.splitlines()

    # 1) Find header (line containing both "CPU" and "C0")
    c0_index = None
    col_idx = {}
    for line in lines:
        elems = [e.strip() for e in line.strip().split("|") if e.strip()]
        if "CPU" in elems and "C0" in elems:
            col_idx = {name: idx for idx, name in enumerate(elems)}
            c0_index = col_idx["C0"]
            break

    if c0_index is None:
        parsed.extend(cpu_metrics)
        for c in sorted(cpuset_cores):
            parsed.append(temps_logical.get(c, 0.0))
        return parsed, sorted(cpuset_cores)

    want_fields = ["C0", "Cx", "Freq", "POLL", "C1", "C1E", "C6"]
    cpuset_set = set(cpuset_cores)
    per_core_map = {c: [0.0] * 7 for c in cpuset_cores}

    for line in lines:
        elems = [e.strip() for e in line.strip().split("|") if e.strip()]
        if not elems:
            continue
        if "CPU" in elems and "C0" in elems:
            continue
        try:
            cpu_val = int(elems[col_idx["CPU"]])
        except Exception:
            continue
        if cpu_val not in cpuset_set:
            continue

        row = []
        for key in want_fields:
            if key in col_idx:
                try:
                    row.append(float(elems[col_idx[key]]))
                except Exception:
                    row.append(0.0)
            else:
                row.append(0.0)
        per_core_map[cpu_val] = row

    sorted_cores = sorted(cpuset_cores)
    for core in sorted_cores:
        parsed.extend(per_core_map.get(core, [0.0] * 7))

    parsed.extend(cpu_metrics)

    for core in sorted_cores:
        parsed.append(temps_logical.get(core, 0.0))

    return parsed, sorted_cores


def get_cpuset_cores(cgroup_name):
    cpuset_path = os.path.join(CGROUP_BASE_PATH, cgroup_name, "cpuset.cpus")
    if not os.path.isfile(cpuset_path):
        return []
    with open(cpuset_path, "r") as f:
        content = f.read().strip()
    cores = []
    for part in content.split(","):
        if "-" in part:
            start, end = map(int, part.split("-"))
            cores.extend(range(start, end + 1))
        else:
            cores.append(int(part))
    return cores


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 cgroup_monitor.py <cgroup_name>", file=sys.stderr)
        sys.exit(1)

    cgroup_name = sys.argv[1]
    if not os.path.isdir(os.path.join(CGROUP_BASE_PATH, cgroup_name)):
        print(f"Error: cgroup '{cgroup_name}' not found", file=sys.stderr)
        sys.exit(1)

    try:
        perf_list = subprocess.run(["perf", "list"], capture_output=True, text=True, check=False).stdout
    except Exception:
        perf_list = ""
    supported = [m for m in METRICS if m in perf_list]
    if not supported:
        print("Error: no perf metrics supported", file=sys.stderr)
        sys.exit(1)

    core_map = get_core_mapping()

    while True:
        cpuset_cores = get_cpuset_cores(cgroup_name)
        if not cpuset_cores:
            time.sleep(1)
            continue

        pids = get_cgroup_pids(cgroup_name)
        core_occ = get_core_occupation(pids)

        cp_cmd = ["/usr/bin/cpupower", "monitor", "sleep", "1"]
        try:
            cp = subprocess.run(cp_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
            cp_out = cp.stdout
        except Exception:
            cp_out = ""

        perf_counts = run_perf_for_cgroup(supported, cgroup_name)
        cpu_metrics = [perf_counts.get(m, 0) for m in supported]

        sensors_out = get_sensors_output()
        phys = parse_sensors_output(sensors_out)
        phys_avg = average_temperatures(phys)

        temps_logical = {}
        for phys_core, tval in phys_avg.items():
            for log_core in core_map.get(phys_core, []):
                temps_logical[log_core] = tval

        parsed, sorted_cpus = parse_cpu_data(cp_out, cpu_metrics, temps_logical, cpuset_cores)

        if parsed:
            num_cores = len(sorted_cpus)
            cpupower_len = num_cores * 7
            perf_len = len(supported)
            temp_len = num_cores

            cpupower_fields = parsed[0:cpupower_len]
            perf_counts_out = parsed[cpupower_len:cpupower_len + perf_len]
            temps_out = parsed[cpupower_len + perf_len:cpupower_len + perf_len + temp_len]

            payload = {
                "num_cores": num_cores,
                "cpus": sorted_cpus,
                "cpupower_fields": cpupower_fields,
                "perf_counts": perf_counts_out,
                "temperatures": temps_out
            }
        else:
            payload = {"error": "no_data"}

        print(json.dumps(payload, separators=(",", ":")))
        sys.stdout.flush()
        time.sleep(1)


if __name__ == "__main__":
    main()
