#!/bin/bash
sudo add-apt-repository ppa:colin-king/stress-ng
sudo apt update
apt install --ignore-missing -y python3-pip pip linux-tools-common linux-tools-generic linux-tools-$(uname -r) stress-ng=0.13.12-2ubuntu1 htop 

apt install --ignore-missing -y luarocks libgfortran5 lm-sensors sysbench ffmpeg powercap-utils ipmitool
apt install docker.io

sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.1/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

luarocks install luasocket
pip install -r requirements.txt
pip install tf-keras torch
pip install --upgrade "transformers[torch]" "accelerate>=0.26.0"


sudo apt install lsb-release curl gpg
sudo rm -f /usr/share/keyrings/redis-archive-keyring.gpg
curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg

echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/redis.list
sudo apt-get update
sudo apt-get install memtier-benchmark bison flex


sudo apt-get install -y redis libevent-dev libssl-dev cgroup-tools
