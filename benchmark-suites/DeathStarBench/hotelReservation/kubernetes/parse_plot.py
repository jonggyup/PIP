#!/usr/bin/env python3
import os
import re
import statistics
import matplotlib.pyplot as plt
import numpy as np

# ─── Configuration ─────────────────────────────────────────────────────────────
DIR_RE        = re.compile(r"^results-new-(?P<power>\d+)-1+$")
FILE_EXT      = ".dat"
# map wrk percent-string → field name
TARGET_PCTS   = {"90.000": "p90", "99.000": "p99", "99.900": "p99.9"}
# color-blind–friendly palette
SYSTEM_COLORS = {
    'baseline':        '#0072B2',
    'capped-baseline': '#009E73',
    'capped-ours':     '#E69F00',
}
# ────────────────────────────────────────────────────────────────────────────────

def convert_to_ms(val: str) -> float:
    if val.endswith("us"):
        return float(val[:-2]) / 1e3
    if val.endswith("ms"):
        return float(val[:-2])
    if val.endswith("s"):
        return float(val[:-1]) * 1e3
    return float(val)

def parse_dat_file(path: str) -> dict:
    pct_re = re.compile(r"^\s*(\d+\.\d+)%\s+(\S+)")
    out = {}
    with open(path) as f:
        for line in f:
            m = pct_re.match(line)
            if not m: continue
            pct, val = m.groups()
            if pct in TARGET_PCTS:
                out[TARGET_PCTS[pct]] = convert_to_ms(val)
    return out

def collect_records():
    records = []
    for d in os.listdir('.'):
        m = DIR_RE.match(d)
        if not m or not os.path.isdir(d):
            continue
        power = int(m.group("power"))
        for fn in os.listdir(d):
            if not fn.endswith(FILE_EXT):
                continue
            system = fn[:-len(FILE_EXT)]
            metrics = parse_dat_file(os.path.join(d, fn))
            if metrics:
                rec = {"power": power, "system": system}
                rec.update(metrics)
                records.append(rec)
    return records

# ─── Updated: plot per power with truncated annotations ─────────────────────────
def plot_truncated_bar_per_power(records, power):
    metrics = ["p90", "p99", "p99.9"]
    systems = sorted({r["system"] for r in records})
    # aggregate mean per (power, system, metric)
    table = {
        sys: [
            statistics.mean([r[m] for r in records
                              if r["power"] == power and r["system"] == sys and m in r])
            if any(r["power"] == power and r["system"] == sys and m in r for r in records)
            else 0.0
            for m in metrics
        ]
        for sys in systems
    }

    # compute threshold = 1.5 × second-largest value
    all_vals = [v for vals in table.values() for v in vals]
    max_val = max(all_vals) if all_vals else 0.0
    if len(all_vals) > 1:
        sorted_vals = sorted(all_vals, reverse=False)
        thresh = sorted_vals[-3] * 1.5
    else:
        thresh = max_val * 0.1

    # prepare plot
    x = np.arange(len(metrics))
    width = 0.2
    center = width * (len(systems) - 1) / 2
    d = .01  # break mark offset
    fig, ax = plt.subplots(figsize=(6, 4))

    for i, sys in enumerate(systems):
        vals = table[sys]
        clipped = [min(v, thresh) for v in vals]
        positions = x + i * width

        # draw bars
        ax.bar(positions, clipped, width, label=sys,
               color=SYSTEM_COLORS.get(sys))

        # annotate if clipped (i.e. truncated)
        for xpos, h, orig in zip(positions, clipped, vals):
            ax.text(xpos, h,
                    f"{orig:.2f}", ha='center',
                    va='bottom', fontsize=10)

    # labels, grid, legend
    ax.set_xticks(x + center)
    ax.set_xticklabels(metrics)
    ax.set_xlabel("Latency Metric")
    ax.set_ylabel("Latency (ms)")
    ax.set_title(f"Latency by System at {power}W")
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    ax.legend()

    plt.tight_layout()
    plt.savefig(f"/users/jonggyu/push/{power}-single.png")
    plt.show()

# ─── Updated: main loop (per-power) ─────────────────────────────────────────────
def main():
    records = collect_records()
    if not records:
        print("No data found in any results-<power>-<run> folders.")
        return
    powers = sorted({r["power"] for r in records})
    for power in powers:
        plot_truncated_bar_per_power(records, power)

if __name__ == "__main__":
    main()
