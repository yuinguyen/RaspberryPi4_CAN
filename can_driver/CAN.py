'''
CAN.py
Original driver made by Longan-Labs' MicroPython_CAN_BUS_MCP2515 made for MCUs
that are compatible with MicroPython liek ESP32, RP2040, etc.
The code was then modified to be compatible with the Raspi 4
Modified by: Yui Nguyen
Date: March 16th, 2025
CAN_1 Class Adapter for Raspberry Pi 4
'''
from .constants import (
    CAN_CLOCK,
    CAN_SPEED,
    ERROR,
)
from .can import CANFrame, CAN_EFF_FLAG, CAN_RTR_FLAG
from .rpi_spi import SPI

class CanError:
    ERROR_OK = ERROR.ERROR_OK
    ERROR_FAIL = ERROR.ERROR_FAIL

class CanMsgFlag:
    RTR = CAN_RTR_FLAG
    EFF = CAN_EFF_FLAG

class CanMsg:
    def __init__(self, can_id=0, data=None, flags=None):
        if flags:
            self.frame = CANFrame(can_id | flags, data)
        else:
            self.frame = CANFrame(can_id, data)
        self.is_remote_frame = self.frame.is_remote_frame
        self.is_extended_id = self.frame.is_extended_id
        self.can_id = self.frame.arbitration_id
        self.data = self.frame.data
        self.dlc = self.frame.dlc
        
    def _set_frame(self, frame):
        self.frame = frame
        self.is_remote_frame = self.frame.is_remote_frame
        self.is_extended_id = self.frame.is_extended_id
        self.can_id = self.frame.arbitration_id
        self.data = self.frame.data
        self.dlc = self.frame.dlc
        
    def _get_frame(self):
        return self.frame

class CAN_1:
    ERROR = ERROR
    def __init__(self, board="RaspberryPi4", spi=0, spics=8):
        """Initialize CAN_1 interface for Raspberry Pi 4.
        
        Args:
            board: Board name (default: "RaspberryPi4")
            spi: SPI bus number (default: 0)
            spics: SPI chip select GPIO pin (default: 8 for CE0)
        """
        self.can = None
        self.board = board
        self.spi_bus = spi
        self.spics = spics
        # Initialize the SPI interface
        # For SPI0, CE0 ...not sure why its configured as device=1 for CE0,
        # but just note that it may not be very intuitive
        spi_interface = SPI(cs=spics, bus=spi, device=1)
        # Initialize the CAN controller
        from .mcp2515 import CAN
        self.can = CAN(spi_interface)
        
    def begin(self, bitrate=CAN_SPEED.CAN_250KBPS, canclock=CAN_CLOCK.MCP_8MHZ, mode='normal'):
        """Initialize the CAN bus with the specified settings.
        
        Args:
            bitrate: CAN bus bitrate (default: 250kbps)
            canclock: MCP2515 crystal frequency (default: 8MHz)
            mode: CAN operation mode (default: 'normal')
            
        Returns:
            ERROR_OK on success, otherwise error code
        """
        ret = self.can.reset()
        if ret != ERROR.ERROR_OK:
            print("Reset Error")
            return ret
            
        ret = self.can.setBitrate(bitrate, canclock)
        if ret != ERROR.ERROR_OK:
            print("Set Bit Rate Error")
            return ret
        
        # Set the CAN operation mode
        if mode == 'normal':
            ret = self.can.setNormalMode()
        elif mode == 'loopback':
            ret = self.can.setLoopbackMode()
        elif mode == 'listen':
            ret = self.can.setListenOnlyMode()
        elif mode == 'config':
            ret = self.can.setConfigMode()
        
        return ret
        
    def init_mask(self, mask, is_ext_id, mask_id):
        """Set CAN bus receive mask.
        
        Args:
            mask: Mask index (0 or 1)
            is_ext_id: True for extended ID, False for standard ID
            mask_id: Mask ID value
            
        Returns:
            ERROR_OK on success, otherwise error code
        """
        ret = self.can.setFilterMask(mask + 1, is_ext_id, mask_id)
        if ret != ERROR.ERROR_OK:
            return ret
            
        ret = self.can.setNormalMode()
        return ret
        
    def init_filter(self, ft, is_ext_id, filter_id):
        """Set CAN bus receive filter.
        
        Args:
            ft: Filter index (0-5)
            is_ext_id: True for extended ID, False for standard ID
            filter_id: Filter ID value
            
        Returns:
            ERROR_OK on success, otherwise error code
        """
        ret = self.can.setFilter(ft, is_ext_id, filter_id)
        if ret != ERROR.ERROR_OK:
            return ret
            
        ret = self.can.setNormalMode()
        return ret
        
    def checkReceive(self):
        """Check if any messages are available for reception.
        
        Returns:
            True if messages are available, False otherwise
        """
        return self.can.checkReceive()
        
    def recv(self):
        """Receive a CAN message.
        
        Returns:
            Tuple with (error_code, CanMsg object)
        """
        error, frame = self.can.readMessage()
        msg = CanMsg()
        if frame:  # Only set the frame if it's not None
            msg._set_frame(frame)
        return error, msg
        
    def send(self, msg):
        """Send a CAN message.
        
        Args:
            msg: CanMsg object
            
        Returns:
            ERROR_OK on success, otherwise error code
        """
        frame = msg._get_frame()
        error = self.can.sendMessage(frame)
        return error
    
    def cleanup(self):
        """Release resources and cleanup."""
        if self.can:
            self.can.cleanup()
