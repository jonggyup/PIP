#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integrated version: parses raw .dat files for best-effort workloads,
computes PIP/Thunderbolt ratios, and generates per-workload plots.

Expected filename format:
  <workload>-os<OSR>-f<FLUC>-(google|powertrace)[-result[s]].dat
Examples:
  cnn-os30-f25-google.dat
  cnn-os30-f25-powertrace-result.dat
  bert-os50-f0-powertrace.dat

Only best-effort workloads are considered: cnn, bert, tfidfvec
  - All use training-time metrics (lower is better -> perf = 1/time)

Outputs:
  <results_dir>/be_ratio.csv        - ratio data
  plots/figure4_<workload>.png      - one plot per workload
"""

import sys, os, re, glob, csv
from collections import defaultdict, namedtuple
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BE_WORKLOADS = {"cnn", "bert", "tfidfvec"}

FNAME_RE = re.compile(
    r'^([A-Za-z0-9]+)-os(\d+)-f(\d+)-(google|powertrace)-result\.dat$',
    re.IGNORECASE,
)

Record = namedtuple("Record", "workload os fluc method value")

# ---------------------------------------------------------------------------
# Parsers (all BE workloads are time-based)
# ---------------------------------------------------------------------------

def parse_training_time(txt: str) -> float:
    m = re.findall(r"Training\s+Time:\s*([\d.]+)\s*seconds", txt, flags=re.IGNORECASE)
    if not m:
        raise ValueError("training time not found")
    return float(m[-1])


def parse_cnn_training_time(txt: str) -> float:
    m = re.findall(r"Training\s+completed\s*in\s*([\d.]+)\s*seconds", txt, flags=re.IGNORECASE)
    if m:
        return float(m[-1])
    return parse_training_time(txt)


WORKLOAD_PARSERS = {
    "tfidfvec": parse_training_time,
    "bert":     parse_training_time,
    "cnn":      parse_cnn_training_time,
}

# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_filename(basename: str):
    m = FNAME_RE.match(basename)
    if not m:
        return None
    wl, osr, fluc, method = m.groups()
    wl = wl.lower()
    if wl not in BE_WORKLOADS:
        return None
    return wl, int(osr), int(fluc), method.lower()


def parse_metric(path: str, workload: str) -> float:
    parser = WORKLOAD_PARSERS[workload]
    with open(path, "r", errors="ignore") as f:
        txt = f.read()
    v = parser(txt)
    if v <= 0:
        raise ValueError("non-positive metric")
    return v


# ---------------------------------------------------------------------------
# Core: parse directory -> ratio rows
# ---------------------------------------------------------------------------

def parse_and_compute_ratios(results_dir: str) -> List[dict]:
    files = glob.glob(os.path.join(results_dir, "*.dat"))
    if not files:
        print(f"No .dat files in {results_dir}", file=sys.stderr)
        return []

    # (wl, os, fluc, method) -> list of metric values
    recs: Dict[Tuple, List[float]] = defaultdict(list)
    skipped = 0

    for path in sorted(files):
        b = os.path.basename(path)
        parsed = parse_filename(b)
        if not parsed:
            skipped += 1
            continue
        wl, osr, fluc, method = parsed
        try:
            v = parse_metric(path, wl)
            recs[(wl, osr, fluc, method)].append(v)
        except Exception as e:
            print(f"  [skip] cannot parse {b}: {e}", file=sys.stderr)
            skipped += 1

    if not recs:
        print("No parseable BE results found.", file=sys.stderr)
        return []

    print(f"Parsed {sum(len(v) for v in recs.values())} files, skipped {skipped}")

    # Aggregate: mean time -> perf = 1 / mean_time
    perf: Dict[Tuple, float] = {}
    for (wl, osr, fluc, method), vals in recs.items():
        mean_time = sum(vals) / len(vals)
        perf[(wl, osr, fluc, method)] = 1.0 / mean_time

    # Group by (wl, os, fluc) and compute ratio = perf(powertrace) / perf(google)
    grouped: Dict[Tuple, Dict[str, float]] = defaultdict(dict)
    for (wl, osr, fluc, method), p in perf.items():
        grouped[(wl, osr, fluc)][method] = p

    rows = []
    for (wl, osr, fluc), methods in sorted(grouped.items()):
        if "powertrace" in methods and "google" in methods and methods["google"] > 0:
            ratio = methods["powertrace"] / methods["google"]
            rows.append({
                "workload": wl,
                "os": osr,
                "fluc": fluc,
                "ratio": f"{ratio:.8f}",
            })
        else:
            missing = [m for m in ("powertrace", "google") if m not in methods]
            print(f"  [warn] {wl} os={osr} fluc={fluc}: missing {', '.join(missing)}",
                  file=sys.stderr)

    return rows


def write_ratio_csv(rows: List[dict], path: str):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["workload", "os", "fluc", "ratio"])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {path} ({len(rows)} rows)")


def read_ratio_csv(path: str):
    data = []
    with open(path, "r", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                data.append((
                    row["workload"].lower(),
                    int(row["os"]),
                    int(row["fluc"]),
                    float(row["ratio"]),
                ))
            except Exception:
                continue
    return data


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot_all(rows, root):
    import numpy as np
    import matplotlib
    import matplotlib.pyplot as plt

    matplotlib.rcParams.update({
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.linewidth": 1.3,
        "xtick.major.width": 1.2,
        "ytick.major.width": 1.2,
        "xtick.major.size": 4,
        "ytick.major.size": 4,
    })

    # Group: wl -> { fluc -> [(os, ratio)] }
    by_wl: Dict[str, Dict[int, List[Tuple[int, float]]]] = defaultdict(lambda: defaultdict(list))
    os_all: Dict[str, set] = defaultdict(set)
    for wl, osr, fluc, ratio in rows:
        by_wl[wl][fluc].append((osr, ratio))
        os_all[wl].add(osr)

    out_dir = os.path.join(root, "plots")
    os.makedirs(out_dir, exist_ok=True)

    for wl, fluc_map in by_wl.items():
        osr_list = sorted(os_all[wl])
        if not osr_list:
            continue

        fig_w, fig_h = 4.6, 1.7
        fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h), dpi=450)

        for fluc, pairs in sorted(fluc_map.items()):
            pairs_sorted = sorted(pairs, key=lambda x: x[0])
            val_by_os = {o: v for o, v in pairs_sorted}
            y = np.array([val_by_os.get(o, np.nan) for o in osr_list], dtype=float)

            ax.plot(
                osr_list, y,
                marker="o",
                linewidth=2.0,
                markersize=5.8,
                label=f"fluc={fluc}",
                clip_on=True,
            )

        ax.axhline(1.00, color="black", linestyle="--", linewidth=1.0, label="_nolegend_")
        ax.axhline(1.05, color="#666666", linestyle=":", linewidth=1.0, label="_nolegend_")

        ax.set_xlabel("OSR (%)", fontsize=11)
        ax.set_ylabel("PIP / Thunderbolt (x)", fontsize=11, labelpad=2.0)

        ax.set_xticks(osr_list)
        ax.set_xticklabels([str(t) for t in osr_list], fontsize=10)
        ax.tick_params(axis="y", which="major", labelsize=10, pad=2.0)

        ax.set_title(wl, fontsize=12, pad=4.0)

        ax.legend(
            fontsize=9.5, ncol=1, frameon=False, loc="best",
            handlelength=2.0, borderaxespad=0.3,
        )

        for spine in ("top", "right", "bottom", "left"):
            ax.spines[spine].set_visible(True)

        ax.margins(x=0.01)

        finite_vals = [v for pairs in fluc_map.values() for _, v in pairs if not np.isnan(v)]
        if finite_vals:
            ymin = min(0.88, min(finite_vals) - 0.05)
            ymax = max(2, max(finite_vals) + 1)
            ax.set_ylim(ymin, ymax)

        fig.tight_layout(pad=0.25)
        base = os.path.join(out_dir, f"figure4_{wl}")
        fig.savefig(base + ".png", bbox_inches="tight")
        plt.close(fig)
        print(f"Wrote {base}.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    results_dir = os.path.join(root, "results-oversub-fluc")
    ratio_csv = os.path.join(results_dir, "be_ratio.csv")

    # Always regenerate from raw .dat files if the directory exists
    if os.path.isdir(results_dir):
        ratio_rows = parse_and_compute_ratios(results_dir)
        if ratio_rows:
            write_ratio_csv(ratio_rows, ratio_csv)
        elif os.path.exists(ratio_csv):
            print("No new data parsed; falling back to existing be_ratio.csv",
                  file=sys.stderr)
        else:
            print("No data found and no existing be_ratio.csv.", file=sys.stderr)
            sys.exit(1)
    elif not os.path.exists(ratio_csv):
        print(f"Neither {results_dir}/ nor {ratio_csv} found.", file=sys.stderr)
        sys.exit(1)

    rows = read_ratio_csv(ratio_csv)
    if not rows:
        print(f"No data in '{ratio_csv}'.", file=sys.stderr)
        sys.exit(2)

    plot_all(rows, root)


if __name__ == "__main__":
    main()
