#!/usr/bin/env python3
import sys, json

# --- update here with your metric labels ---
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
# ---------------------------------------------

def read_values(path, key):
    try:
        data = json.load(open(path))
    except Exception as e:
        sys.exit(f"Failed to read JSON from {path}: {e}")
    if key not in data or not isinstance(data[key], list):
        sys.exit(f"Key '{key}' not found or is not a list in {path}")
    return [float(x) for x in data[key]]

def main():
    if len(sys.argv) != 4:
        sys.exit(f"Usage: {sys.argv[0]} remote.json local.json <json_key>")

    remote_path, local_path, key = sys.argv[1], sys.argv[2], sys.argv[3]
    remote = read_values(remote_path, key)
    local  = read_values(local_path, key)

    if len(remote) != len(local):
        sys.exit(f"Error: '{key}' length mismatch ({len(remote)} vs {len(local)})")

    # choose labels
    if key == 'perf_counts':
        labels = METRICS
        if len(labels) != len(remote):
            sys.exit(f"Error: METRICS length ({len(labels)}) != '{key}' length ({len(remote)})")
    else:
        labels = [str(i) for i in range(len(remote))]

    for name, r, l in zip(labels, remote, local):
        if l != 0:
            diff = abs(r - l) / l * 100
            print(f"{name:40s} remote={r}, local={l}, diff={diff:.2f}%")
        else:
            print(f"{name:40s} remote={r}, local={l}, diff=undefined (local=0)")

if __name__ == "__main__":
    main()

