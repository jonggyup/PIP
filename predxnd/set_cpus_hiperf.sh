#!/bin/bash
# Usage: ./set_cpus.sh <cgroup_name> <num_cpus>
set -euo pipefail

CGROUP_NAME="$1"
NUM_CPUS="$2"

CGROUP_PATH="/sys/fs/cgroup/$CGROUP_NAME"

# Ensure the cgroup exists
if [ ! -d "$CGROUP_PATH" ]; then
    echo "Creating cgroup $CGROUP_NAME"
    mkdir -p "$CGROUP_PATH"
fi

# Ensure cpuset controller is enabled
if ! grep -qw cpuset /sys/fs/cgroup/cgroup.subtree_control; then
    echo "+cpuset" > /sys/fs/cgroup/cgroup.subtree_control
fi

# Parse topology
mapfile -t cpu_list < <(
    lscpu -p=CPU,CORE,SOCKET,NODE | grep -v '^#' | sort -t, -k4,4 -k3,3 -k2,2 | awk -F, '{print $1":"$2":"$3":"$4}'
)

declare -A selected_cores
declare -a final_cpus

for entry in "${cpu_list[@]}"; do
    IFS=":" read -r cpu core socket node <<< "$entry"

    # Avoid selecting both SMT siblings
    key="${core}_${socket}_${node}"
    if [[ -z "${selected_cores[$key]+x}" ]]; then
        selected_cores["$key"]=$cpu
        final_cpus+=("$cpu")
        [[ "${#final_cpus[@]}" -ge "$NUM_CPUS" ]] && break
    fi
done

if [[ "${#final_cpus[@]}" -lt "$NUM_CPUS" ]]; then
    echo "Warning: Not enough physical cores. Including SMT siblings."
    for entry in "${cpu_list[@]}"; do
        cpu="${entry%%:*}"
        if [[ ! " ${final_cpus[*]} " =~ " ${cpu} " ]]; then
            final_cpus+=("$cpu")
            [[ "${#final_cpus[@]}" -ge "$NUM_CPUS" ]] && break
        fi
    done
fi

CPU_RANGE=$(echo "${final_cpus[@]}" | tr ' ' ',' | sed -E 's/,/,/g')

# Apply cpus to cgroup
echo "Assigning CPUs: $CPU_RANGE to cgroup $CGROUP_NAME"
echo "$CPU_RANGE" > "$CGROUP_PATH/cpuset.cpus"
echo "0" > "$CGROUP_PATH/cpuset.mems" # assumes all memory nodes are usable

# Optional: move all existing processes (if any) to update affinity
# for pid in $(cat "$CGROUP_PATH/cgroup.procs"); do
#     taskset -cp "$CPU_RANGE" "$pid"
# done

