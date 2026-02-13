#!/bin/bash
docker-compose down 
docker-compose up -d
./docker-cgroup.sh critical

cgexec -g cpu:user ./wrk3 \
  -target 'http://localhost:8080/wrk2-api/home-timeline/read?user_id=1&start=0&stop=10' \
  -duration 300s -sla-ms 500 \
  -phases '45s@200,10s@500,60s@300,15s@600,60s@300,10s@700,60s@300,15s@800,55s@200,10s@400' \
  -jitter-pct 10 -think-mean-ms 8

#./wrk -D exp -t 20 -c 40 -d 300 -L -s ./wrk2/scripts/social-network/compose-post.lua http://localhost:8080/wrk2-api/post/compose -R 50000
docker-compose down
