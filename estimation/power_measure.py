import threading
import time
import subprocess
import os
import glob

def get_ipmi_power(samples):
    """Measure IPMI power and store values in the shared list 'samples'."""
    result = subprocess.run(
        ["ipmitool", "dcmi", "power", "reading"],
        capture_output=True,
        text=True
    )
    for line in result.stdout.splitlines():
        if "Instantaneous" in line:
            ipmi_power = float(line.split()[3])  # Assuming power value is the 4th field
            samples['ipmi'].append(ipmi_power)

def get_rapl_power(samples, max_energy):
    """Measure CPU package power across multiple sockets using RAPL and store values in the shared list 'samples'."""
    package_paths = [path for path in glob.glob("/sys/class/powercap/intel-rapl:*") if path.count(':') == 1]

    previous_energies = [
        int(open(f"{path}/energy_uj").read().strip()) for path in package_paths
    ]

    time.sleep(0.1)  # Sampling interval

    current_energies = [
        int(open(f"{path}/energy_uj").read().strip()) for path in package_paths
    ]
    total_power = 0.0

    # Calculate power for each package and handle counter rollover
    for prev_energy, curr_energy in zip(previous_energies, current_energies):
        if curr_energy < prev_energy:
            curr_energy += max_energy  # Adjust for rollover

        # Calculate power in watts for the current package
        power = (curr_energy - prev_energy) / 1e6 / 0.1  # converting µJ to W for 0.1 sec interval
        total_power += power  # Aggregate power for all packages

    # Store the total aggregated package power
    samples['cpu'].append(total_power)

def get_dram_power(samples, max_dram_energy):
    """Measure DRAM power across multiple sockets using RAPL and store values in the shared list 'samples'."""
    dram_paths = [path for path in glob.glob("/sys/class/powercap/intel-rapl:*:1")]

    previous_energies = [
        int(open(f"{path}/energy_uj").read().strip()) for path in dram_paths
    ]

    time.sleep(0.1)  # Sampling interval

    current_energies = [
        int(open(f"{path}/energy_uj").read().strip()) for path in dram_paths
    ]
    total_power = 0.0

    # Calculate power for each DRAM domain and handle counter rollover
    for prev_energy, curr_energy in zip(previous_energies, current_energies):
        if curr_energy < prev_energy:
            curr_energy += max_dram_energy  # Adjust for rollover

        # Calculate power in watts for the current DRAM domain
        power = (curr_energy - prev_energy) / 1e6 / 0.1  # converting µJ to W for 0.1 sec interval
        total_power += power  # Aggregate power for all DRAM domains

    # Store the total aggregated DRAM power
    samples['dram'].append(total_power)

def main():
    # Read max energy range for rollover detection for CPU and DRAM
    max_energy = int(open("/sys/class/powercap/intel-rapl:0/max_energy_range_uj").read().strip())
    max_dram_energy = max_energy  # Assuming the same max range for DRAM, adjust if needed

    while True:
        start_time = time.time()
        samples = {'ipmi': [], 'cpu': [], 'dram': []}

        while time.time() - start_time < 1.0:  # Collect data for one second
            ipmi_thread = threading.Thread(target=get_ipmi_power, args=(samples,))
            cpu_thread = threading.Thread(target=get_rapl_power, args=(samples, max_energy))
            dram_thread = threading.Thread(target=get_dram_power, args=(samples, max_dram_energy))

            ipmi_thread.start()
            cpu_thread.start()
            dram_thread.start()

            ipmi_thread.join()
            cpu_thread.join()
            dram_thread.join()

        # Calculate the average power readings
        avg_ipmi_power = sum(samples['ipmi']) / len(samples['ipmi']) if samples['ipmi'] else 0
        avg_cpu_power = sum(samples['cpu']) / len(samples['cpu']) if samples['cpu'] else 0
        avg_dram_power = sum(samples['dram']) / len(samples['dram']) if samples['dram'] else 0
        avg_rest_power = avg_ipmi_power - (avg_cpu_power + avg_dram_power)

        # Print the average values for the last one second
#        print(f"IPMI Power: {avg_ipmi_power:.2f} W, CPU Power (RAPL): {avg_cpu_power:.2f} W, DRAM Power: {avg_dram_power:.2f} W, Rest Power: {avg_rest_power:.2f} W", end='\r')

        print(f"IPMI Power: {avg_ipmi_power:.2f} W, CPU Power (RAPL): {avg_cpu_power:.2f} W, DRAM Power: {avg_dram_power:.2f} W, Rest Power: {avg_rest_power:.2f} W", flush=True)

if __name__ == "__main__":
    main()

