#!/bin/bash
set -e

# cleanup old build
sudo rm -rfv /usr/local/lib/libboron* /usr/local/bin/boron /usr/lib/libfaun.* /usr/local/share/man/man1/boron.*

# Basic dependencies
sudo apt-get update
sudo apt-get install -y \
  git build-essential autotools-dev libpng-dev libvorbis-dev libpulse-dev \
  libxcursor-dev libsdl2-dev libxml2-dev

# Clean cache
sudo apt-get clean

# Clone and build boron
git clone https://git.code.sf.net/p/urlan/boron/code urlan-boron-code
cd urlan-boron-code
./configure
make
sudo make install

# Link and configure Boron library
echo "/usr/local/lib" | sudo tee /etc/ld.so.conf.d/boron.conf
sudo ln -s /usr/local/lib/libboron.so.2.96.0 /usr/local/lib/libboron.so
sudo ldconfig

# Clone xu4 engine
cd ..
git clone https://github.com/xu4-engine/u4.git

# Move boron headers to expected place if necessary
mkdir -p u4/src/boron
cp urlan-boron-code/include/* u4/src/boron/

# Prepare faun submodule
cd u4/src/faun
git submodule update --init
./configure --no_flac
make
sudo make DESTDIR=/usr install

# build xu4
cd ../..
./configure
make download
make mod
make
sudo make install

# copy needed files
sudo install -D -m 755 src/xu4 /usr/bin/xu4
sudo install -D -m 644 render.pak /usr/share/xu4/render.pak
sudo install -m 644 u4upgrad.zip ultima4.zip Ultima-IV.mod U4-Upgrade.mod /usr/share/xu4

echo "Setup complete. Run the game with xu4"
