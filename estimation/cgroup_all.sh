#!/bin/bash

# Define the cgroup path
CGROUP_PATH="/sys/fs/cgroup/user"

# Check if cgroup already exists, create it if not
if [ ! -d "$CGROUP_PATH" ]; then
    mkdir "$CGROUP_PATH"
fi

# Ensure cgroup v2 is mounted (if not already)
if ! mountpoint -q /sys/fs/cgroup; then
    mount -t cgroup2 none /sys/fs/cgroup
fi

# Get the PIDs of all running processes/threads
PIDS=$(ps -e -o pid=)

# Move all PIDs to the cgroup
for pid in $PIDS; do
    echo $pid > "$CGROUP_PATH/cgroup.procs"
done

echo "max 100000" | sudo tee /sys/fs/cgroup/user/cpu.max

echo "All PIDs except those on the current TTY moved to $CGROUP_PATH."

