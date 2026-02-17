#!/bin/bash

CGROUP_ROOT="/sys/fs/cgroup"
USER_CGROUP="$CGROUP_ROOT/user"
CRITICAL_CGROUP="$CGROUP_ROOT/critical"

# Ensure both controllers are explicitly enabled at root level
for controller in cpuset cpu; do
    if grep -qw "$controller" "$CGROUP_ROOT/cgroup.controllers"; then
        echo "+$controller" > "$CGROUP_ROOT/cgroup.subtree_control"
    fi
done

#rmdir $USER_CGROUP
#rmdir $CRITICAL_CGROUP

# Create cgroups explicitly
mkdir -p "$USER_CGROUP"
mkdir -p "$CRITICAL_CGROUP"

# Explicitly enable controllers inside the child cgroups
echo "+cpuset +cpu" > "$USER_CGROUP/cgroup.subtree_control" || true
echo "+cpuset +cpu" > "$CRITICAL_CGROUP/cgroup.subtree_control" || true

# Determine total CPUs early so we can use it in our math
TOTAL_CPUS=$(lscpu -p=cpu | grep -E "^[0-9]" | wc -l)
ALL_CPUS="0-$((TOTAL_CPUS - 1))"

# Calculate the new max value: 100 * cores * 100,000
CPU_MAX_VAL=$(( 100 * TOTAL_CPUS * 100000 ))

# Set cpu.max using the calculated value
echo "$CPU_MAX_VAL 100000" > "$CRITICAL_CGROUP/cpu.max"
echo "$CPU_MAX_VAL 100000" > "$USER_CGROUP/cpu.max"

# Restore CPU affinity (all cores)
echo "$ALL_CPUS" > "$CRITICAL_CGROUP/cpuset.cpus"
echo "$ALL_CPUS" > "$USER_CGROUP/cpuset.cpus"

echo "Restored CPU affinity and set cpu.max to $CPU_MAX_VAL for both cgroups."
