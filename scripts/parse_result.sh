#!/bin/bash

# Function to calculate average and standard deviation
calculate_stats() {
    local data=("$@")
    local sum=0
    local sumsq=0
    local count=${#data[@]}

    # Calculate sum and sum of squares
    for value in "${data[@]}"; do
        sum=$(echo "$sum + $value" | bc)
        sumsq=$(echo "$sumsq + ($value * $value)" | bc)
    done

    # Calculate average
    local avg=$(echo "$sum / $count" | bc -l)

    # Calculate variance
    local variance=$(echo "($sumsq - ($sum * $sum / $count)) / $count" | bc -l)

    # Calculate standard deviation
    local stddev=$(echo "sqrt($variance)" | bc -l)

    echo "$avg $stddev"
}

# Process each file in the directory
for file in ../results/*; do
    filename=$(basename "$file")  # Extract just the file name
    errors=()
    truths=()

    # Read each line in the file
    while IFS= read -r line; do
        # Extract the Error-A and Truth values using regex
        error=$(echo "$line" | grep -oP "Error-A\(%\): \K[0-9.]+")
        truth=$(echo "$line" | grep -oP "Truth: \K[0-9.]+")
        
        if [[ -n $error && -n $truth ]]; then
            errors+=("$error")
            truths+=("$truth")
        fi
    done < "$file"

    # Calculate stats for errors
    if [[ ${#errors[@]} -gt 0 ]]; then
        read avg_error stddev_error <<< $(calculate_stats "${errors[@]}")
    fi

    # Calculate average for truth
    if [[ ${#truths[@]} -gt 0 ]]; then
        sum_truth=0
        for truth in "${truths[@]}"; do
            sum_truth=$(echo "$sum_truth + $truth" | bc)
        done
        avg_truth=$(echo "$sum_truth / ${#truths[@]}" | bc -l)
    fi

    # Print results in a single line with 2 decimal precision
    printf "%s %.2f %.2f %.2f\n" "$filename" "$avg_truth" "$avg_error" "$stddev_error"
done

