#!/bin/bash
/usr/local/bin/docker-compose down 
/usr/local/bin/docker-compose up -d
./docker-cgroup.sh critical

#./wrk -D exp -t 20 -c 40 -d 300 -L -s ./wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua http://0.0.0.0:5000 -R 300000

cgexec -g cpu:user ./wrk3 \
  -target 'http://0.0.0.0:5000' \
  -duration 300s -sla-ms 300 \
  -phases '30s@500,10s@800,30s@400,15s@900,60s@400,10s@800,30s@520,15s@900,55s@380,10s@500' \
  -jitter-pct 10 -think-mean-ms 8


/usr/local/bin/docker-compose down
