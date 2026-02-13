#!/bin/bash
#
# check_system.sh: Pre-flight checker for the PIP artifact.
#
# This script verifies that the system meets the necessary hardware and
# software requirements to run the evaluation experiments. It checks for
# the presence and, where possible, the specific versions of key components.
#

echo "================================================="
echo "PIP Artifact - System Requirements Checker"
echo "================================================="

# --- Helper Functions ---
NC='\033[0m' # No Color
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
HARD_FAIL=0

pass() {
    printf "[ ${GREEN}PASS${NC} ] %s\n" "$1"
}

fail() {
    printf "[ ${RED}FAIL${NC} ] %s\n" "$1"
    HARD_FAIL=1
}

warn() {
    printf "[ ${YELLOW}WARN${NC} ] %s\n" "$1"
}

# Checks system tools. Uses substring match for flexibility.
check_tool_version() {
    local name="$1"
    local required_version="$2"
    local command_to_run="$3"
    local detected_version

    if ! command -v ${command_to_run%% *} &> /dev/null; then
        fail "$name is not installed."
        return
    fi

    # The command needs to be executed without quotes to handle pipelines
    detected_version=$(eval "$command_to_run")
    
    if [[ "$detected_version" == *"$required_version"* ]]; then
        pass "$name version is correct ($detected_version)."
    else
        warn "$name version is '$detected_version'. Recommended is '$required_version'."
    fi
}

# Checks python packages. Uses a "starts with" match for flexibility.
check_py_pkg_version() {
    local name="$1"
    local required_version="$2"
    
    local installed_version
    # Robustly get the version string from the line starting with "Version:"
    installed_version=$(pip show "$name" 2>/dev/null | grep '^Version:' | awk '{print $2}')
    
    if [ -z "$installed_version" ]; then
        fail "Python package '$name' is not installed."
        return
    fi

    # Use a "starts with" comparison to handle cases like "1.2.8" vs "1.2.8-Apache"
    if [[ "$installed_version" == "$required_version"* ]]; then
        pass "Python package '$name' version is correct ($installed_version)."
    else
        warn "Python package '$name' version is '$installed_version'. Recommended is '$required_version'."
    fi
}


# --- Main Checks ---

# 1. OS Check
echo -e "\n--- Checking Operating System ---"
if [ -f /etc/lsb-release ]; then
    source /etc/lsb-release
    if [ "$DISTRIB_ID" == "Ubuntu" ] && [[ "$DISTRIB_RELEASE" == "22.04"* ]]; then
        pass "OS is Ubuntu 22.04 (Recommended: 22.04.2 LTS)."
    else
        warn "OS is not Ubuntu 22.04 ($DISTRIB_ID $DISTRIB_RELEASE). The recommended OS is 22.04.2 LTS."
    fi
else
    warn "Could not determine OS version. Ubuntu 22.04.2 LTS is recommended."
fi

# 2. Sudo/Root Check
echo -e "\n--- Checking Permissions ---"
if sudo -n true 2>/dev/null; then
    pass "User has sudo privileges."
else
    fail "User does not have passwordless sudo privileges. Experiments require sudo."
fi

# 3. Hardware: RAPL Support Check
echo -e "\n--- Checking Hardware ---"
if [ -d "/sys/class/powercap/intel-rapl" ] || [ -d "/sys/class/powercap/amd_rapl" ]; then
    pass "CPU RAPL interface found."
else
    fail "CPU RAPL interface not found at /sys/class/powercap/. This is a critical requirement."
fi

# 4. Software: Command-line Tools Check
echo -e "\n--- Checking Key Commands ---"
check_tool_version "stress-ng" "0.13.12" "stress-ng --version | head -n 1"
check_tool_version "perf" "5.15" "perf --version"
check_tool_version "Docker" "28.2.2" "docker --version"
check_tool_version "Python" "3.10" "python3 --version"

# 5. Software: Python Packages Check
echo -e "\n--- Checking Python Packages ---"
check_py_pkg_version "catboost" "1.2.8"
check_py_pkg_version "scikit-learn" "1.7.2"
check_py_pkg_version "torch" "2.10.0"
check_py_pkg_version "pandas" "2.3.3"
check_py_pkg_version "numpy" "2.2.6"
check_py_pkg_version "tensorflow" "2.20.0"


# --- Final Verdict ---
echo -e "\n-------------------------------------------------"
if [ $HARD_FAIL -eq 1 ]; then
    echo -e "${RED}FAILURE:${NC} One or more critical requirements are not met. Please fix the issues above."
    exit 1
else
    echo -e "${GREEN}SUCCESS:${NC} All critical requirements are met. You are ready to run the experiments."
    echo -e "Please check for any ${YELLOW}WARN${NC} messages above, as minor version differences may affect reproducibility."
fi
echo "================================================="

exit 0
