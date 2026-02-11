#!/bin/bash
#/etc/init.d/redis-server start
memtier_benchmark --clients 10 --ratio 1:1 --data-size 128 --threads=20 -n 100000 -d 50000 --pipeline=1
#/etc/init.d/redis-server stop
