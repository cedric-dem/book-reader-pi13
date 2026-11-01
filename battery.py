#!/usr/bin/env python
import struct
try:
        import smbus  # apt package python3-smbus
except ImportError:
        import smbus2 as smbus  # pip install smbus2 (same API, works inside a venv)
import sys
import time

CW2015_ADDRESS   = 0X62
CW2015_REG_VCELL = 0X02
CW2015_REG_SOC   = 0X04
CW2015_REG_MODE  = 0X0A



def readVoltage(bus):
        "This function returns as float the voltage from the Raspi UPS Hat via the provided SMBus object"
        read = bus.read_word_data(CW2015_ADDRESS, CW2015_REG_VCELL)
        swapped = struct.unpack("<H", struct.pack(">H", read))[0]
        voltage = swapped * 0.305 /1000
        return voltage


def readCapacity(bus):
        "This function returns as a float the remaining capacity of the battery connected to the Raspi UPS Hat via the provided SMBus object"
        read = bus.read_word_data(CW2015_ADDRESS, CW2015_REG_SOC)
        swapped = struct.unpack("<H", struct.pack(">H", read))[0]
        capacity = swapped/256
        return capacity


def QuickStart(bus):
        "This function wake up the CW2015 and make a quick-start fuel-gauge calculations "
        bus.write_word_data(CW2015_ADDRESS, CW2015_REG_MODE, 0x30)


# Bus shared by read_battery_level, opened (and the CW2015 woken up) on the first call
_bus = None


def read_battery_level():
        "Returns the battery percentage as an int between 0 and 100 (used by run_ui.py)"
        global _bus
        if _bus is None:
                _bus = smbus.SMBus(1)  # 1 = /dev/i2c-1 (port I2C1)
                QuickStart(_bus)
        return max(0, min(100, int(round(readCapacity(_bus)))))




#----------------------------------------------------------------------------------
# Standalone monitoring loop, only when run directly (python battery.py), not when imported

if __name__ == "__main__":
        import RPi.GPIO as GPIO

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(4,GPIO.IN)  # GPIO4 is used to detect whether an external power supply is inserted

        bus = smbus.SMBus(1)  # 0 = /dev/i2c-0 (port I2C0), 1 = /dev/i2c-1 (port I2C1)


        QuickStart(bus)

        print ("  ")
        print ("Initialize the CW2015 ......")


        while True:

         print ("++++++++++++++++++++")
         print ("Voltage:%5.2fV" % readVoltage(bus))
         print ("Battery:%5i%%" % readCapacity(bus))

         if readCapacity(bus) == 100:
                print ("Battery FULL")
         if readCapacity(bus) < 5:
                print ("Battery LOW")

        #GPIO is high when power is plugged in
         if (GPIO.input(4) == GPIO.HIGH):
                print ("Power Adapter Plug In ")
         if (GPIO.input(4) == GPIO.LOW):
                print ("Power Adapter Unplug")

         print ("++++++++++++++++++++")
         time.sleep(2)
