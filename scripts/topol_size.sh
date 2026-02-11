#!/bin/bash

# Run cpupower monitor and store the output
output=$(cpupower monitor ls)

# Initialize variables
c0_index=""
tmp_data=()

# Split the output into lines and process each line
IFS=$'\n' read -rd '' -a lines <<< "$output"

for line in "${lines[@]}"; do
    # Split the line by "|"
    elements=($(echo "$line" | tr '|' '\n'))

    # Clean up the elements by trimming whitespace
    elements=("${elements[@]// /}")

    # Find the index of 'C0' in the line that contains 'CPU'
    if [[ "${elements[*]}" == *"CPU"* && -z "$c0_index" ]]; then
        for i in "${!elements[@]}"; do
            if [[ "${elements[$i]}" == "C0" ]]; then
                c0_index=$i
                break
            fi
        done
        continue  # Skip this header line
    fi

    # Start collecting data from the next line after 'CPU'
    if [[ -n "$c0_index" && "${elements[@]}" != *"CPU"* && ${#elements[@]} -gt 0 ]]; then
        # Extract the C0 data for all CPU entries
        if [[ ${#elements[@]} -gt $c0_index ]]; then
            for (( i=$c0_index; i<${#elements[@]}; i++ )); do
                if [[ -n "${elements[$i]}" ]]; then
                    tmp_data+=("${elements[$i]}")
                fi
            done
        fi
    fi
done

# Calculate the number of entries that meet the condition
# (e.g., non-empty and numeric entries)
count=0
for entry in "${tmp_data[@]}"; do
    if [[ $entry =~ ^[0-9]+([.][0-9]+)?$ ]]; then
        count=$((count + 1))
    fi
done

python3 coretemp_simp.py 1
num_cores_temp=$(cat core_temp.dat | wc -l)
# Calculate the number of CPU cores
#cpu_cores=$(lscpu | grep "^CPU(s):" | awk '{print $2}')

# Calculate the sum of count and cpu_cores
total=$((count + num_cores_temp))
max_freq=$(($(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq) / 1000))


# Save the result to ./file.dat
echo "$count $total $max_freq" > ./topol_metric_size.dat
