#!/bin/bash
sudo pkill -ef send_print > /dev/null 2>&1
sudo pkill -ef merge_pred > /dev/null 2>&1
sudo pkill -f "filebench|run-cgroup.sh|run-bg.sh|cnninf.py|bert_benchmark.py|cnn2.py|tfidvec.py" > /dev/null 2>&1
if [ -f /sys/fs/cgroup/user/cgroup.procs ]; then
	xargs -a /sys/fs/cgroup/user/cgroup.procs -r sudo kill -9 > /dev/null 2>&1
fi
if [ -f /sys/fs/cgroup/critical/cgroup.procs ]; then
	xargs -a /sys/fs/cgroup/critical/cgroup.procs -r sudo kill -9 > /dev/null 2>&1
fi
(cd /users/jonggyu/PowerTrace/benchmark-suites/DeathStarBench/socialNetwork && docker-compose down)
(cd /users/jonggyu/PowerTrace/benchmark-suites/DeathStarBench/hotelReservation && docker-compose down)
docker volume rm $(docker volume ls -q)


