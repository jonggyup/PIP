#!/bin/bash

set -e

CGROUP_ROOT="/sys/fs/cgroup"
USER_CGROUP="$CGROUP_ROOT/user"
CRITICAL_CGROUP="$CGROUP_ROOT/critical"

# Auto-detect CPUs per socket
get_cpus_by_socket() {
    socket="$1"
    lscpu -p=cpu,socket | grep -E "^[0-9]" | awk -F, -v s="$socket" '$2 == s {print $1}' | paste -sd ',' -
}

# Get available socket IDs
readarray -t SOCKET_IDS < <(lscpu -p=socket | grep -E "^[0-9]" | sort -nu)

if [ "${#SOCKET_IDS[@]}" -lt 2 ]; then
    echo "At least 2 CPU sockets are required."
    exit 1
fi

CRITICAL_SOCKET="${SOCKET_IDS[0]}"
USER_SOCKET="${SOCKET_IDS[1]}"

# Get CPU lists
CRITICAL_CPUS=$(get_cpus_by_socket "$CRITICAL_SOCKET")
USER_CPUS=$(get_cpus_by_socket "$USER_SOCKET")

# Assign CPUs explicitly
echo "$USER_CPUS" > "$USER_CGROUP/cpuset.cpus"
echo "$CRITICAL_CPUS" > "$CRITICAL_CGROUP/cpuset.cpus"

echo "User cgroup CPUs: $USER_CPUS"
echo "Critical cgroup CPUs: $CRITICAL_CPUS"

# Start stress-ng workloads explicitly in cgroups
stress-ng -c 32 &
echo $! > "$CRITICAL_CGROUP/cgroup.procs"


stress-ng -c 32 &
echo $! > "$USER_CGROUP/cgroup.procs"

python3 user_throttle.py

pkill -ef stress-ng
