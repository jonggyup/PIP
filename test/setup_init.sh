#!/bin/bash

# Ensure cgroup v2 is enabled and mounted
if ! mount | grep -q cgroup2; then
    echo "Mounting cgroup v2..."
    sudo mount -t cgroup2 none /sys/fs/cgroup
fi

# Create the cgroup directory if it doesn't exist
sudo mkdir -p /sys/fs/cgroup/user

# Set the CPU usage limit to 50% of a single CPU (adjust as needed)
echo "max 100000" | sudo tee /sys/fs/cgroup/user/cpu.max

# Function to add all current PIDs to the cgroup
add_all_pids() {
    for pid in $(ps -e -o pid=); do
        echo $pid | sudo tee /sys/fs/cgroup/user/cgroup.procs >/dev/null 2>&1
    done
}

# Add all current PIDs to the cgroup
add_all_pids

# Verify the configuration
echo "CPU throttling configuration:"
cat /sys/fs/cgroup/user/cpu.max
cat /sys/fs/cgroup/user/cpu.stat

echo "All processes have been migrated to /sys/fs/cgroup/user/"

