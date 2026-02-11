generate_random_budget() {
  # Create an array of possible budget values
  local budgets=(150 180 210 240 270 300)

  # Use awk to generate a pseudorandom number based on a seed
  local seed=$1
  local index=$(awk -v seed=$seed 'BEGIN { srand(seed); print int(rand() * 6) }')

  # Output the randomly selected budget
  echo ${budgets[$index]}
}

# Set a fixed seed for reproducibility
seed=12345

previous_budget=-1
echo 300 > ./budget
sleep 60
# Main loop
while true; do
  # Generate a new budget using the seed
  current_budget=$(generate_random_budget $seed)

  # Ensure the new budget differs by at least 30 from the previous one
  if [ $previous_budget -ne -1 ]; then
    diff=$(( current_budget - previous_budget ))
    diff=${diff#-}  # Absolute value of the difference
    if [ $diff -lt 30 ]; then
      seed=$((seed + 1))  # Increment the seed to generate a new random budget
      continue  # Skip the rest of the loop and regenerate
    fi
  fi

  # Output the current budget
  echo $current_budget > ./budget

  # Update previous_budget and increment seed for the next iteration
  previous_budget=$current_budget
  seed=$((seed + 1))

  # Sleep for 1 second (or 60 seconds if you prefer)
  sleep 60
done
