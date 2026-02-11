import os
import re
import glob
import sys
import math

# Use CLI argument if provided, else None
app_param = sys.argv[1] if len(sys.argv) > 1 else None  # python3 get_result3.py fileserver

result_dir = './results-evaluation-throttle/'
files = glob.glob(os.path.join(result_dir, 'app-*.log'))

summary = []
# now includes throttle columns
header = ["target_app", "target_bg", "target_thr", "source_bg", "source_thr", "avg_pred", "avg_truth", "error"]

for file in files:
    base = os.path.basename(file)
    # updated regex to capture two throttle values
    m = re.match(
        r'app-(.+?)_tgt-bg-(.+?)-(\d+)_src-bg-(.+?)-(\d+)\.log',
        base
    )
    if not m:
        continue
    target_app, target_bg, target_thr, source_bg, source_thr = m.groups()
    target_thr = int(target_thr)
    source_thr = int(source_thr)

    pred_vals = []
    truth_vals = []
    in_pred = in_truth = False

    with open(file) as f:
        for line in f:
            if "--- PREDICTION RESULTS ---" in line:
                in_pred, in_truth = True, False
                continue
            if "--- GROUND TRUTH RESULTS ---" in line:
                in_pred, in_truth = False, True
                continue
            if in_pred:
                m_pred = re.search(r'Estimated Power:\s*([\d.]+)', line)
                if m_pred:
                    pred_vals.append(float(m_pred.group(1)))
            elif in_truth:
                m_truth = re.search(r'Truth:\s*([\d.]+)', line)
                if m_truth:
                    truth_vals.append(float(m_truth.group(1)))

    if pred_vals and truth_vals:
        avg_pred = sum(pred_vals) / len(pred_vals)
        avg_truth = sum(truth_vals) / len(truth_vals)
        error = abs(avg_pred - avg_truth) / avg_truth * 100
        # include throttles in the row
        summary.append([
            target_app, target_bg, target_thr,
            source_bg, source_thr,
            avg_pred, avg_truth, error
        ])

def mean_std(vals):
    if not vals:
        return float('nan'), float('nan')
    mean = sum(vals) / len(vals)
    std = math.sqrt(sum((x - mean) ** 2 for x in vals) / len(vals))
    return mean, std

def avg_err(rows):
    vals = [row[7] for row in rows]  # error is now at index 7
    return mean_std(vals)

def max_err(rows):
    if not rows:
        return float('nan'), []
    max_val = max(row[7] for row in rows)
    max_rows = [row for row in rows if row[7] == max_val]
    return max_val, max_rows

if app_param:
    print(f"\nError summary for app: {app_param}")
    app_cases = [
        ("As target_app", [r for r in summary if r[0] == app_param]),
        ("As target_bg",  [r for r in summary if r[1] == app_param]),
        ("As source_bg",  [r for r in summary if r[3] == app_param]),  # index 3 now
        ("As any",        [r for r in summary if app_param in (r[0], r[1], r[3])]),
    ]
    for case_name, rows in app_cases:
        mean_v, std_v = avg_err(rows)
        max_v, max_rows = max_err(rows)
        print(f"{case_name}: mean, std={mean_v:.2f}, {std_v:.2f}, max={max_v:.2f}, n={len(rows)}")
        for r in max_rows:
            print("  Max case:", dict(zip(header, r)))
else:
    # Default: print all rows
    print(",".join(header))
    for row in summary:
        print(",".join(
            f"{x:.2f}" if isinstance(x, float) else str(x)
            for x in row
        ))

    # compare target_bg vs source_bg (now index 1 vs 3)
    same_bg = [r for r in summary if r[1] == r[3]]
    diff_bg = [r for r in summary if r[1] != r[3]]
    all_rows = summary

    print("\nError Summary (%):")

    mean_same, std_same = avg_err(same_bg)
    max_same, max_same_rows = max_err(same_bg)
    print(f"Same source/target BG: mean, std={mean_same:.2f}, {std_same:.2f}, max={max_same:.2f}")
    for r in max_same_rows:
        print("  Max case:", dict(zip(header, r)))

    mean_diff, std_diff = avg_err(diff_bg)
    max_diff, max_diff_rows = max_err(diff_bg)
    print(f"Different source/target BG: mean, std={mean_diff:.2f}, {std_diff:.2f}, max={max_diff:.2f}")
    for r in max_diff_rows:
        print("  Max case:", dict(zip(header, r)))

    mean_all, std_all = avg_err(all_rows)
    max_all, max_all_rows = max_err(all_rows)
    print(f"All cases: mean, std={mean_all:.2f}, {std_all:.2f}, max={max_all:.2f}")
    for r in max_all_rows:
        print("  Max case:", dict(zip(header, r)))

