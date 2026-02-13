#!/bin/bash
#
# show_versions.sh: Displays the versions of critical software components.
#
# This script helps document the exact environment used for the evaluation,
# which is crucial for reproducibility.
#

echo "================================================="
echo "PIP Artifact - Software Version Information"
echo "================================================="

# Helper to print version or an error message
print_version() {
    local name="$1"
    local command="$2"
    
    printf "%-20s: " "$name"
    if command -v ${command%% *} &> /dev/null; then
        $command 2>&1 | head -n 1
    else
        echo "Not Found"
    fi
}

# --- OS and Kernel ---
echo -e "
--- OS and Kernel ---"
print_version "Operating System" "lsb_release -ds"
print_version "Kernel" "uname -r"

# --- System Tools & Compilers ---
echo -e "
--- System Tools ---"
print_version "gcc" "gcc --version"
print_version "Docker" "docker --version"
print_version "docker-compose" "docker-compose --version"
print_version "perf" "perf --version"
print_version "stress-ng" "stress-ng --version"

# --- Python Environment ---
echo -e "
--- Python Environment ---"
print_version "Python" "python3 --version"

echo "Key Python Packages:"
packages=("catboost" "scikit-learn" "torch" "pandas" "numpy")
for pkg in "${packages[@]}"; do
    # Use pip show to get the version of each package
    version_info=$(pip show "$pkg" 2>/dev/null | grep Version)
    if [ -n "$version_info" ]; then
        printf "  %-18s: %s
" "$pkg" "${version_info##* }"
    else
        printf "  %-18s: Not Found
" "$pkg"
    fi
done

echo "================================================="
