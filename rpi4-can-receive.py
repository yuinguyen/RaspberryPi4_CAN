#!/usr/bin/env python3
'''
spi4-can-receive.py
Original driver made by Longan-Labs' MicroPython_CAN_BUS_MCP2515 made for MCUs
that are compatible with MicroPython liek ESP32, RP2040, etc.
The code was then modified to be compatible with the Raspi 4
Modified by: Yui Nguyen
Date: March 16th, 2025
A simple example to receive data from CAN bus on Raspberry Pi 4
'''
import sys
import time
from can_driver import CAN_1, CanError, CAN_SPEED, CAN_CLOCK

SPI0_CE0_PIN = 8
SPI0_CE1_PIN = 7

# Setup
can = CAN_1(board="RaspberryPi4", spics=SPI0_CE0_PIN) 

# Initialize - default 250kbps @ CAN module crystal frequency = 8MHz, change if network uses a different baudrate
# or module uses a different crystal clk source
ret = can.begin(bitrate=CAN_SPEED.CAN_250KBPS,canclock=CAN_CLOCK.MCP_8MHZ)
if ret != CanError.ERROR_OK:
    print("Error initializing CAN!")
    sys.exit(1)
print("Initialized successfully!")

# Receive loop
print("Waiting for CAN messages...")
try:
    while True:
        if can.checkReceive():
            error, msg = can.recv()
            if error == CanError.ERROR_OK:
                print('------------------------------')
                print("CAN ID: %#x" % msg.can_id)
                print("Is RTR frame:", msg.is_remote_frame)
                print("Is EFF frame:", msg.is_extended_id)
                print("CAN data hex:", msg.data.hex())
                print("CAN data dlc:", msg.dlc)
        else:
            time.sleep(0.1)
except KeyboardInterrupt:
    print("\nExiting...")
finally:
    # Clean up
    can.cleanup()
    print("CAN interface closed")
