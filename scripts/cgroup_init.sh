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

# After controllers are enabled explicitly, you can safely set cpu.max
echo "max 100000" > "$CRITICAL_CGROUP/cpu.max"
echo "max 100000" > "$USER_CGROUP/cpu.max"

# Determine total CPUs
TOTAL_CPUS=$(lscpu -p=cpu | grep -E "^[0-9]" | wc -l)
ALL_CPUS="0-$((TOTAL_CPUS - 1))"

# Restore CPU affinity (all cores)
echo "$ALL_CPUS" > "$CRITICAL_CGROUP/cpuset.cpus"
echo "$ALL_CPUS" > "$USER_CGROUP/cpuset.cpus"

echo "Restored CPU affinity and cpu.max to unlimited for both cgroups."

