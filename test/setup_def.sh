#!/bin/bash
total_cores=$(nproc)
core_range="0-$(($total_cores - 1))"

# Check if the directory exists before creating it
if [ ! -d /sys/fs/cgroup/user ]; then
    sudo mkdir /sys/fs/cgroup/user
fi

echo $$
# Adding current process to the cgroup
echo $$ > /sys/fs/cgroup/user/cgroup.procs

# Set the cpu.max and cpuset.cpus values
echo "max 100000" | sudo tee /sys/fs/cgroup/user/cpu.max
echo "$core_range" | sudo tee /sys/fs/cgroup/user/cpuset.cpus

