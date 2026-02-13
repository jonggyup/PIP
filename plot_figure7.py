import os
import re
import glob
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

def parse_perf_file(filename):
    with open(filename, 'r') as f:
        data = f.readlines()

    base = os.path.basename(filename)
    tokens = base.split('_')
    group1 = tokens[0]
    group2 = tokens[1] if len(tokens) > 1 else "NA"
    system = tokens[2] if len(tokens) > 2 else "NA"
    perf_value = None

    if group1 == "fileserver":
        for line in data:
            if "IO Summary:" in line:
                match = re.search(r'([\d\.]+)mb/s', line)
                if match:
                    perf_value = float(match.group(1))
                break
    elif group1 in ("hotel", "social"):
        for line in data:
            if "avg_goodput_rps:" in line:
                match = re.search(r'avg_goodput_rps:\s*([\d\.]+)', line)
                if match:
                    perf_value = float(match.group(1))
                    break
    elif group1 == "cnninf":
        for line in data:
            if "Average inferences/sec:" in line:
                match = re.search(r'Average inferences/sec:\s*([\d\.]+)', line)
                if match:
                    perf_value = float(match.group(1))
                break
    return group1, group2, system, perf_value

def process_perf_data(directory):
    results = {}
    for filename in glob.glob(os.path.join(directory, "*_performance1.dat")):
        group1, group2, system, perf = parse_perf_file(filename)
        if perf is not None:
            results[(group1, group2, system)] = perf

    grouped = {}
    for (group1, group2, system), perf in results.items():
        grouped.setdefault((group1, group2), {})[system] = perf

    data = []
    for (group1, group2), systems in grouped.items():
        if "sys" in systems and "google" in systems:
            google_val = systems["google"]
            sys_val = systems["sys"]
            improvement = sys_val / google_val
            data.append([group1, group2, improvement, sys_val, google_val])
    
    return pd.DataFrame(data, columns=["Group1", "Group2", "Improvement", "Sys", "Google"])


def compute_power_file_metrics(filename):
    with open(filename, "r") as f:
        lines = [line.strip() for line in f if line.strip()]
    
    if len(lines) <= 40:
        return None
    
    data_lines = lines[20:-20]
    values = []
    for line in data_lines:
        parts = [x.strip() for x in line.split("|")]
        if len(parts) < 2:
            continue
        try:
            val_last = float(parts[-1])
            values.append(val_last)
        except ValueError:
            continue

    if not values:
        return None

    average = sum(values) / len(values)
    active_power = average - 100
    return {"active_power": active_power}

def process_power_data(directory):
    group_data = {}
    for filepath in glob.glob(os.path.join(directory, "*_power.dat")):
        filename = os.path.basename(filepath)
        parts = filename.split("_")
        if len(parts) < 4:
            continue

        LSapp, BEapp, sysname = parts[0], parts[1], parts[2]

        if sysname == "sys":
            label = "PIP"
        elif sysname == "google":
            label = "Thunderbolt"
        else:
            continue

        metrics = compute_power_file_metrics(filepath)
        if metrics is None:
            continue

        key = (LSapp, BEapp)
        if key not in group_data:
            group_data[key] = {}
        group_data[key][label] = metrics

    data = []
    for (group1, group2), systems in group_data.items():
        if "PIP" in systems and "Thunderbolt" in systems:
            pip_data = systems["PIP"]
            th_data = systems["Thunderbolt"]
            if th_data["active_power"] > 0:
                improvement = pip_data["active_power"] / th_data["active_power"]
            else:
                improvement = 0.0
            data.append([group1, group2, improvement, pip_data['active_power'], th_data['active_power']])

    return pd.DataFrame(data, columns=["Group1", "Group2", "Improvement", "PIP", "Thunderbolt"])

def generate_heatmap(df, output_pdf, title, ylabel):
    plt.rcParams["font.family"] = "serif"
    plt.rcParams["font.serif"] = ["Times New Roman", "Times", "DejaVu Serif"]
    plt.rcParams.update({'font.size': 20})

    group1_mapping = {"cnninf": "D", "fileserver": "G", "hotel": "E", "social": "F"}
    group2_mapping = {"bert": "A", "cnn": "B", "tfidfvec": "C"}

    df["Group1_letter"] = df["Group1"].map(group1_mapping)
    df["Group2_letter"] = df["Group2"].map(group2_mapping)
    
    df.dropna(subset=["Group1_letter", "Group2_letter"], inplace=True)

    pivot_table = df.pivot(index="Group1_letter", columns="Group2_letter", values="Improvement")
    row_order = sorted(pivot_table.index)
    col_order = sorted(pivot_table.columns)

    plt.figure(figsize=(5, 5))
    sns.heatmap(pivot_table.loc[row_order, col_order],
                vmin=0, vmax=3,
                cmap="inferno",
                annot=True, fmt=".2f",
                cbar_kws={"label": "Improvement", "ticks": [0, 1, 2, 3]})

    plt.xlabel("Best-effort applications")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(output_pdf)
    plt.close()

def main():
    data_dir = "results-qos-cap"
    
    # Process performance data
    perf_df = process_perf_data(data_dir)
    generate_heatmap(perf_df, 
                     "./plots/figure7a.png", 
                     "Perf. Imp.", 
                     "User-facing applications")

    # Process power data
    power_df = process_power_data(data_dir)
    generate_heatmap(power_df, 
                     "./plots/figure7b.png", 
                     "Pwr Imp.", 
                     "User-facing applications")

    print("Processing complete. Generated heatmaps for results-qos-cap.")

if __name__ == "__main__":
    main()
