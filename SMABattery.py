"""
SMA_SunnyIslandController: Reading out and controlling a SMA Sunny Island 8.0-13 (battery storage)
MIT License
Copyright (c) 2021 Harm van den Brink
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

__author__  = 'Harm van den Brink'
__email__   = 'harmvandenbrink@gmail.com'
__license__ = 'MIT License'

__version__ = '0.0.5'
__status__  = 'Beta'

import time
import threading
from collections import OrderedDict

import sunspec.core.client as clientSunspec
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pymodbus.compat import iteritems
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder, BinaryPayloadDecoder
import argparse
import json

class SMABattery:
    MODBUS_IP = '192.168.105.20'
    MODBUS_PORT = 502
    MAX_CHARGE_VALUE = 5500
    MAX_DISCHARGE_VALUE = -5500
    ACTIVATE_CONTROL_ADDRESS = 40151
    CHANGE_POWER_ADDRESS = 40149
    DEFAULT_READ_MODELS = ['common', 'inverter', 'nameplate', 'status', 'controls', 'storage']

    sunSpecClient = None
    modbusClient = None

    SETPOINT = 0

    def __init__(self, modbus_ip=MODBUS_IP, modbus_port=MODBUS_PORT):
        self.MODBUS_IP = modbus_ip
        self.MODBUS_PORT = modbus_port
        assert self.connect()

        threading.Thread(target=self.send_scheduled, daemon=True).start()

    def connect(self):
        try:
            self.sunSpecClient = clientSunspec.SunSpecClientDevice(clientSunspec.TCP, 126, ipaddr=self.MODBUS_IP, ipport=self.MODBUS_PORT, timeout=2.0)
            self.modbusClient = ModbusClient(self.MODBUS_IP, port=self.MODBUS_PORT, unit_id=3 , auto_open=True, auto_close=True)
            print("Connection sucessful!")
            return True
        except:
            print("Error connecting to the inverter")
            return False

    def changePower(self, power):
        print(f"changePower {power}")
        limited = self.__limit(power, self.MAX_DISCHARGE_VALUE, self.MAX_CHARGE_VALUE)
        self.SETPOINT = limited
        print(f"__limit result: {limited}")
        
        print("/changePower")

    def send_scheduled(self):
        print("Start scheduled sending")
        # 40149 Active power setpoint - int32
        # 40151 Eff./reac. pow. contr. via comm. 802 = "active" 803 = "inactive", ENUM - uint32
        # 40153 Reactive power setpoint - uint32
        # 0x0322 is the value (802) to activate the control of power via modbus communication
        while True:
            print(f"Sending... {self.SETPOINT}W")
            self.__sendModbus(self.ACTIVATE_CONTROL_ADDRESS, 0x0322, "uint32")
            self.__sendModbus(self.CHANGE_POWER_ADDRESS, self.SETPOINT, "int32")
            time.sleep(5)

    def readSMAValues(self):
        sma = {}

        for model in self.sunSpecClient.models:
            if model in self.DEFAULT_READ_MODELS:
                getattr(self.sunSpecClient, model).read()
            for point in getattr(self.sunSpecClient, model).points:
                value = getattr(getattr(self.sunSpecClient, model), point)
                if value is not None:
                    if model not in sma:
                        sma[model] = {}
                    sma[model][point] = value

        return sma

    def __limit(self, num, minimum, maximum):
        return int(max(min(num, maximum), minimum))

    def __sendModbus(self, address, value, type):
        print("__sendModbus")
        try:
            if(self.modbusClient.connect() == False):
                print("Modbus connection lost, trying to reconnect...")
                self.modbusClient = ModbusClient(self.MODBUS_IP, port=self.MODBUS_PORT, unit_id=3 , auto_open=True, auto_close=True)
                print("Modbus Connected: {}".format(self.modbusClient.connect()))
            else:
                # SMA expects everything in Big Endian format
                builder = BinaryPayloadBuilder(byteorder=Endian.Big, wordorder=Endian.Big)
                # Only unsigned int32 and signed int32 are built in. It is enough to control the flow of power of the battery.
                if (type == "uint32"):
                    builder.add_32bit_uint(value)
                if (type == "int32"):
                    builder.add_32bit_int(value)
                registers = builder.to_registers()
                self.modbusClient.write_registers(address, registers, unit=3)
        except:
            print("sending failed. trying reconnect and resend")
            self.connect()
            time.sleep(1)
            self.__sendModbus(address, value, type)
        print("/__sendModbus")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument('-s', '--set_power', required=False, type=float, default=None,
                        help="Set output power of the battery in Watts. Positive, give to the grid. Negative, charge. Max value: 5500 Watts on (dis)charge")
    parser.add_argument('-r', '--read', required=False, type=bool, default=True,
                        help='Alpha for the learning rage.')
    args, unknown = parser.parse_known_args()

    battery_sma = SMABattery()

    if args.set_power is not None:
        assert isinstance(args.set_power, float), "Set power should be a float value"
        assert battery_sma.MAX_DISCHARGE_VALUE <= args.set_power <= battery_sma.MAX_CHARGE_VALUE, "Operating battery outside limits"
        battery_sma.changePower(args.set_power)

        while True:
            continue

        # time.sleep(8)
        # battery_sma.changePower(-5000)
        # time.sleep(20)
        # battery_sma.changePower(0)
        # time.sleep(120)

    elif args.read:
        print("---------------")
        print("Battery values:")
        print("---------------")
        print(json.dumps(battery_sma.readSMAValues(), indent=4))

    else:
        print("Run the file with the correct arguments, use --help to know more.")

