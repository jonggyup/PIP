import os
import time
import pyinotify

CGROUP_ROOT = "/sys/fs/cgroup"  # Adjust if needed

class ProcTracker:
    def __init__(self):
        self.procs_map = {}  # path -> set of pids

    def update(self, path):
        try:
            with open(path) as f:
                pids = set(int(pid) for pid in f.read().split())
        except Exception:
            return

        prev = self.procs_map.get(path, set())
        new_pids = pids - prev
        self.procs_map[path] = pids

        for pid in new_pids:
            cmd = self.get_cmdline(pid)
            cgroup_name = os.path.relpath(path, CGROUP_ROOT).replace("/cgroup.procs", "")
            print(f"New PID {pid} ({cmd}) added to cgroup: {cgroup_name}")

    def get_cmdline(self, pid):
        try:
            with open(f"/proc/{pid}/cmdline", 'rb') as f:
                raw = f.read().replace(b'\x00', b' ').decode().strip()
                return raw or "(empty)"
        except Exception:
            return "(exited)"

class CgroupEventHandler(pyinotify.ProcessEvent):
    def __init__(self, tracker):
        self.tracker = tracker

    def process_IN_MODIFY(self, event):
        self.tracker.update(event.pathname)

def find_all_cgroup_procs():
    result = []
    for root, dirs, files in os.walk(CGROUP_ROOT):
        for f in files:
            if f == "cgroup.procs":
                result.append(os.path.join(root, f))
    return result

def main():
    tracker = ProcTracker()
    wm = pyinotify.WatchManager()
    handler = CgroupEventHandler(tracker)
    notifier = pyinotify.Notifier(wm, handler)

    for path in find_all_cgroup_procs():
        tracker.update(path)  # Initialize with current state
        wm.add_watch(path, pyinotify.IN_MODIFY)

    print("Tracking cgroup.procs additions...")
    notifier.loop()

if __name__ == "__main__":
    main()

