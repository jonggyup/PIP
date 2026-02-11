#!/bin/bash
docker-compose down 
docker-compose up -d
#./docker-cgroup.sh
./wrk -D exp -t 20 -c 40 -d 300 -L -s ./wrk2/scripts/social-network/compose-post.lua http://localhost:8080/wrk2-api/post/compose -R 50000
docker-compose down
