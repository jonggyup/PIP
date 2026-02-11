####measure per socket power without idle power####
#!/bin/bash
sleepDuration=1
toSecond=1000000

# Function to get CPU energy_uj for a given zone
get_cpu_energy_uj() {
    local zone=$1
    grep -x -A 4 "Zone ${zone}" <<< "$output" | tail -1 | awk '{print $2}'
}

# Function to get max energy range for a given zone (for rollover handling)
get_max_energy_range_uj() {
    local zone=$1
    grep -x -A 2 "Zone ${zone}" <<< "$output" | grep "max_energy_range_uj" | awk '{print $2}'
}

# Function to calculate power and handle rollover case
calculate_power() {
    local energy1=$1
    local energy2=$2
    local max_energy_range=$3

    if [ "$energy2" -ge "$energy1" ]; then
        local energy_diff=$((energy2 - energy1))
    else
        # Handle rollover case
        local energy_diff=$((max_energy_range - energy1 + energy2))
    fi

    echo "scale=2; $energy_diff / $toSecond" | bc
}
get_mem_energy_uj() {
    local zone=$1
    grep -A 4 "Zone ${zone}:0" <<< "$output" | tail -1 | awk '{print $2}'
}


# Main function to calculate power for two zones and print on the same line
cal_all_power() {
    while true; do
        output=$(sudo powercap-info -p intel-rapl)

        # Get initial energy values and max energy range for both zones
        energy1_cpu_zone0=$(get_cpu_energy_uj 0)
        energy1_cpu_zone1=$(get_cpu_energy_uj 1)
        max_energy_range_zone0=$(get_max_energy_range_uj 0)
        max_energy_range_zone1=$(get_max_energy_range_uj 1)
        energy1_mem_zone0=$(get_mem_energy_uj 0)
        energy1_mem_zone1=$(get_mem_energy_uj 1)


        # Sleep for the defined duration
        sleep $sleepDuration

        # Get updated energy values after sleep
        output=$(sudo powercap-info -p intel-rapl)
        energy2_cpu_zone0=$(get_cpu_energy_uj 0)
        energy2_cpu_zone1=$(get_cpu_energy_uj 1)
        energy2_mem_zone0=$(get_mem_energy_uj 0)
        energy2_mem_zone1=$(get_mem_energy_uj 1)


        # Calculate power for both zones, handling rollover if necessary
        power_cpu_zone0=$(calculate_power $energy1_cpu_zone0 $energy2_cpu_zone0 $max_energy_range_zone0)
        power_cpu_zone1=$(calculate_power $energy1_cpu_zone1 $energy2_cpu_zone1 $max_energy_range_zone1)
        power_mem_zone0=$(calculate_power $energy1_mem_zone0 $energy2_mem_zone0 $max_energy_range_zone0)
        power_mem_zone1=$(calculate_power $energy1_mem_zone1 $energy2_mem_zone1 $max_energy_range_zone1)

	power_cpu_zone0=$(echo "$power_cpu_zone0 - 60" | bc)
	power_cpu_zone1=$(echo "$power_cpu_zone1 - 67" | bc)
	total=$(echo "$power_cpu_zone0 + $power_cpu_zone1" | bc)

        # Get the current time in seconds since midnight
        current_time=$(date +'%H %M %S')
        hour=$(echo $current_time | awk '{print $1}')
        minute=$(echo $current_time | awk '{print $2}')
        second=$(echo $current_time | awk '{print $3}')
        wall_clock_seconds=$((10#$hour * 3600 + 10#$minute * 60 + 10#$second))

        # Print the current time, CPU power for both zones, and total power on the same line
        echo "$wall_clock_seconds $power_cpu_zone0 $power_cpu_zone1 $total"

    done
}

# Call the main function
cal_all_power

