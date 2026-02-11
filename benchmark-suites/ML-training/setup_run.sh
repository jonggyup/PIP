#!/bin/bash
total_cores=$(nproc)
core_range="0-$(($total_cores - 1))"


mkdir /sys/fs/cgroup/user
echo $$ > /sys/fs/cgroup/user/cgroup.procs
echo "max 100000" > /sys/fs/cgroup/user/cpu.max
echo "$core_range" > /sys/fs/cgroup/user/cpuset.cpus

arg=$(echo "$1" | tr '[:upper:]' '[:lower:]')

if [ "$arg" == "cpu" ]; then
    python3 /proj/tasrdma-PG0/jonggyu/PowerTrace-noperf2/test/cpu_test.py
elif [ "$arg" == "cache" ]; then
    python3 /proj/tasrdma-PG0/jonggyu/PowerTrace-noperf2/test/cpu_cache_test.py
elif [ "$arg" == "stress" ]; then
    stress-ng -c 64
else
    echo "Invalid argument. Please specify 'CPU' or 'cache'."
fi

