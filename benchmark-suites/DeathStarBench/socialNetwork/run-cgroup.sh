#!/bin/bash
docker-compose down 
docker-compose up -d
./docker-cgroup.sh user
#cgexec -g cpu:user ./wrk -D exp -t 20 -c 40 -d 300 -L -s ./wrk2/scripts/social-network/compose-post.lua http://localhost:8080/wrk2-api/post/compose -R 3000
#cgexec -g cpu:user ./wrk -D exp -t 30 -c 60 -d 300 -L -s ./wrk2/scripts/social-network/compose-post.lua http://localhost:8080/wrk2-api/post/compose -R 9000
#cgexec -g cpu:user ./wrk -D exp -t 30 -c 60 -d 300 -L -s ./wrk2/scripts/social-network/compose-post.lua http://localhost:8080/wrk2-api/post/compose -R 1500
#cgexec -g cpu:user ./wrk -D exp -t 8 -c 16 -d 300 -L -s ./wrk2/scripts/social-network/compose-post.lua http://localhost:8080/wrk2-api/post/compose -R 90000


cgexec -g cpu:user ./wrk3 \
  -target 'http://localhost:8080/wrk2-api/home-timeline/read?user_id=1&start=0&stop=10' \
  -duration 300s -sla-ms 500 \
  -phases '30s@100,10s@200,30s@150,10s@250,60s@150,10s@300,60s@150,15s@250,55s@150,10s@400' \
  -jitter-pct 10 -think-mean-ms 8

docker-compose down
