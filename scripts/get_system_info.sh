#!/bin/bash
#
# get_system_info.sh: Gathers key system information for debugging.
#
# This script collects details about the hardware, OS, and software environment
# and saves it to a log file. If the evaluator encounters issues, they can
# run this script and share the output with the authors.
#

LOG_FILE="system_info.log"
echo "--- Gathering system information for debugging ---"
echo "Output will be saved to: $LOG_FILE"

{
    echo "================================================="
    echo "PIP Artifact - System Information"
    echo "Generated on: $(date)"
    echo "================================================="

    echo -e "
--- CPU Information ---"
    lscpu

    echo -e "
--- Memory Information ---"
    free -h

    echo -e "
--- OS and Kernel Information ---"
    uname -a
    echo ""
    [ -f /etc/lsb-release ] && cat /etc/lsb-release

    echo -e "
--- Docker Version ---"
    docker --version

    echo -e "
--- Python Version ---"
    python3 --version

    echo -e "
--- Pip Packages ---"
    pip list

    echo -e "
--- Disk Usage ---"
    df -h .

    echo -e "
--- System Uptime ---"
    uptime

} > "$LOG_FILE" 2>&1

echo "--- System information successfully saved to $LOG_FILE ---"

