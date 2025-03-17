'''
rpi_spi.py
Original driver made by Longan-Labs' MicroPython_CAN_BUS_MCP2515 made for MCUs
that are compatible with MicroPython liek ESP32, RP2040, etc.
The code was then modified to be compatible with the Raspi 4
Modified by: Yui Nguyen
Date: March 16th, 2025
SPI Interface for Raspberry Pi 4
'''
import time
import spidev
import RPi.GPIO as GPIO

from .constants import SPI_DEFAULT_BAUDRATE, SPI_DUMMY_INT, SPI_TRANSFER_LEN, SPI_HOLD_US

class SPI:
    def __init__(self, cs=8, baudrate=SPI_DEFAULT_BAUDRATE, bus=0, device=0):
        """Initialize SPI interface for Raspberry Pi 4.
        
        Args:
            cs: GPIO pin number for chip select (BCM numbering)
            baudrate: SPI clock frequency in Hz
            bus: SPI bus number
            device: SPI device/chip select
        """
        # Initialize GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(cs, GPIO.OUT)
        GPIO.output(cs, GPIO.HIGH)
        
        # SPI CS pin
        self._SPICS = cs
        
        # Initialize SPI
        self._SPI = spidev.SpiDev()
        self._SPI.open(bus, device) 
        #self._SPI.open(0, 1)
        self._SPI.max_speed_hz = baudrate
        self._SPI.mode = 0  # SPI mode 0: CPOL=0, CPHA=0
        self._SPI.lsbfirst = False  # MSB first
        
        # End communication
        self.end()
    
    def start(self):
        """Pull CS low to start SPI communication."""
        GPIO.output(self._SPICS, GPIO.LOW)
        time.sleep(SPI_HOLD_US / 1000000.0)
    
    def end(self):
        """Pull CS high to end SPI communication."""
        GPIO.output(self._SPICS, GPIO.HIGH)
        time.sleep(SPI_HOLD_US / 1000000.0)
    
    def transfer(self, value=SPI_DUMMY_INT, read=False):
        """Write int value to SPI and read SPI value simultaneously.
        
        Args:
            value: Byte value to write (0-255)
            read: If True, return the read value, otherwise None
            
        Returns:
            Read byte value if read=True, otherwise None
        """
        if read:
            # For read operations, send the value and read the response
            response = self._SPI.xfer2([value])
            return response[0]
        else:
            # For write operations, just send the value
            self._SPI.xfer2([value])
            return None

    def cleanup(self):
        """Clean up GPIO and SPI resources."""
        try:
            self._SPI.close()
        except:
            pass
