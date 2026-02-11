#!/usr/bin/env python3
import sys
import socket
import subprocess
import time

if len(sys.argv) != 3:
    print("Usage: python3 send.py <cgroup_name> <server ip>", file=sys.stderr)
    sys.exit(1)

cgroup = sys.argv[1]
serverip = sys.argv[2]
HOST   = "clnode" + serverip + ".clemson.cloudlab.us"
PORT   = 9999

# 1) Connect to the collector (retry up to 3×)
for attempt in range(3):
    try:
        sock = socket.create_connection((HOST, PORT))
        break
    except Exception as exc:
        if attempt == 2:
            print(f"ERROR: cannot connect to {HOST}:{PORT}: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(1)
else:
    sys.exit(1)

# 2) Launch cgroup_monitor.py <cgroup> and capture its stdout
cmd  = ["python3", "cgroup_monitor.py", cgroup]
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

try:
    # 3) Forward each JSON line as-is (plus newline) to the server
    for raw_json in proc.stdout:
        line = raw_json.rstrip("\n")
        if not line:
            continue

        # Skip any “error” objects if you want, or send them as well.
        try:
            sock.sendall((line + "\n").encode("utf-8"))
        except BrokenPipeError:
            break
        except Exception:
            break

finally:
    try:
        proc.stdout.close()
    except:
        pass
    proc.terminate()
    try:
        proc.wait(timeout=1)
    except:
        pass
    try:
        sock.close()
    except:
        pass

