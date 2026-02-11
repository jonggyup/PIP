#!/bin/bash

CGROUP="/sys/fs/cgroup/$1"
if [ ! -d "$CGROUP" ]; then
	echo "Cgroup $CGROUP does not exist."
	exit 1
fi

for container in $(docker ps --format '{{.Names}}'); do
	pid=$(docker inspect --format '{{.State.Pid}}' "$container")
	if [ -n "$pid" ] && [ -d /proc/$pid ]; then
		echo $pid | sudo tee "$CGROUP/cgroup.procs" > /dev/null
		for child in $(pgrep -P "$pid"); do
			echo $child | sudo tee "$CGROUP/cgroup.procs" > /dev/null
		done
	fi
done

# Move docker daemons to 'user' cgroup
for pname in dockerd containerd containerd-shim docker-proxy; do
	for pid in $(pgrep -x "$pname"); do
		echo $pid | sudo tee $CGROUP/cgroup.procs > /dev/null
	done
done

echo $$ | sudo tee $CGROUP/cgroup.procs
