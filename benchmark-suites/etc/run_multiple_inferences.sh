#!/bin/bash

# Run inference concurrently (4 processes)
for i in {1..4}
do
   python3 realtime_detection.py &
done

wait
