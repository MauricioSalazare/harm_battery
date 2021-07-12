@echo off
Call git clone --recursive https://github.com/sunspec/pysunspec.git
cd pysunspec
python setup.py install