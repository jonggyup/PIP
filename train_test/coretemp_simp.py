import subprocess
import time
import sys
from collections import defaultdict

def parse_sensors_output(output):
    temperatures = defaultdict(list)
    socket = None
    for line in output.splitlines():
        if line.startswith("Package"):
            socket = line.split(' ')[2].strip(":")
        elif line.startswith("Core"):
            core_info = line.split(':')
            core_id = int(core_info[0].strip().split(' ')[1]) * 2 + int(socket)
            temp = float(core_info[1].split('°')[0].strip().strip('+'))
            temperatures[core_id].append(temp)
    return temperatures

def get_sensors_output():
    result = subprocess.run(['sensors'], stdout=subprocess.PIPE)
    return result.stdout.decode('utf-8')

def get_core_mapping():
    result = subprocess.run(['lscpu', '-p=cpu,core'], stdout=subprocess.PIPE)
    output = result.stdout.decode('utf-8')
    
    core_mapping = defaultdict(list)
    for line in output.splitlines():
        if line.startswith('#'):
            continue
        logical_core, physical_core = map(int, line.split(','))
        core_mapping[physical_core].append(logical_core)
    
    return core_mapping

def average_temperatures(temp_dict):
    averaged_temps = {}
    for core, temps in temp_dict.items():
        averaged_temps[core] = sum(temps) / len(temps)
    return averaged_temps


def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <duration_in_seconds>")
        sys.exit(1)

    duration = int(sys.argv[1])
    end_time = time.time() + duration
    all_temperatures = defaultdict(list)
    core_mapping = get_core_mapping()

    while time.time() < end_time:
        sensors_output = get_sensors_output()
        current_temperatures = parse_sensors_output(sensors_output)
        for core, temps in current_temperatures.items():
            for logical_core in core_mapping[core]:
                all_temperatures[logical_core].extend(temps)

    averaged_temps = average_temperatures(all_temperatures)

    # Sorting by logical core ID and saving to core_temp.dat file
    with open("core_temp.dat", "w") as f:
        for core in sorted(averaged_temps.keys()):
            f.write(f"{averaged_temps[core]:.2f}\n")

if __name__ == "__main__":
    main()
