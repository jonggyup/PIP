#!/bin/bash

# Start the containers
#/usr/local/bin/docker-compose up -d

# Move each container into the /sys/fs/cgroup/user cgroup
for container in $(docker ps --format '{{.Names}}'); do
    pid=$(docker inspect --format '{{.State.Pid}}' $container)
    sudo bash -c "echo $pid > /sys/fs/cgroup/user/cgroup.procs"
    echo $pid
done

# Optionally move the current shell (or any other process) into the same cgroup
#sudo bash -c "echo $$ > /sys/fs/cgroup/user/cgroup.procs"

