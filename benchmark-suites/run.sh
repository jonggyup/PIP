#!/bin/bash
pushd ./filebench/
#./setup.sh
./run.sh
popd

pushd ./DeathStarBench/hotelReservation
./run.sh
popd

pushd ./jonggyu/DeathStarBench/socialNetwork
./run.sh
popd

#pushd /proj/tasrdma-PG0/jonggyu/memtier_benchmark
#make install
#popd

pushd /proj/tasrdma-PG0/jonggyu/kcbench
./run.sh
popd
