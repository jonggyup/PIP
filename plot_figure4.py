#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vertical layout version: wider plots for stacking top-to-bottom.
- Wider figure to fill a single column comfortably.
- Enlarged fonts, thicker lines, larger markers for visibility.
- Full box (all spines shown).
- Shows only half of x-labels, but always includes first & last.
- Saves PNG (raster) and PDF (vector) per workload.
"""

import sys, os, csv
from collections import defaultdict
from typing import Dict, List, Tuple

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

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    ratio_csv = os.path.join(root, "results-oversub-fluc", "be_ratio.csv")
    if not os.path.exists(ratio_csv):
        print(f"Missing {ratio_csv}. Run parse_fluc_be.py first.", file=sys.stderr)
        sys.exit(1)

    rows = read_ratio_csv(ratio_csv)
    if not rows:
        print("No rows in be_ratio.csv.", file=sys.stderr); sys.exit(2)

    # Group per workload: fluc -> list of (os, ratio)
    by_wl: Dict[str, Dict[int, List[Tuple[int, float]]]] = defaultdict(lambda: defaultdict(list))
    os_all: Dict[str, set] = defaultdict(set)
    for wl, osr, fluc, ratio in rows:
        by_wl[wl][fluc].append((osr, ratio))
        os_all[wl].add(osr)

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

    out_dir = os.path.join(root, "plots")
    os.makedirs(out_dir, exist_ok=True)

    for wl, fluc_map in by_wl.items():
        osr_list = sorted(os_all[wl])
        if not osr_list:
            continue


        # —— Wider and shorter figure for vertical stacking ——
        fig_w = 4.6   # inches (wider)
        fig_h = 1.7   # inches (shorter)
        fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h), dpi=450)

        # Plot each fluc line
        for fluc, pairs in sorted(fluc_map.items()):
            pairs_sorted = sorted(pairs, key=lambda x: x[0])
            val_by_os = {o: v for o, v in pairs_sorted}
            y = np.array([val_by_os.get(o, np.nan) for o in osr_list], dtype=float)

            ax.plot(
                osr_list,
                y,
                marker="o",
                linewidth=2.0,
                markersize=5.8,
                label=f"fluc={fluc}",
                clip_on=True,
            )

        # Reference lines
        ax.axhline(1.00, color="black", linestyle="--", linewidth=1.0, label="_nolegend_")
        ax.axhline(1.05, color="#666666", linestyle=":", linewidth=1.0, label="_nolegend_")

        # Labels
        ax.set_xlabel("OSR (%)", fontsize=11)
        ax.set_ylabel("PIP / Thunderbolt (×)", fontsize=11, labelpad=2.0)

        # Show ALL x-labels
        ax.set_xticks(osr_list)
        ax.set_xticklabels([str(t) for t in osr_list], fontsize=10)
        ax.tick_params(axis="y", which="major", labelsize=10, pad=2.0)

       # Title
        ax.set_title(wl, fontsize=12, pad=4.0)

        # Legend
        ax.legend(
            fontsize=9.5,
            ncol=1,
            frameon=False,
            loc="best",
            handlelength=2.0,
            borderaxespad=0.3,
        )

        # Keep full box
        for spine in ("top", "right", "bottom", "left"):
            ax.spines[spine].set_visible(True)

        ax.margins(x=0.01)

        # Y-limits tightened
        finite_vals = [v for pairs in fluc_map.values() for _, v in pairs if not np.isnan(v)]
        if finite_vals:
            ymin = min(0.88, min(finite_vals) - 0.05)
            ymax = max(2, max(finite_vals) + 1)  # raised from 1.15 → 1.25
            ax.set_ylim(ymin, ymax)

        fig.tight_layout(pad=0.25)
        base = os.path.join(out_dir, f"figure4_{wl}")
        fig.savefig(base + ".png", bbox_inches="tight")
        plt.close(fig)
        print(f"Wrote {base}.png")

if __name__ == "__main__":
    main()