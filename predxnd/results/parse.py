#!/usr/bin/env python3

import os
import re
import numpy as np

results_dir = "."  # Change if needed
result_files = [f for f in os.listdir(results_dir) if f.endswith(".dat")]

def extract_errors(filepath):
    errors = []
    with open(filepath, 'r') as f:
        for line in f:
            match = re.search(r'Error:\s*([\d.]+)%', line)
            if match:
                errors.append(float(match.group(1)))
    return errors

print(f"{'File'}, {'Mean Error (%)'}, {'Std Dev (%)'}")

for filename in result_files:
    path = os.path.join(results_dir, filename)
    errors = extract_errors(path)
    if len(errors) > 3:
        errors.sort()
        trimmed = errors[:-3]  # Remove 3 highest
        mean = np.mean(trimmed)
        std = np.std(trimmed)
        print(f"{filename.replace('.dat','')}, {mean:.2f}, {std:.2f}")

