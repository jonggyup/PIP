#!/bin/bash
/usr/local/bin/docker-compose down 
/usr/local/bin/docker-compose up -d
./docker-cgroup.sh user
#cgexec -g cpu:user ./wrk -D exp -t 20 -c 40 -d 300 -L -s ./wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua http://0.0.0.0:5000 -R 50000
#cgexec -g cpu:user ./wrk -D exp -t 30 -c 60 -d 300 -L -s ./wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua http://0.0.0.0:5000 -R 100000
#cgexec -g cpu:user ./wrk -D exp -t 8 -c 16 -d 300 -L -s ./wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua http://0.0.0.0:5000 -R 90000

cgexec -g cpu:user ./wrk3 \
  -target 'http://0.0.0.0:5000' \
  -duration 300s -sla-ms 300 \
  -phases '10s@300,10s@600,30s@300,10s@800,40s@250,10s@900,40s@220,15s@900,55s@280,10s@500' \
  -jitter-pct 10 -think-mean-ms 8

/usr/local/bin/docker-compose down
