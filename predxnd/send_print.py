#!/usr/bin/env python3
import sys
import socket
import subprocess
import time
import json
import glob
import os

if len(sys.argv) != 3:
    print("Usage: python3 send.py <cgroup_name> <server ip>", file=sys.stderr)
    sys.exit(1)

cgroup = sys.argv[1]
serverip = sys.argv[2]
HOST = "clnode" + serverip + ".clemson.cloudlab.us"
PORT = 9999

def get_package_rapl_paths():
    paths = []
    for base in sorted(glob.glob("/sys/class/powercap/intel-rapl:*")):
        try:
            name_file = os.path.join(base, "name")
            with open(name_file) as f:
                if f.read().strip().startswith("package-"):
                    paths.append(os.path.join(base, "energy_uj"))
        except:
            continue
    return paths

def read_energy(paths):
    return [int(open(p).read()) for p in paths]

def measure_total_power(paths, interval=0.5):
    e1 = read_energy(paths)
    time.sleep(interval)
    e2 = read_energy(paths)
    return sum((e2[i] - e1[i]) / 1e6 / interval for i in range(len(paths)))

# Connect
for attempt in range(3):
    try:
        sock = socket.create_connection((HOST, PORT))
        break
    except Exception as exc:
        if attempt == 2:
            print(f"ERROR: cannot connect to {HOST}:{PORT}: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(1)

sock_file = sock.makefile("r")
rapl_paths = get_package_rapl_paths()

cmd = ["python3", "cgroup_monitor3.py", cgroup]
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

try:
    for raw_json in proc.stdout:
        line = raw_json.strip()
        if not line:
            continue

        try:
            sock.sendall((line + "\n").encode("utf-8"))
        except:
            break

        try:
            response_line = sock_file.readline()
            response = json.loads(response_line)
            est_power = response.get("estimated_power", None)

            if est_power is not None:
                local_power = measure_total_power(rapl_paths)
                abs_error = abs(est_power - local_power) / local_power * 100
                print(f"Local: {local_power:.2f}W | Estimated: {est_power:.2f}W | Error: {abs_error:.2f}%", flush=True)
        except:
            continue

finally:
    try: proc.stdout.close()
    except: pass
    proc.terminate()
    try: proc.wait(timeout=1)
    except: pass
    try: sock.close()
    except: pass

