#!/bin/bash
/usr/local/bin/docker-compose down 
/usr/local/bin/docker-compose up -d
./docker-cgroup.sh critical
./wrk -D exp -t 20 -c 40 -d 300 -L -s ./wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua http://0.0.0.0:5000 -R 300000
/usr/local/bin/docker-compose down
