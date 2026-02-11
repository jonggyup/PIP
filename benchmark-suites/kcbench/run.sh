#!/bin/bash
make -C '/root/.cache/kcbench/linux-5.7/' mrproper
./kcbench --skip-compilerchecks
