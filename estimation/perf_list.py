import subprocess

# List of metrics to evaluate
metrics = [
    "cpu-cycles", "instructions", "cache-references", "cache-misses",
    "branches", "branch-misses", "bus-cycles", "ref-cycles",
    "context-switches", "cpu-migrations", "page-faults",
    "L1-dcache-loads", "L1-dcache-load-misses", "L1-icache-load-misses",
    "LLC-loads", "LLC-load-misses", "dTLB-loads", "dTLB-load-misses",
    "msr/aperf/", "msr/mperf/", "msr/pperf/", "fp_arith_inst_retired.scalar_double",
    "fp_arith_inst_retired.scalar_single", "fp_arith_inst_retired.128b_packed_double",
    "fp_arith_inst_retired.128b_packed_single", "fp_arith_inst_retired.256b_packed_double",
    "fp_arith_inst_retired.256b_packed_single", "fp_arith_inst_retired.512b_packed_double"
]

def check_perf_support(metrics):
    try:
        # Run `perf list` to get all supported events
        result = subprocess.run(["perf", "list"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            print(f"Error running 'perf list': {result.stderr}")
            return

        supported_events = result.stdout
        supported_metrics = []
        unsupported_metrics = []

        # Check each metric in the list
        for metric in metrics:
            if metric in supported_events:
                supported_metrics.append(metric)
            else:
                unsupported_metrics.append(metric)

        # Print results
        print("Supported Metrics:")
        for m in supported_metrics:
            print(f"  - {m}")

        print("\nUnsupported Metrics:")
        for m in unsupported_metrics:
            print(f"  - {m}")

    except FileNotFoundError:
        print("Error: 'perf' command not found. Make sure 'perf' is installed and available in your PATH.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# Run the check
check_perf_support(metrics)

