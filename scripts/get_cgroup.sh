#!/bin/bash

# Check if a PID is provided as an argument
if [ -z "$1" ]; then
    echo "Usage: $0 <pid>"
    exit 1
fi

PID=$1

# Check if the specified PID exists
if [ ! -d "/proc/$PID" ]; then
    echo "PID $PID does not exist."
    exit 1
fi

# Get the cgroup information for the specified PID
CGROUP=$(cat /proc/$PID/cgroup)

# Print the cgroup information
echo "Cgroup for PID $PID:"
echo "$CGROUP"

