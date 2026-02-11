#!/bin/bash

total_cores=$(nproc)
core_range="0-$(($total_cores - 1))"


echo $$ > /sys/fs/cgroup/user/cgroup.procs
echo "max 100000" > /sys/fs/cgroup/user/cpu.max
echo "$core_range" > /sys/fs/cgroup/user/cpuset.cpus

{ time (python /proj/tasrdma-PG0/jonggyu/PowerTrace-noperf/test/tfidvec.py); }
