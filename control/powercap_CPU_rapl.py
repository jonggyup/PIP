import time

# File containing the overall power budget in watts.
BUDGET_FILE = "./budget"

# RAPL sysfs paths for per-socket power limits (in microwatts).
RAPL_LIMIT_FILES = [
    "/sys/class/powercap/intel-rapl:0/constraint_0_power_limit_uw",
    "/sys/class/powercap/intel-rapl:1/constraint_0_power_limit_uw",
    "/sys/class/powercap/intel-rapl:0/constraint_1_power_limit_uw",
    "/sys/class/powercap/intel-rapl:1/constraint_1_power_limit_uw",

]

# Energy counter files (in microjoules) for each socket.
ENERGY_FILES = [
    "/sys/class/powercap/intel-rapl:0/energy_uj",
    "/sys/class/powercap/intel-rapl:1/energy_uj"
]

def read_budget():
    """Read the total power budget (in watts) from the file."""
    with open(BUDGET_FILE, "r") as f:
        return float(f.read().strip())

def set_limits(total_budget):
    """
    Divide the total budget equally between two sockets,
    convert the per-socket budget (in watts) to microwatts,
    and update the RAPL limit files.
    Returns the per-socket budget in watts.
    """
    per_socket_budget = total_budget / 2
    limit_uw = int(per_socket_budget * 1_000_000)
    for rapl_file in RAPL_LIMIT_FILES:
        try:
            with open(rapl_file, "w") as f:
                f.write(str(limit_uw))
        except Exception as e:
            print(f"Error writing to {rapl_file}: {e}")
    return per_socket_budget

def read_energy(socket_idx):
    """Read the current energy counter (in microjoules) for a given socket."""
    with open(ENERGY_FILES[socket_idx], "r") as f:
        return float(f.read().strip())

def main():
    start_time = time.time()  # Record program start time.
    last_budget = None
    prev_energy = [0.0, 0.0]

    # Initialize previous energy readings for both sockets.
    for i in (0, 1):
        try:
            prev_energy[i] = read_energy(i)
        except Exception as e:
            print(f"Error reading initial energy for socket {i}: {e}")
            prev_energy[i] = 0.0

    while True:
        loop_start = time.time()
        time.sleep(2)  # Wait approximately one second.
        loop_end = time.time()
        elapsed = loop_end - loop_start

        measured = [0.0, 0.0]
        # Calculate measured power (in watts) for each socket.
        for i in (0, 1):
            try:
                curr_energy = read_energy(i)
                delta = curr_energy - prev_energy[i]
                if delta < 0:
                    # Handle possible counter wraparound.
                    delta = curr_energy
                measured[i] = (delta * 1e-6) / elapsed  # Convert microjoules to joules.
                prev_energy[i] = curr_energy
            except Exception as e:
                print(f"Error reading energy for socket {i}: {e}")
                measured[i] = 0.0

        actual_power = measured[0] + measured[1]

        try:
            total_budget = read_budget()
        except Exception as e:
            print("Error reading budget file:", e)
            total_budget = 0.0

        # If the budget changed or measured power exceeds the total budget, update per-socket limits.
        if (last_budget != total_budget) or (actual_power > total_budget):
            per_socket_limit = set_limits(total_budget)
            last_budget = total_budget
        else:
            per_socket_limit = total_budget / 2

        # Elapsed time (in seconds) since the program started.
        timestamp = int(time.time() - start_time)
        # Output format: timestamp | socket0_limit | socket1_limit | total budget | actual power
        print(f"{timestamp} | {per_socket_limit:.2f} | {per_socket_limit:.2f} | {total_budget:.2f} | {actual_power:.2f}", flush=True)

if __name__ == "__main__":
    main()

