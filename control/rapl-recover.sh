#!/bin/bash

# This script restores the power limits to the maximum allowed value for each socket.
# It iterates through all intel-rapl:* directories that have a max_power_range_uw file.
# Usage: sudo ./restore_power.sh
max_power0=$(cat /sys/class/powercap/intel-rapl\:0/constraint_0_max_power_uw)
max_power1=$(cat /sys/class/powercap/intel-rapl\:0/constraint_1_max_power_uw)
echo $max_power0 > /sys/class/powercap/intel-rapl\:0/constraint_0_power_limit_uw
echo $max_power1 > /sys/class/powercap/intel-rapl\:0/constraint_1_power_limit_uw
echo $max_power0 > /sys/class/powercap/intel-rapl\:1/constraint_0_power_limit_uw
echo $max_power1> /sys/class/powercap/intel-rapl\:1/constraint_1_power_limit_uw
