#!/bin/bash

total_cores=$(nproc)
core_range="0-$(($total_cores - 1))"


echo $$ > /sys/fs/cgroup/user/cgroup.procs
echo "max 100000" > /sys/fs/cgroup/user/cpu.max
echo "$core_range" > /sys/fs/cgroup/user/cpuset.cpus

{ time (sysbench cpu --cpu-max-prime=20000000 --threads=40 run >/dev/null 2>&1); } 
