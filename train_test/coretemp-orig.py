import subprocess
import time
import re
import sys
from collections import defaultdict

def get_core_mapping():
    core_mapping = {}
    result = subprocess.run(['lscpu', '-p=CPU,CORE,SOCKET'], stdout=subprocess.PIPE, text=True)
    for line in result.stdout.splitlines():
        if line.startswith('#'):
            continue
        cpu, core, socket = map(int, line.split(','))
        core_mapping[(socket, core)] = core_mapping.get((socket, core), []) + [cpu]
    return core_mapping

def parse_sensors_output(output):
    cores_temp = defaultdict(list)
    socket_pattern = re.compile(r'coretemp-isa-([0-9]+)')
    core_pattern = re.compile(r'Core ([0-9]+):\s+\+([0-9.]+)°C')
    
    current_socket = None
    for line in output.splitlines():
        socket_match = socket_pattern.search(line)
        if socket_match:
            current_socket = int(socket_match.group(1))
            continue
        
        if current_socket is not None:
            core_match = core_pattern.search(line)
            if core_match:
                core_id = int(core_match.group(1))
                temp = float(core_match.group(2))
                cores_temp[(current_socket, core_id)].append(temp)
    
    return cores_temp

def duplicate_temps(cores_temp, core_mapping):
    duplicated_temps = defaultdict(list)
    for (socket, core), temps in cores_temp.items():
        if (socket, core) in core_mapping:
            logical_cores = core_mapping[(socket, core)]
            for logical_core in logical_cores:
                duplicated_temps[(socket, logical_core)].extend(temps)
    return duplicated_temps

def average_temperature(cores_temp):
    avg_temp = {}
    for core, temps in cores_temp.items():
        avg_temp[core] = sum(temps) / len(temps)
    return avg_temp

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <duration_in_seconds>")
        sys.exit(1)
    
    duration = int(sys.argv[1])
    end_time = time.time() + duration

    core_mapping = get_core_mapping()
    cores_temp = defaultdict(list)
    
    while time.time() < end_time:
        result = subprocess.run(['sensors'], stdout=subprocess.PIPE, text=True)
        temp_data = parse_sensors_output(result.stdout)
        duplicated_temp_data = duplicate_temps(temp_data, core_mapping)
        for core, temps in duplicated_temp_data.items():
            cores_temp[core].extend(temps)
        time.sleep(1)
    
    avg_temp = average_temperature(cores_temp)
    
    for core, temp in sorted(avg_temp.items()):
        print(f"Socket {core[0]}, Core {core[1]}: Average Temperature = {temp:.2f}°C")

if __name__ == "__main__":
    main()

