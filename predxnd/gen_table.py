import os
import re
import glob
import csv

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

def avg_err(rows):
    vals = [row[5] for row in rows]
    return sum(vals) / len(vals) if vals else float('nan')

def max_err(rows):
    if not rows:
        return float('nan')
    return max(row[5] for row in rows)

apps = sorted(set(sum([[row[0], row[1], row[2]] for row in summary], [])))

cases = [
    ("Target App", lambda app, row: row[0] == app),
    ("Dst BG",  lambda app, row: row[1] == app),
    ("Src BG",  lambda app, row: row[2] == app),
    ("Any",        lambda app, row: app in [row[0], row[1], row[2]]),
]

def make_table(table_fn):
    table = []
    for case_name, selector in cases:
        row_vals = []
        for app in apps:
            rows = [row for row in summary if selector(app, row)]
            row_vals.append(table_fn(rows))
        table.append([case_name] + row_vals)
    return table

avg_table = make_table(avg_err)
max_table = make_table(max_err)

# Write average error table as CSV
with open("average_error_table.csv", "w", newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["Case"] + apps)
    writer.writerows([[r[0]] + [f"{v:.2f}" for v in r[1:]] for r in avg_table])

# Write max error table as CSV
with open("max_error_table.csv", "w", newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["Case"] + apps)
    writer.writerows([[r[0]] + [f"{v:.2f}" for v in r[1:]] for r in max_table])

print("Wrote average_error_table.csv and max_error_table.csv")

