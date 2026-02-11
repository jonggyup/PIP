#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./set_cpus.sh <cgroup_name> <num_cpus>
#   ./set_cpus.sh <cgroup_name> <num_cpus> <cpu_util_percent>
if [ $# -eq 2 ]; then
    CGROUP="$1"
    NUM_CPUS="$2"
    UTIL=100
elif [ $# -eq 3 ]; then
    CGROUP="$1"
    NUM_CPUS="$2"
    UTIL="$3"
else
    echo "Usage:" >&2
    echo "  $0 <cgroup_name> <num_cpus>" >&2
    echo "  $0 <cgroup_name> <num_cpus> <cpu_util_percent>" >&2
    exit 1
fi

CRIT="critical"
CGROUP_ROOT="/sys/fs/cgroup/"
CGP="/sys/fs/cgroup/$CGROUP"
CRP="/sys/fs/cgroup/$CRIT"

# ensure cgroups exist
for P in "$CGP" "$CRP"; do
    [ -d "$P" ] || mkdir -p "$P"
done

# Ensure both controllers are explicitly enabled at root level
for controller in cpuset cpu; do
    if grep -qw "$controller" "$CGROUP_ROOT/cgroup.controllers"; then
        echo "+$controller" > "$CGROUP_ROOT/cgroup.subtree_control"
    fi
done



# — original core‐parsing block —
declare -A core_groups
while IFS=',' read -r cpu core socket; do
    key="${socket}_${core}"
    core_groups["$key"]="${core_groups["$key"]:+${core_groups["$key"]} }$cpu"
done < <(lscpu -p=CPU,CORE,SOCKET | grep -v '^#')
# — end original block —

# pick first NUM_CPUS in socket/core order
sorted_keys=$(printf "%s\n" "${!core_groups[@]}" | sort -t_ -k1,1n -k2,2n)
selected=()
for key in $sorted_keys; do
    for c in ${core_groups[$key]}; do
        selected+=("$c")
        [[ ${#selected[@]} -ge $NUM_CPUS ]] && break 2
    done
done

if [ ${#selected[@]} -lt $NUM_CPUS ]; then
    echo "Error: only ${#selected[@]} CPUs available, but $NUM_CPUS requested." >&2
    exit 1
fi

# compute remaining for critical
mapfile -t all_cpus < <(lscpu -p=CPU | grep -v '^#' | cut -d, -f1)
declare -A used
for c in "${selected[@]}"; do used[$c]=1; done
remaining=()
for c in "${all_cpus[@]}"; do
    [[ -z "${used[$c]+x}" ]] && remaining+=("$c")
done

# write cpusets
USR=$(IFS=,; echo "${selected[*]}")
CRT=$(IFS=,; echo "${remaining[*]}")
echo "$USR" > "$CGP/cpuset.cpus"
echo "0"   > "$CGP/cpuset.mems"
echo "$CRT" > "$CRP/cpuset.cpus"
echo "0"     > "$CRP/cpuset.mems"

# set cpu.max = PERIOD * NUM_CPUS * UTIL/100
PERIOD=100000
QUOTA=$(( PERIOD * NUM_CPUS * UTIL / 100 ))
echo "${QUOTA} ${PERIOD}" > "$CGP/cpu.max"
