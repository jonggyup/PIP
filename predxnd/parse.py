import os
import re
import numpy as np

def parse_file(path):
    locals_, ests_ = [], []
    with open(path) as f:
        for line in f:
            m = re.match(r"Local: ([\d\.]+)W \| Estimated: ([\d\.]+)W", line)
            if m:
                locals_.append(float(m.group(1)))
                ests_.append(float(m.group(2)))
    return np.array(locals_), np.array(ests_)

def get_dir_suffixes(base='.'):
    dirs = [d for d in os.listdir(base) if d.startswith("results-wbg-") and os.path.isdir(d)]
    suffixes = []
    for d in dirs:
        m = re.match(r"results-wbg-(\d+)-(\d+)", d)
        if m:
            suffixes.append((int(m.group(1)), int(m.group(2))))
    return suffixes

def get_workloads(dirpath):
    return [f for f in os.listdir(dirpath) if f.endswith(".dat")]

def analyze(base='.'):
    print("local,remote,workload,mean_error,std_error,num_samples")
    dir_suffixes = get_dir_suffixes(base)
    for local, remote in sorted(dir_suffixes):
        dname = f"results-wbg-{local}-{remote}"
        workloads = get_workloads(dname)
        for wl in workloads:
            wlname = wl.replace('.dat', '')
            if local == remote:
                l, e = parse_file(os.path.join(dname, wl))
                if len(l) == 0:
                    print(f"{local},{remote},{wlname},NaN,NaN,0")
                    continue
                errors = np.abs((l - e) / l) * 100
                if len(errors) > 5:
                    errors = np.sort(errors)[:-5]
                print(f"{local},{remote},{wlname},{errors.mean():.2f},{errors.std():.2f},{len(errors)}")
            else:
                # Choose files based on direction
                if remote > local:
                    local_path = f"results-wbg-{local}-{local}/{wl}"
                    est_path = f"results-wbg-{local}-{remote}/{wl}"
                else:
                    local_path = f"results-wbg-{remote}-{remote}/{wl}"
                    est_path = f"results-wbg-{remote}-{local}/{wl}"
                if not (os.path.exists(local_path) and os.path.exists(est_path)):
                    print(f"{local},{remote},{wlname},NaN,NaN,0")
                    continue
                l, _ = parse_file(local_path)
                _, e = parse_file(est_path)
                n = min(len(l), len(e))
                if n == 0:
                    print(f"{local},{remote},{wlname},NaN,NaN,0")
                    continue
                errors = np.abs((l[:n] - e[:n]) / l[:n]) * 100
                if len(errors) > 5:
                    errors = np.sort(errors)[:-5]
                print(f"{local},{remote},{wlname},{errors.mean():.2f},{errors.std():.2f},{len(errors)}")

if __name__ == '__main__':
    analyze('.')

