import time
import subprocess

# Define cgroup paths
cgroup_user1 = "/sys/fs/cgroup/user1/cgroup.procs"
cgroup_user2 = "/sys/fs/cgroup/user2/cgroup.procs"

# Docker run command
docker_cmd = [
    "./scaphandre/target/debug/scaphandre", "stdout", "-p", "100", "-s", "1", "-t", "2"
]

# Function to get the list of PIDs from a cgroup
def get_pids(cgroup_path):
    try:
        with open(cgroup_path, 'r') as file:
            pids = file.read().strip().split()
        return pids
    except FileNotFoundError:
        return []

# Function to get the power consumption for a given PID from scaphandre output
def get_power_for_pid(scaphandre_output, pid):
    for line in scaphandre_output.splitlines():
        parts = line.strip().split()
        if len(parts) > 2 and parts[2] == pid:
            try:
                return float(parts[0])  # Power value is the first field
            except (IndexError, ValueError):
                continue
    return 0.0

# Function to get the total power for a cgroup
def get_total_power(cgroup_pids, scaphandre_output):
    total_power = 0.0
    for pid in cgroup_pids:
        total_power += get_power_for_pid(scaphandre_output, pid)
    return total_power

# Function to get the current wall clock time in total seconds (hours + minutes + seconds)
def get_wall_clock_time_in_seconds():
    current_time = time.localtime()
    total_seconds = current_time.tm_hour * 3600 + current_time.tm_min * 60 + current_time.tm_sec
    return total_seconds

# Main loop to run docker command and aggregate power
while True:
    # Run the docker command and capture the output
    result = subprocess.run(docker_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    scaphandre_output = result.stdout

    # Get PIDs from user1 and user2 cgroups
    user1_pids = get_pids(cgroup_user1)
    user2_pids = get_pids(cgroup_user2)

    # Get total power for user1 and user2
    user1_power = get_total_power(user1_pids, scaphandre_output)
    user2_power = get_total_power(user2_pids, scaphandre_output)

    # Get the current wall clock time in total seconds
    wall_clock_seconds = get_wall_clock_time_in_seconds()

    # Print the wall clock time and the aggregated power values on the same line
    print(f"{wall_clock_seconds} {user1_power:.2f} {user2_power:.2f}", flush=True)

