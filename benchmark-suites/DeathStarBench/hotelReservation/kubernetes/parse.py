#!/usr/bin/env python3
import os, re, statistics, sys

# ─── Config ────────────────────────────────────────────────────────────────────
DIR_RE     = re.compile(r"^results-new-(?P<power>\d+)-1+$")
FILE_EXT   = ".dat"
TARGET_PCTS = {"90.000", "99.000", "99.900"}
# ────────────────────────────────────────────────────────────────────────────────

def parse_latencies(path):
    pct_re = re.compile(r"^\s*(?P<pct>\d+\.\d+)%\s+(?P<val>\S+)")
    out = {}
    with open(path) as f:
        for line in f:
            m = pct_re.match(line)
            if not m: continue
            pct = m.group("pct")
            if pct in TARGET_PCTS:
                v = m.group("val")
                if v.endswith("us"):
                    sec = float(v[:-2]) / 1e3
                elif v.endswith("ms"):
                    sec = float(v[:-2])
                elif v.endswith("s"):
                    sec = float(v[:-1]) * 1e3
                else:
                    sec = float(v)
                out[pct] = sec
    return out

def main():
    data = {}  # (power, system, pct) -> [values]
    for d in os.listdir('.'):
        m = DIR_RE.match(d)
        if not m or not os.path.isdir(d):
            continue
        power = int(m.group("power"))
        for fn in os.listdir(d):
            if not fn.endswith(FILE_EXT):
                continue
            system = fn[:-len(FILE_EXT)]
            results = parse_latencies(os.path.join(d, fn))
            for pct, sec in results.items():
                data.setdefault((power, system, pct), []).append(sec)

    # header
    print("power,system,p90,p99,p99.9")
    powers = sorted({p for (p,_,_) in data})
    systems = sorted({s for (_,s,_) in data})
    for p in powers:
        for s in systems:
            key90  = (p, s, "90.000")
            key99  = (p, s, "99.000")
            key999 = (p, s, "99.900")
            if key90 not in data:
                continue
            avg90  = statistics.mean(data[key90])
            avg99  = statistics.mean(data[key99])  if key99  in data else 0
            avg999 = statistics.mean(data[key999]) if key999 in data else 0
            print(f"{p},{s},{avg90:.2f},{avg99:.2f},{avg999:.2f}")

if __name__ == "__main__":
    main()


