#!/bin/bash
../wrk -D exp -t 32 -c 400 -d 100 -L -s ../wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua http://10.96.6.203:5000 -R 90000
