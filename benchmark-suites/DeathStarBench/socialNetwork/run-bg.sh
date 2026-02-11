#!/bin/bash
docker-compose down 
docker-compose up -d
./docker-cgroup.sh critical
cgexec -g cpu:critical ./wrk -D exp -t 8 -c 16 -d 300 -L -s ./wrk2/scripts/social-network/compose-post.lua http://localhost:8080/wrk2-api/post/compose -R 90000
docker-compose down
