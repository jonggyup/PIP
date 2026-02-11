#!/bin/bash
echo 0 > /proc/sys/kernel/randomize_va_space
./filebench -f ./workloads/fileserver.f
sleep 60
#./filebench -f ./workloads/webserver.f
#sleep 60
