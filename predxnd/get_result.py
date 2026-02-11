import os
import re
import glob
import sys
import math

# Use CLI argument if provided, else None
app_param = sys.argv[1] if len(sys.argv) > 1 else None  # python3 get_result3.py fileserver

result_dir = './results-evaluation/'
files = glob.glob(os.path.join(result_dir, '*.log'))

summary = []
header = ["target_app", "target_bg", "source_bg", "avg_pred", "avg_truth", "error"]

for file in files:
    base = os.path.basename(file)
    m = re.match(r'app-(.+?)_tgt-bg-(.+?)_src-bg-(.+?)\.log', base)
    if not m:
        continue
    target_app, target_bg, source_bg = m.groups()

    pred_vals = []
    truth_vals = []
    in_pred = False
    in_truth = False

    with open(file) as f:
        for line in f:
            if "--- PREDICTION RESULTS ---" in line:
                in_pred = True
                in_truth = False
                continue
            if "--- GROUND TRUTH RESULTS ---" in line:
                in_pred = False
                in_truth = True
                continue
            if in_pred:
                m_pred = re.search(r'Estimated Power:\s*([\d.]+)', line)
                if m_pred:
                    pred_vals.append(float(m_pred.group(1)))
            if in_truth:
                m_truth = re.search(r'Truth:\s*([\d.]+)', line)
                if m_truth:
                    truth_vals.append(float(m_truth.group(1)))
    if pred_vals and truth_vals:
        avg_pred = sum(pred_vals) / len(pred_vals)
        avg_truth = sum(truth_vals) / len(truth_vals)
        error = abs(avg_pred - avg_truth) / avg_truth * 100
        summary.append([target_app, target_bg, source_bg, avg_pred, avg_truth, error])

def mean_std(vals):
    if not vals:
        return float('nan'), float('nan')
    mean = sum(vals) / len(vals)
    std = math.sqrt(sum((x - mean) ** 2 for x in vals) / len(vals))
    return mean, std

def avg_err(rows):
    vals = [row[5] for row in rows]
    return mean_std(vals)

def max_err(rows):
    if not rows:
        return float('nan'), []
    max_val = max(row[5] for row in rows)
    max_rows = [row for row in rows if row[5] == max_val]
    return max_val, max_rows

if app_param:
    print(f"\nError summary for app: {app_param}")
    app_cases = [
        ("As target_app", [row for row in summary if row[0] == app_param]),
        ("As target_bg", [row for row in summary if row[1] == app_param]),
        ("As source_bg", [row for row in summary if row[2] == app_param]),
        ("As any (target_app/target_bg/source_bg)", [
            row for row in summary if app_param in [row[0], row[1], row[2]]
        ]),
    ]
    for case_name, rows in app_cases:
        mean_v, std_v = avg_err(rows)
        max_v, max_rows = max_err(rows)
        print(f"{case_name}: mean, std={mean_v:.2f}, {std_v:.2f}, max={max_v:.2f}, n={len(rows)}")
        for r in max_rows:
            print("  Max case:", dict(zip(header, r)))
else:
    # Default: same, diff, all
    print(",".join(header))
    for row in summary:
        print(",".join(f"{x:.2f}" if isinstance(x, float) else str(x) for x in row))

    same_bg = [row for row in summary if row[1] == row[2]]
    diff_bg = [row for row in summary if row[1] != row[2]]
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

