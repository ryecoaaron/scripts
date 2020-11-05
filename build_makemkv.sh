#!/bin/bash

MAKEMKV_VERS=1.15.3

apt-get update
apt-get install -y build-essential pkg-config libc6-dev libssl-dev libexpat1-dev libavcodec-dev libgl1-mesa-dev qtbase5-dev zlib1g-dev less
apt-get clean

wget https://www.makemkv.com/download/makemkv-bin-${MAKEMKV_VERS}.tar.gz
wget https://www.makemkv.com/download/makemkv-oss-${MAKEMKV_VERS}.tar.gz

tar xvzf makemkv-bin-${MAKEMKV_VERS}.tar.gz
tar xvzf makemkv-oss-${MAKEMKV_VERS}.tar.gz

cd makemkv-oss-${MAKEMKV_VERS}
./configure
make
sudo make install

cd ..

cd makemkv-bin-${MAKEMKV_VERS}
echo "yes" | make
sudo make install
