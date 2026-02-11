#!/bin/bash
yes | ./dependencies.sh
rm ./data/training-data.csv
pushd ./scripts
./governor.sh
./collect_data.sh
popd
sleep 10

(cd ./benchmark-suites/etc && ./install_models.sh)

pushd ./estimation
touch budget
echo 300 > budget
../scripts/topol_size.sh 
popd

pushd ./train_test
python3 ML_create.py
python3 ML_create-perf.py
python3 ML_create-kepler.py
python3 ML_create-powerapi.py

python3 ML_create-v1.1.py
python3 ML_create-v1.2.py
python3 ML_create-v1.3.py

sleep 10
python3 idle_map.py 1
popd

sleep 10

./run-bench-initial.sh
rmdir /sys/fs/cgroup/user
(cd ./scripts && ./cgroup_init.sh)

cp ./estimation/topol_metric_size.dat ./predxnd/
