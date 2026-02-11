#!/bin/bash

CGROUP_BASE="/sys/fs/cgroup"
USER_CPUS=$(cat "$CGROUP_BASE/user/cpuset.cpus.effective")
CRIT_CPUS=$(cat "$CGROUP_BASE/critical/cpuset.cpus.effective")
DURATION=1

# Define all perf metrics
METRICS=(
    "cpu_clk_unhalted.ref_tsc" "cpu_clk_unhalted.thread_p" "LLC-load-misses" "instructions"
    "cpu-cycles" "cpu-clock" "cache-misses" "cache-references"
    "branches" "branch-misses" "bus-cycles" "ref-cycles"
    "context-switches" "cpu-migrations" "page-faults"
    "L1-dcache-loads" "L1-dcache-load-misses" "L1-icache-load-misses"
    "LLC-loads" "dTLB-loads" "dTLB-load-misses"
    "msr/aperf/" "msr/mperf/" "msr/pperf/"
    "fp_arith_inst_retired.scalar_double" "fp_arith_inst_retired.scalar_single"
    "fp_arith_inst_retired.128b_packed_double" "fp_arith_inst_retired.128b_packed_single"
    "fp_arith_inst_retired.256b_packed_double" "fp_arith_inst_retired.256b_packed_single"
    "fp_arith_inst_retired.512b_packed_double"
)

# Join metrics into comma-separated string
METRIC_LIST=$(IFS=, ; echo "${METRICS[*]}")

# Run perf for each target
USER_OUT=$(perf stat -x, -e "$METRIC_LIST" -C "$USER_CPUS" sleep $DURATION 2>&1)
CRIT_OUT=$(perf stat -x, -e "$METRIC_LIST" -C "$CRIT_CPUS" sleep $DURATION 2>&1)
SYS_OUT=$(perf stat -x, -e "$METRIC_LIST" -a sleep $DURATION 2>&1)

# Header
echo "Metric,User,Critical,User+Critical,System,%Diff"
ORDER=1
# Parse output per metric
for metric in "${METRICS[@]}"; do
    USER_VAL=$(echo "$USER_OUT" | grep ",$metric" | awk -F',' '{gsub(",", "", $1); print $1}')
    CRIT_VAL=$(echo "$CRIT_OUT" | grep ",$metric" | awk -F',' '{gsub(",", "", $1); print $1}')
    SYS_VAL=$(echo "$SYS_OUT" | grep ",$metric" | awk -F',' '{gsub(",", "", $1); print $1}')

    # Skip if any missing or 0
    if [[ -z "$USER_VAL" || -z "$CRIT_VAL" || -z "$SYS_VAL" || "$SYS_VAL" == "0" ]]; then
        echo "$metric,ERROR,ERROR,ERROR,ERROR,ERROR"
        continue
    fi
    SUM_VAL=$(awk -v u="$USER_VAL" -v c="$CRIT_VAL" 'BEGIN { printf "%.2f", u + c }')

    DIFF=$(awk -v sum="$SUM_VAL" -v sys="$SYS_VAL" 'BEGIN { printf "%.2f", (sum - sys) * 100 / sys }')

    echo "$ORDER,$metric,$USER_VAL,$CRIT_VAL,$SUM_VAL,$SYS_VAL,$DIFF%"
    ORDER=$((ORDER + 1))
done

