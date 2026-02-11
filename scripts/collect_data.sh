#!/bin/bash
CGROUP_ROOT="/sys/fs/cgroup"
USER_CGROUP="$CGROUP_ROOT/user"
CRITICAL_CGROUP="$CGROUP_ROOT/critical"

(cd ../train_test/ && python3 feature_extract.py 1 ) &

mkdir -p ../data
./stressor.sh
sleep 10
./cgroup_init.sh
stress-ng -c 64 &
echo $! > "$USER_CGROUP/cgroup.procs"
python3 ./cgroup_possible_runs.py

#./run-realworld-bench.sh

pkill -ef stress-ng
./cgroup_init.sh
./ctl_test.sh
pkill -ef feature_extract
./cgroup_init.sh
