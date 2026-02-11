#!/bin/bash

# Get the number of available CPU cores
num_cores=$(nproc)

# Loop through each core and set the governor to performance
for ((i=0; i<num_cores; i++))
do
    echo "performance" | sudo tee /sys/devices/system/cpu/cpu$i/cpufreq/scaling_governor
done

echo "All CPU cores have been set to performance governor."

