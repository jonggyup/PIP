#!/bin/bash

# Get the directory of the script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Fileserver benchmark
pushd "$SCRIPT_DIR/benchmark-suites/filebench" > /dev/null
./setup.sh
echo 0 > /proc/sys/kernel/randomize_va_space
./filebench -f ./workloads/fileserver.f
popd > /dev/null

# Hotel reservation benchmark
pushd "$SCRIPT_DIR/benchmark-suites/DeathStarBench/hotelReservation" > /dev/null
./run.sh
popd > /dev/null

# Social network benchmark
pushd "$SCRIPT_DIR/benchmark-suites/DeathStarBench/socialNetwork" > /dev/null
./run.sh
popd > /dev/null

# Kernel compilation benchmark
pushd "$SCRIPT_DIR/benchmark-suites/kcbench" > /dev/null
./setup.sh
./run.sh
popd > /dev/null

# BERT benchmark
pushd "$SCRIPT_DIR/benchmark-suites/ML-training" > /dev/null
python3 bert_benchmark.py
popd > /dev/null

# CNN benchmark
pushd "$SCRIPT_DIR/benchmark-suites/ML-training" > /dev/null
python3 cnn2.py
popd > /dev/null

# tfidvec benchmark
pushd "$SCRIPT_DIR/benchmark-suites/ML-training" > /dev/null
python3 tfidfvec.py
popd > /dev/null

# tfidvec benchmark
pushd "$SCRIPT_DIR/benchmark-suites/etc" > /dev/null
python3 cnninf.py --duration=300
popd > /dev/null

