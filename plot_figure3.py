#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stacked heatmaps across fluctuation levels (rows), with two columns:
  Left  = PIP        (reds)
  Right = Thunderbolt (blues)

Requirements satisfied:
  • One shared horizontal colorbar per method (two total), placed ABOVE each column.
  • Y-axis uses A/B/C/D (mapping printed to stdout; denote in caption).
  • Safe-cell outline at >= 0.90.
  • Cell annotations use .1f.
  • Row labels: “Fluctuation: X%”.
  • Compact width, larger fonts, constrained layout.

Accepted file patterns:
  workload-os<OSR>-p<P>[-fluc<FLUC>]-(google|powertrace)-result(s).dat
  workload-baseline[-fluc<FLUC>]-result(s).dat   # <<< supports fluc-specific baselines

Outputs:
  - plots/heatmap_normalized_all_workloads_fluc_stack.png

Usage:
  python3 plot_heatmap_fluc_stack.py [dir_with_dat_files]
"""
import sys, re, os, glob
from collections import namedtuple
from typing import Dict, Tuple, List

# ---------- Workload configuration ----------
WORKLOAD_SPECS = {
    "fileserver": ("throughput", "parse_fileserver_mb_s"),
    "tfidfvec"  : ("time",       "parse_training_time"),
    "bert"      : ("time",       "parse_training_time"),
    "cnn"       : ("time",       "parse_cnn_training_time"),
    "cnninf"    : ("throughput", "parse_cnninf_ips"),
    "hotel"     : ("throughput", "parse_wrk_requests_per_sec"),
    "social"    : ("throughput", "parse_wrk_requests_per_sec"),
}
# Show order → letters A,B,C,D
SHOW_WORKLOADS = ["fileserver", "cnninf", "hotel", "social"]

RE_RESULT_ENDING = re.compile(r"-result(s)?\.dat$", re.IGNORECASE)
LABEL_MAP = {"powertrace": "PIP", "google": "Thunderbolt", "baseline": "Baseline"}
def method_label(m: str) -> str:
    return LABEL_MAP.get(m, m)

# ---------- Parsers ----------
def parse_fileserver_mb_s(text: str) -> float:
    m = re.findall(r"IO Summary:.*?(\d+(?:\.\d+)?)\s*mb/s", text, flags=re.IGNORECASE|re.DOTALL)
    if not m: raise ValueError("fileserver: MB/s not found in IO Summary")
    return float(m[-1])

def parse_training_time(text: str) -> float:
    m = re.findall(r"Training\s+Time:\s*([\d.]+)\s*seconds", text, flags=re.IGNORECASE)
    if not m: raise ValueError("training time not found")
    return float(m[-1])

def parse_cnn_training_time(text: str) -> float:
    m = re.findall(r"Training\s+completed\s*in\s*([\d.]+)\s*seconds", text, flags=re.IGNORECASE)
    if m: return float(m[-1])
    return parse_training_time(text)

def parse_wrk_requests_per_sec(text: str) -> float:
    m = re.findall(r"avg_goodput_rps:\s*([\d.]+)", text, flags=re.IGNORECASE)
    if not m: raise ValueError("wrk Requests/sec not found")
    return float(m[-1])

def parse_cnninf_ips(text: str) -> float:
    m = re.findall(r"Average\s+inferences/sec:\s*([\d.]+)", text, flags=re.IGNORECASE)
    if not m: raise ValueError("cnninf IPS not found")
    return float(m[-1])

PARSERS = {
    "parse_fileserver_mb_s": parse_fileserver_mb_s,
    "parse_training_time": parse_training_time,
    "parse_cnn_training_time": parse_cnn_training_time,
    "parse_wrk_requests_per_sec": parse_wrk_requests_per_sec,
    "parse_cnninf_ips": parse_cnninf_ips,
}

# ---------- Core ----------
Record = namedtuple("Record", "workload os p fluc method metric_type value path")

def parse_filename(path: str):
    """
    Accepts:
      workload-os<OSR>-f<FLUC>-(google|powertrace)-result(s).dat
      workload-baseline[-fluc<FLUC>]-result(s).dat
    Returns (workload, method, os, p, fluc), where p is now always 0.
    """
    b = os.path.basename(path)
    m = re.match(
        r"^([A-Za-z0-9]+)-os(\d+)-f(\d+)-(google|powertrace)-result(s)?\.dat$",
        b, re.IGNORECASE,
    )
    if m:
        wl, os_val, fluc, method, _ = m.groups()
        return wl.lower(), method.lower(), int(os_val), 0, int(fluc)

    # fluc-specific baseline
    m = re.match(r"^([A-Za-z0-9]+)-baseline(?:-fluc(\d+))?-result(s)?\.dat$", b, re.IGNORECASE)
    if m:
        wl, fluc, _ = m.groups()
        return wl.lower(), "baseline", 0, 0, (int(fluc) if fluc else 0)

    raise ValueError(f"Filename does not match known patterns: {b}")

def parse_metric_for_file(path: str, workload: str) -> float:
    metric_type, parser_name = WORKLOAD_SPECS[workload]
    parser = PARSERS[parser_name]
    with open(path, "r", errors="ignore") as f:
        txt = f.read()
    return parser(txt)

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    dat_files = [p for p in glob.glob(os.path.join(root, "results-oversub-fluc", "*.dat")) if RE_RESULT_ENDING.search(p)]
    if not dat_files:
        sys.exit("No *-result(s).dat files found.")

    # Baselines indexed by (workload, fluc). Keep legacy baseline under fluc=None.  # <<< changed
    baselines: Dict[Tuple[str, int], Record] = {}
    legacy_baseline: Dict[str, Record] = {}

    method_records: List[Record] = []

    for path in sorted(dat_files):
        try:
            wl, method, osv, pv, fluc = parse_filename(path)
            if wl not in WORKLOAD_SPECS:
                print(f"[skip] Unknown workload '{wl}' in {os.path.basename(path)}", file=sys.stderr)
                continue
            metric_type, _ = WORKLOAD_SPECS[wl]
            val = parse_metric_for_file(path, wl)
            rec = Record(wl, osv, pv, fluc, method, metric_type, val, path)
            if method == "baseline":
                if fluc is not None and fluc != 0:
                    baselines[(wl, fluc)] = rec
                else:
                    # store both as fluc=0 baseline and legacy fallback           # <<< changed
                    baselines[(wl, 0)] = rec
                    legacy_baseline[wl] = rec
            else:
                method_records.append(rec)
        except Exception as e:
            print(f"[warn] Failed {os.path.basename(path)}: {e}", file=sys.stderr)

    if not method_records or (not baselines and not legacy_baseline):
        sys.exit("Missing method or baseline results.")

    # ---------- Normalize vs matching (workload, fluc) baseline ----------      # <<< changed
    out_rows = []
    for r in method_records:
        # Prefer exact (wl, fluc), then (wl, 0), then legacy (wl).
        b = baselines.get((r.workload, r.fluc)) \
            or baselines.get((r.workload, 0)) \
            or legacy_baseline.get(r.workload)
        if not b:
            print(f"[warn] No baseline for {r.workload} fluc={r.fluc}; skipping.", file=sys.stderr)
            continue

        if r.metric_type == "throughput":
            if b.value <= 0:
                print(f"[warn] Invalid baseline value for {r.workload} fluc={r.fluc}", file=sys.stderr);
                continue
            norm = r.value / b.value
        else:
            if r.value <= 0:
                print(f"[warn] Invalid method value for {r.workload} fluc={r.fluc}", file=sys.stderr);
                continue
            norm = b.value / r.value

        norm = min(1.0, norm)
        out_rows.append({
            "workload": r.workload,
            "os": r.os,
            "fluc": r.fluc,
            "method": r.method,     # 'google' or 'powertrace'
            "normalized": norm,
        })

    if not out_rows:
        sys.exit("No normalized rows could be generated.")

    # ---- Aggregate for matrices per (fluc, method) ----
    import numpy as np
    try:
        import matplotlib
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"[warn] Plotting libs unavailable: {e}", file=sys.stderr)
        return

    matplotlib.rcParams.update({
        "font.size": 11,
        "axes.labelsize": 12,
        "xtick.labelsize": 10,
        "ytick.labelsize": 11,
    })

    workloads = [w for w in SHOW_WORKLOADS if w in WORKLOAD_SPECS]
    if not workloads:
        sys.exit("No valid workloads selected for display.")

    # A/B/C/D mapping
    wl_to_letter = {w: chr(ord('A') + i) for i, w in enumerate(workloads)}
    print("Workload mapping (use in caption):")
    for w in workloads:
        print(f"  {wl_to_letter[w]} = {w}")

    osr_set = sorted({int(r["os"]) for r in out_rows if r["os"] is not None})
    fluc_set = sorted({int(r["fluc"]) for r in out_rows if r["fluc"] is not None})

    # aggregator: (wl, os, fluc, method) -> mean
    agg: Dict[Tuple[str,int,int,str], List[float]] = {}
    for r in out_rows:
        key = (r["workload"], int(r["os"]), int(r["fluc"]), r["method"])
        agg.setdefault(key, []).append(float(r["normalized"]))

    # Precompute matrices for each fluctuation
    mats = {}  # fluc -> (pip_mat, thb_mat)
    for fl in fluc_set:
        pip_mat = np.full((len(workloads), len(osr_set)), np.nan, dtype=float)
        thb_mat = np.full((len(workloads), len(osr_set)), np.nan, dtype=float)
        for i, wl in enumerate(workloads):
            for j, osr in enumerate(osr_set):
                for meth, mat in (("powertrace", pip_mat), ("google", thb_mat)):
                    vals = agg.get((wl, osr, fl, meth), [])
                    if vals:
                        mat[i, j] = min(1.0, max(0.0, sum(vals)/len(vals)))
        mats[fl] = (pip_mat, thb_mat)

    # ---- Plot (rows = fluc levels, cols = 2 methods) ----
    os.makedirs(os.path.join(root, "plots"), exist_ok=True)

    # Size: width scales with OSR count; height scales with workloads × fluc rows
    fig_w = max(5.6, 0.32 * len(osr_set) * 2)      # two columns
    per_row_h = max(2.2, 0.44 * len(workloads))
    fig_h = max(2.6, per_row_h * len(fluc_set))

    fig, axes = plt.subplots(
        nrows=len(fluc_set), ncols=2,
        figsize=(fig_w, fig_h), dpi=160, constrained_layout=True
    )
    # ensure 2D indexing even for a single row
    if len(fluc_set) == 1:
        axes = [axes]

    reds = matplotlib.colormaps["Reds"].copy()
    blues = matplotlib.colormaps["Blues"].copy()
    try:
        reds.set_bad(color="#dddddd")
        blues.set_bad(color="#dddddd")
    except Exception:
        pass

    THR = 0.9

    def outline(ax, mat):
        nr, nc = mat.shape
        for i in range(nr):
            for j in range(nc):
                v = mat[i, j]
                if np.isnan(v) or v < THR:
                    continue
                ax.add_patch(matplotlib.patches.Rectangle(
                    (j - 0.5, i - 0.5), 1, 1, fill=False, edgecolor="black", linewidth=2.0
                ))

    def annotate(ax, mat):
        nr, nc = mat.shape
        for i in range(nr):
            for j in range(nc):
                v = mat[i, j]
                if np.isnan(v): continue
                tcolor = "white" if v >= 0.6 else "black"
                ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=9, color=tcolor)

    # draw panels
    for r, fl in enumerate(fluc_set):
        pip_mat, thb_mat = mats[fl]
        axL, axR = axes[r][0], axes[r][1]

        im0 = axL.imshow(pip_mat, aspect="auto", interpolation="nearest", vmin=0.0, vmax=1.0, cmap=reds)
        im1 = axR.imshow(thb_mat, aspect="auto", interpolation="nearest", vmin=0.0, vmax=1.0, cmap=blues)

        # ticks/labels
        for ax, right in ((axL, False), (axR, True)):
            ax.set_xticks(range(len(osr_set)))
            ax.set_xticklabels([str(x) for x in osr_set])
            ax.set_yticks(range(len(workloads)))
            # only left column shows y tick labels to save width
            if right:
                ax.set_yticklabels([])
            else:
                ax.set_yticklabels([wl_to_letter[w] for w in workloads])
            # x label only on bottom row
            if r == len(fluc_set) - 1:
                ax.set_xlabel("OSR (%)")
            # y label only on left column
            if not right:
                ax.set_ylabel("Workload")

        outline(axL, pip_mat); outline(axR, thb_mat)
        annotate(axL, pip_mat); annotate(axR, thb_mat)

        # Row label
        axL.text(-0.45, -0.85, f"Fluctuation: {fl}%", transform=axL.transData,
                 ha="left", va="center", fontsize=11)

    # ---- Two shared colorbars (one per column), placed ABOVE each column ----
    # Left column (PIP)
    sm_left = matplotlib.cm.ScalarMappable(
        norm=matplotlib.colors.Normalize(vmin=0.0, vmax=1.0), cmap=reds
    )
    sm_left.set_array([])
    cbar_left = fig.colorbar(
        sm_left, ax=[axes[r][0] for r in range(len(fluc_set))],
        orientation="horizontal", location="top"
    )
    cbar_left.set_label("PIP — Norm. Perf. (0..1)")

    # Right column (Thunderbolt)
    sm_right = matplotlib.cm.ScalarMappable(
        norm=matplotlib.colors.Normalize(vmin=0.0, vmax=1.0), cmap=blues
    )
    sm_right.set_array([])
    cbar_right = fig.colorbar(
        sm_right, ax=[axes[r][1] for r in range(len(fluc_set))],
        orientation="horizontal", location="top"
    )
    cbar_right.set_label("Thunderbolt — Norm. Perf. (0..1)")

    outp = os.path.join(root, "plots", "figure3.png")
    fig.savefig(outp, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {outp}")

if __name__ == "__main__":
    main()

