import os
import glob
import numpy as np
import sys

def analyze_results(directory):
    """
    Analyzes the result files in the given directory and prints a comparison table.
    """
    results = {}
    all_errors = {'PIP': [], 'Kepler': [], 'PowerAPI': []}
    files = sorted(glob.glob(os.path.join(directory, '*.dat')))

    if not files:
        print(f"No .dat files found in {directory}")
        return

    for f_path in files:
        workload = os.path.basename(f_path).replace('.dat', '')
        pip_errors = []
        kepler_errors = []
        powerapi_errors = []

        with open(f_path, 'r') as f:
            for line in f:
                try:
                    parts = [float(p.strip()) for p in line.split(',')]
                    if len(parts) >= 13:
                        pip_errors.append(parts[7])
                        kepler_errors.append(parts[11])
                        powerapi_errors.append(parts[12])
                except (ValueError, IndexError) as e:
                    print(f"Could not parse line in {f_path}: {line.strip()} - {e}")

        if pip_errors:
            results[workload] = {
                'PIP': {'mean': np.mean(pip_errors), 'std': np.std(pip_errors)},
                'Kepler': {'mean': np.mean(kepler_errors), 'std': np.std(kepler_errors)},
                'PowerAPI': {'mean': np.mean(powerapi_errors), 'std': np.std(powerapi_errors)}
            }
            all_errors['PIP'].extend(pip_errors)
            all_errors['Kepler'].extend(kepler_errors)
            all_errors['PowerAPI'].extend(powerapi_errors)

    summary = {
        'PIP': {'mean': np.mean([res['PIP']['mean'] for res in results.values()]), 'std': np.std(all_errors['PIP'])},
        'Kepler': {'mean': np.mean([res['Kepler']['mean'] for res in results.values()]), 'std': np.std(all_errors['Kepler'])},
        'PowerAPI': {'mean': np.mean([res['PowerAPI']['mean'] for res in results.values()]), 'std': np.std(all_errors['PowerAPI'])}
    }

    print_table(results, summary)

def print_table(results, summary):
    """
    Prints the results in a formatted table with a hierarchical header.
    """
    if not results:
        print("No results to display.")
        return

    # Define column widths
    workload_col_width = 15
    mape_col_width = 10
    std_col_width = 10
    method_col_width = mape_col_width + std_col_width + 3  # for " | "

    # Header - Line 1: Method names
    header1 = (f"{'':<{workload_col_width}} | "
               f"{'PIP':^{method_col_width}} | "
               f"{'Kepler':^{method_col_width}} | "
               f"{'PowerAPI':^{method_col_width}}")
    print(header1)

    # Header - Line 2: Sub-columns (MAPE, SD)
    header2_parts = []
    for _ in range(3):
        header2_parts.append(f"{'MAPE (%)':<{mape_col_width}} | {'SD (%)':<{std_col_width}}")
    header2 = f"{'Workload':<{workload_col_width}} | {' | '.join(header2_parts)}"
    print(header2)

    # Separator
    print("-" * len(header2))

    # Body
    for workload, data in results.items():
        pip_mean = data['PIP']['mean']
        pip_std = data['PIP']['std']
        kepler_mean = data['Kepler']['mean']
        kepler_std = data['Kepler']['std']
        powerapi_mean = data['PowerAPI']['mean']
        powerapi_std = data['PowerAPI']['std']
        print(f"{workload:<{workload_col_width}} | "
              f"{pip_mean:<{mape_col_width}.1f} | {pip_std:<{std_col_width}.1f} | "
              f"{kepler_mean:<{mape_col_width}.1f} | {kepler_std:<{std_col_width}.1f} | "
              f"{powerapi_mean:<{mape_col_width}.1f} | {powerapi_std:<{std_col_width}.1f}")

    # Summary
    print("-" * len(header2))
    avg_pip_mean = summary['PIP']['mean']
    avg_pip_std = summary['PIP']['std']
    avg_kepler_mean = summary['Kepler']['mean']
    avg_kepler_std = summary['Kepler']['std']
    avg_powerapi_mean = summary['PowerAPI']['mean']
    avg_powerapi_std = summary['PowerAPI']['std']

    print(f"{'Average':<{workload_col_width}} | "
          f"{avg_pip_mean:<{mape_col_width}.1f} | {avg_pip_std:<{std_col_width}.1f} | "
          f"{avg_kepler_mean:<{mape_col_width}.1f} | {avg_kepler_std:<{std_col_width}.1f} | "
          f"{avg_powerapi_mean:<{mape_col_width}.1f} | {avg_powerapi_std:<{std_col_width}.1f}")


if __name__ == '__main__':
    output_path = 'plots/table2.txt'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        original_stdout = sys.stdout
        sys.stdout = f
        try:
            analyze_results('results-comp')
        finally:
            sys.stdout = original_stdout
    print(f"Results saved to {output_path}")