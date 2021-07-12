#!/bin/bash

pip3 install pyserial

apt update
apt install -y git

git clone --recursive https://github.com/sunspec/pysunspec.git
cd pysunspec

python3 setup.py install