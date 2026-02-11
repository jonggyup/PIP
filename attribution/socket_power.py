import subprocess
import time
from decimal import Decimal

toSecond = 1000000  # Corresponding to your `toSecond` variable in shell script
sleepDuration = 1  # Sleep duration between energy readings in seconds

def get_mem_energy_uj(output, zone):
    """Extract memory energy consumption (energy_uj) for the given zone."""
    lines = output.splitlines()
    zone_marker = f"Zone {zone}:0"
    for i, line in enumerate(lines):
        if zone_marker in line:
            return int(lines[i+4].split(":")[1].strip())
    return None

def get_cpu_energy_uj(output, zone):
    """Extract CPU energy consumption (energy_uj) for the given zone."""
    lines = output.splitlines()
    zone_marker = f"Zone {zone}"
    for i, line in enumerate(lines):
        if zone_marker in line:
            return int(lines[i+4].split(":")[1].strip())
    return None

def calculate_power(energy1, energy2):
    """Calculate power based on energy difference and toSecond variable."""
    energy_diff = energy2 - energy1
    power = Decimal(energy_diff) / Decimal(toSecond)
    return round(power, 0)

def cal_all_power():
    """Main function to calculate power for multiple zones."""
    result_array = []

    # Get initial readings
    output = subprocess.run(['sudo', 'powercap-info', '-p', 'intel-rapl'], capture_output=True, text=True).stdout

    for zone in range(2):
        energy1_cpu = get_cpu_energy_uj(output, zone)
        energy1_mem = get_mem_energy_uj(output, zone)

        # Sleep for the defined duration
        time.sleep(sleepDuration)

        # Get the next readings
        output = subprocess.run(['sudo', 'powercap-info', '-p', 'intel-rapl'], capture_output=True, text=True).stdout
        energy2_cpu = get_cpu_energy_uj(output, zone)
        energy2_mem = get_mem_energy_uj(output, zone)

        # Calculate power for CPU and Memory
        power_cpu = calculate_power(energy1_cpu, energy2_cpu)
        power_mem = calculate_power(energy1_mem, energy2_mem)
        result_array[zone] = power_cpu

        # Calculate real CPU power
#        power_realcpu = power_cpu - power_mem

        # Store the results
#        result_array.append((power_realcpu, power_mem))

        # Output results
    print(f"{result_array[0]} | {result_array[1]}")

    return result_array

# Call the main function
cal_all_power()

