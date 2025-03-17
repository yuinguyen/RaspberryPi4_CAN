'''
mcp2515.py
Original driver made by Longan-Labs' MicroPython_CAN_BUS_MCP2515 made for MCUs
that are compatible with MicroPython liek ESP32, RP2040, etc.
The code was then modified to be compatible with the Raspi 4
Modified by: Yui Nguyen
Date: March 16th, 2025
MCP2515 CAN controller implementation for Raspberry Pi 4
'''
import time
import collections
from typing import Any, Optional, List, Tuple

# Import SPI interface and CAN frame implementation
from .rpi_spi import SPI
from .constants import *
from .can import CAN_EFF_FLAG, CAN_EFF_MASK, CAN_ERR_FLAG, CAN_ERR_MASK
from .can import CAN_RTR_FLAG, CAN_SFF_MASK, CAN_IDLEN, CAN_MAX_DLEN, CANFrame

TXBnREGS = collections.namedtuple("TXBnREGS", "CTRL SIDH DATA")
RXBnREGS = collections.namedtuple("RXBnREGS", "CTRL SIDH DATA CANINTFRXnIF")

TXB = [
    TXBnREGS(REGISTER.MCP_TXB0CTRL, REGISTER.MCP_TXB0SIDH, REGISTER.MCP_TXB0DATA),
    TXBnREGS(REGISTER.MCP_TXB1CTRL, REGISTER.MCP_TXB1SIDH, REGISTER.MCP_TXB1DATA),
    TXBnREGS(REGISTER.MCP_TXB2CTRL, REGISTER.MCP_TXB2SIDH, REGISTER.MCP_TXB2DATA),
]

RXB = [
    RXBnREGS(
        REGISTER.MCP_RXB0CTRL,
        REGISTER.MCP_RXB0SIDH,
        REGISTER.MCP_RXB0DATA,
        CANINTF.CANINTF_RX0IF,
    ),
    RXBnREGS(
        REGISTER.MCP_RXB1CTRL,
        REGISTER.MCP_RXB1SIDH,
        REGISTER.MCP_RXB1DATA,
        CANINTF.CANINTF_RX1IF,
    ),
]


class CAN:
    def __init__(self, SPI: Any) -> None:
        self.SPI = SPI
        self.mcp2515_rx_index = 0

    def reset(self) -> int:
        self.SPI.start()
        self.SPI.transfer(INSTRUCTION.INSTRUCTION_RESET)
        self.SPI.end()

        time.sleep(0.01)  # 10ms delay

        # Initialize transmit buffers
        zeros = bytearray(14)
        self.setRegisters(REGISTER.MCP_TXB0CTRL, zeros)
        self.setRegisters(REGISTER.MCP_TXB1CTRL, zeros)
        self.setRegisters(REGISTER.MCP_TXB2CTRL, zeros)

        # Initialize receive buffers
        self.setRegister(REGISTER.MCP_RXB0CTRL, 0)
        self.setRegister(REGISTER.MCP_RXB1CTRL, 0)

        # Setup interrupt enables
        self.setRegister(
            REGISTER.MCP_CANINTE,
            CANINTF.CANINTF_RX0IF
            | CANINTF.CANINTF_RX1IF
            | CANINTF.CANINTF_ERRIF
            | CANINTF.CANINTF_MERRF,
        )

        # Receives all valid messages with either Standard or Extended Identifiers that
        # meet filter criteria. RXF0 is applied for RXB0, RXF1 is applied for RXB1
        self.modifyRegister(
            REGISTER.MCP_RXB0CTRL,
            RXBnCTRL_RXM_MASK | RXB0CTRL_BUKT | RXB0CTRL_FILHIT_MASK,
            RXBnCTRL_RXM_STDEXT | RXB0CTRL_BUKT | RXB0CTRL_FILHIT,
        )
        self.modifyRegister(
            REGISTER.MCP_RXB1CTRL,
            RXBnCTRL_RXM_MASK | RXB1CTRL_FILHIT_MASK,
            RXBnCTRL_RXM_STDEXT | RXB1CTRL_FILHIT,
        )

        # Clear filters and masks
        # Do not filter any standard frames for RXF0 used by RXB0
        # Do not filter any extended frames for RXF1 used by RXB1
        filters = [RXF.RXF0, RXF.RXF1, RXF.RXF2, RXF.RXF3, RXF.RXF4, RXF.RXF5]
        for f in filters:
            ext = True if f == RXF.RXF1 else False
            result = self.setFilter(f, ext, 0)
            if result != ERROR.ERROR_OK:
                return result
                
        masks = [MASK.MASK0, MASK.MASK1]
        for m in masks:
            result = self.setFilterMask(m, True, 0)
            if result != ERROR.ERROR_OK:
                return result

        return ERROR.ERROR_OK

    def readRegister(self, reg: int) -> int:
        self.SPI.start()
        self.SPI.transfer(INSTRUCTION.INSTRUCTION_READ)
        self.SPI.transfer(reg)
        ret = self.SPI.transfer(read=True)
        self.SPI.end()

        return ret

    def readRegisters(self, reg: int, n: int) -> List[int]:
        self.SPI.start()
        self.SPI.transfer(INSTRUCTION.INSTRUCTION_READ)
        self.SPI.transfer(reg)
        # MCP2515 has auto-increment of address-pointer
        values = []
        for i in range(n):
            values.append(self.SPI.transfer(read=True))
        self.SPI.end()

        return values

    def setRegister(self, reg: int, value: int) -> None:
        self.SPI.start()
        self.SPI.transfer(INSTRUCTION.INSTRUCTION_WRITE)
        self.SPI.transfer(reg)
        self.SPI.transfer(value)
        self.SPI.end()

    def setRegisters(self, reg: int, values: bytearray) -> None:
        self.SPI.start()
        self.SPI.transfer(INSTRUCTION.INSTRUCTION_WRITE)
        self.SPI.transfer(reg)
        for v in values:
            self.SPI.transfer(v)
        self.SPI.end()

    def modifyRegister(
        self, reg: int, mask: int, data: int, spifastend: bool = False
    ) -> None:
        self.SPI.start()
        self.SPI.transfer(INSTRUCTION.INSTRUCTION_BITMOD)
        self.SPI.transfer(reg)
        self.SPI.transfer(mask)
        self.SPI.transfer(data)
        if not spifastend:
            self.SPI.end()
        else:
            # Direct GPIO control - not recommended in RPi implementation
            # We'll use a regular end() with a shorter delay
            self.SPI.end()

    def getStatus(self) -> int:
        self.SPI.start()
        self.SPI.transfer(INSTRUCTION.INSTRUCTION_READ_STATUS)
        i = self.SPI.transfer(read=True)
        self.SPI.end()

        return i

    def setConfigMode(self) -> int:
        return self.setMode(CANCTRL_REQOP_MODE.CANCTRL_REQOP_CONFIG)

    def setListenOnlyMode(self) -> int:
        return self.setMode(CANCTRL_REQOP_MODE.CANCTRL_REQOP_LISTENONLY)

    def setSleepMode(self) -> int:
        return self.setMode(CANCTRL_REQOP_MODE.CANCTRL_REQOP_SLEEP)

    def setLoopbackMode(self) -> int:
        return self.setMode(CANCTRL_REQOP_MODE.CANCTRL_REQOP_LOOPBACK)

    def setNormalMode(self) -> int:
        return self.setMode(CANCTRL_REQOP_MODE.CANCTRL_REQOP_NORMAL)

    def setMode(self, mode: int) -> int:
        self.modifyRegister(REGISTER.MCP_CANCTRL, CANCTRL_REQOP, mode)

        # Wait for the mode to change (timeout after 10ms)
        start_time = time.time()
        modeMatch = False
        while (time.time() - start_time) < 0.01:  # 10ms timeout
            newmode = self.readRegister(REGISTER.MCP_CANSTAT)
            newmode &= CANSTAT_OPMOD

            modeMatch = newmode == mode
            if modeMatch:
                break
            time.sleep(0.001)  # 1ms delay

        return ERROR.ERROR_OK if modeMatch else ERROR.ERROR_FAIL

#     def setBitrate(self, canSpeed: int, canClock: int = CAN_CLOCK.MCP_8MHZ) -> int:
#         error = self.setConfigMode()
#         if error != ERROR.ERROR_OK:
#             return error
# 
#         set_ = 1
#         try:
#             cfg1, cfg2, cfg3 = CAN_CFGS[canClock][canSpeed]
#         except KeyError:
#             set_ = 0
# 
#         if set_:
#             self.setRegister(REGISTER.MCP_CNF1, cfg1)
#             self.setRegister(REGISTER.MCP_CNF2, cfg2)
#             self.setRegister(REGISTER.MCP_CNF3, cfg3)
#             return ERROR.ERROR_OK
#         return ERROR.ERROR_FAIL

    def setBitrate(self, canSpeed: int, canClock: int = CAN_CLOCK.MCP_16MHZ) -> int:
        error = self.setConfigMode()
        if error != ERROR.ERROR_OK:
            return error

        try:
            # First check if the clock type exists in the dictionary
            if canClock not in CAN_CFGS:
                print(f"Error: Invalid clock type {canClock}. Valid options are: {list(CAN_CFGS.keys())}")
                return ERROR.ERROR_FAIL
                
            # Then check if the speed exists for that clock type
            if canSpeed not in CAN_CFGS[canClock]:
                print(f"Error: Invalid speed {canSpeed} for clock type {canClock}.")
                print(f"Valid speeds for this clock are: {list(CAN_CFGS[canClock].keys())}")
                return ERROR.ERROR_FAIL
                
            # Now safely get the configuration values
            cfg1, cfg2, cfg3 = CAN_CFGS[canClock][canSpeed]
            
            # Set the registers
            self.setRegister(REGISTER.MCP_CNF1, cfg1)
            self.setRegister(REGISTER.MCP_CNF2, cfg2)
            self.setRegister(REGISTER.MCP_CNF3, cfg3)
            return ERROR.ERROR_OK
        except KeyError as e:
            print(f"Configuration error: {e}")
            print(f"Available clock types: {list(CAN_CFGS.keys())}")
            # If we have the requested clock, show available speeds for it
            if canClock in CAN_CFGS:
                print(f"Available speeds for clock {canClock}: {list(CAN_CFGS[canClock].keys())}")
            return ERROR.ERROR_FAIL
        except Exception as e:
            print(f"Unexpected error in setBitrate: {e}")
            return ERROR.ERROR_FAIL
    def setClkOut(self, divisor: int) -> int:
        if divisor == CAN_CLKOUT.CLKOUT_DISABLE:
            # Turn off CLKEN
            self.modifyRegister(REGISTER.MCP_CANCTRL, CANCTRL_CLKEN, 0x00)

            # Turn on CLKOUT for SOF
            self.modifyRegister(REGISTER.MCP_CNF3, CNF3_SOF, CNF3_SOF)
            return ERROR.ERROR_OK

        # Set the prescaler (CLKPRE)
        self.modifyRegister(REGISTER.MCP_CANCTRL, CANCTRL_CLKPRE, divisor)

        # Turn on CLKEN
        self.modifyRegister(REGISTER.MCP_CANCTRL, CANCTRL_CLKEN, CANCTRL_CLKEN)

        # Turn off CLKOUT for SOF
        self.modifyRegister(REGISTER.MCP_CNF3, CNF3_SOF, 0x00)
        return ERROR.ERROR_OK

    def prepareId(self, ext: int, id_: int) -> bytearray:
        canid = id_ & 0xFFFF
        buffer = bytearray(CAN_IDLEN)

        if ext:
            buffer[MCP_EID0] = canid & 0xFF
            buffer[MCP_EID8] = canid >> 8
            canid = id_ >> 16
            buffer[MCP_SIDL] = canid & 0x03
            buffer[MCP_SIDL] += (canid & 0x1C) << 3
            buffer[MCP_SIDL] |= TXB_EXIDE_MASK
            buffer[MCP_SIDH] = canid >> 5
        else:
            buffer[MCP_SIDH] = canid >> 3
            buffer[MCP_SIDL] = (canid & 0x07) << 5
            buffer[MCP_EID0] = 0
            buffer[MCP_EID8] = 0

        return buffer

    def setFilterMask(self, mask: int, ext: int, ulData: int) -> int:
        res = self.setConfigMode()
        if res != ERROR.ERROR_OK:
            return res

        reg = None
        if mask == MASK.MASK0:
            reg = REGISTER.MCP_RXM0SIDH
        elif mask == MASK.MASK1:
            reg = REGISTER.MCP_RXM1SIDH
        else:
            return ERROR.ERROR_FAIL

        tbufdata = self.prepareId(ext, ulData)
        self.setRegisters(reg, tbufdata)

        return ERROR.ERROR_OK

    def setFilter(self, ft: int, ext: int, ulData: int) -> int:
        res = self.setConfigMode()
        if res != ERROR.ERROR_OK:
            return res

        reg = None
        if ft == RXF.RXF0:
            reg = REGISTER.MCP_RXF0SIDH
        elif ft == RXF.RXF1:
            reg = REGISTER.MCP_RXF1SIDH
        elif ft == RXF.RXF2:
            reg = REGISTER.MCP_RXF2SIDH
        elif ft == RXF.RXF3:
            reg = REGISTER.MCP_RXF3SIDH
        elif ft == RXF.RXF4:
            reg = REGISTER.MCP_RXF4SIDH
        elif ft == RXF.RXF5:
            reg = REGISTER.MCP_RXF5SIDH
        else:
            return ERROR.ERROR_FAIL

        tbufdata = self.prepareId(ext, ulData)
        self.setRegisters(reg, tbufdata)

        return ERROR.ERROR_OK

    def sendMessage(self, frame: Any, txbn: Optional[int] = None) -> int:
        if txbn is None:
            return self.sendMessage_(frame)

        if frame.dlc > CAN_MAX_DLEN:
            return ERROR.ERROR_FAILTX

        txbuf = TXB[txbn]

        ext = frame.can_id & CAN_EFF_FLAG
        rtr = frame.can_id & CAN_RTR_FLAG
        id_ = frame.can_id & (CAN_EFF_MASK if ext else CAN_SFF_MASK)

        data = self.prepareId(ext, id_)
        mcp_dlc = (frame.dlc | RTR_MASK) if rtr else frame.dlc

        data.extend(bytearray(1 + frame.dlc))
        data[MCP_DLC] = mcp_dlc
        for i in range(frame.dlc):
            data[MCP_DATA + i] = frame.data[i]

        self.setRegisters(txbuf.SIDH, data)

        self.modifyRegister(
            txbuf.CTRL, TXBnCTRL.TXB_TXREQ, TXBnCTRL.TXB_TXREQ, spifastend=True
        )

        ctrl = self.readRegister(txbuf.CTRL)
        if ctrl & (TXBnCTRL.TXB_ABTF | TXBnCTRL.TXB_MLOA | TXBnCTRL.TXB_TXERR):
            return ERROR.ERROR_FAILTX
        return ERROR.ERROR_OK

    def sendMessage_(self, frame: Any) -> int:
        if frame.dlc > CAN_MAX_DLEN:
            return ERROR.ERROR_FAILTX

        txBuffers = [TXBn.TXB0, TXBn.TXB1, TXBn.TXB2]

        for i in range(N_TXBUFFERS):
            txbuf = TXB[txBuffers[i]]
            ctrlval = self.readRegister(txbuf.CTRL)
            if (ctrlval & TXBnCTRL.TXB_TXREQ) == 0:
                return self.sendMessage(frame, txBuffers[i])

        return ERROR.ERROR_ALLTXBUSY

    def readMessage(self, rxbn: int = None) -> Tuple[int, Any]:
        if rxbn is None:
            return self.readMessage_()

        rxb = RXB[rxbn]

        tbufdata = self.readRegisters(rxb.SIDH, 1 + CAN_IDLEN)

        id_ = (tbufdata[MCP_SIDH] << 3) + (tbufdata[MCP_SIDL] >> 5)

        if (tbufdata[MCP_SIDL] & TXB_EXIDE_MASK) == TXB_EXIDE_MASK:
            id_ = (id_ << 2) + (tbufdata[MCP_SIDL] & 0x03)
            id_ = (id_ << 8) + tbufdata[MCP_EID8]
            id_ = (id_ << 8) + tbufdata[MCP_EID0]
            id_ |= CAN_EFF_FLAG

        dlc = tbufdata[MCP_DLC] & DLC_MASK
        if dlc > CAN_MAX_DLEN:
            return ERROR.ERROR_FAIL, None

        ctrl = self.readRegister(rxb.CTRL)
        if ctrl & RXBnCTRL_RTR:
            id_ |= CAN_RTR_FLAG

        frame = CANFrame(can_id=id_)

        data_array = self.readRegisters(rxb.DATA, dlc)
        frame.data = bytes(data_array)

        return ERROR.ERROR_OK, frame

    def readMessage_(self) -> Tuple[int, Any]:
        rc = ERROR.ERROR_NOMSG, None

        stat = self.getStatus()
        if stat & STAT.STAT_RX0IF and self.mcp2515_rx_index == 0:
            rc = self.readMessage(RXBn.RXB0)
            if self.getStatus() & STAT.STAT_RX1IF:
                self.mcp2515_rx_index = 1
            self.modifyRegister(REGISTER.MCP_CANINTF, RXB[RXBn.RXB0].CANINTFRXnIF, 0)
        elif stat & STAT.STAT_RX1IF:
            rc = self.readMessage(RXBn.RXB1)
            self.mcp2515_rx_index = 0
            self.modifyRegister(REGISTER.MCP_CANINTF, RXB[RXBn.RXB1].CANINTFRXnIF, 0)

        return rc

    def checkReceive(self) -> bool:
        res = self.getStatus()
        if res & STAT_RXIF_MASK:
            return True
        return False

    def checkError(self) -> bool:
        eflg = self.getErrorFlags()

        if eflg & EFLG_ERRORMASK:
            return True
        return False

    def getErrorFlags(self) -> int:
        return self.readRegister(REGISTER.MCP_EFLG)

    def clearRXnOVRFlags(self) -> None:
        self.modifyRegister(REGISTER.MCP_EFLG, EFLG.EFLG_RX0OVR | EFLG.EFLG_RX1OVR, 0)

    def getInterrupts(self) -> int:
        return self.readRegister(REGISTER.MCP_CANINTF)

    def clearInterrupts(self) -> None:
        self.setRegister(REGISTER.MCP_CANINTF, 0)

    def getInterruptMask(self) -> int:
        return self.readRegister(REGISTER.MCP_CANINTE)

    def clearTXInterrupts(self) -> None:
        self.modifyRegister(
            REGISTER.MCP_CANINTF,
            CANINTF.CANINTF_TX0IF | CANINTF.CANINTF_TX1IF | CANINTF.CANINTF_TX2IF,
            0,
        )

    def clearRXnOVR(self) -> None:
        eflg = self.getErrorFlags()
        if eflg != 0:
            self.clearRXnOVRFlags()
            self.clearInterrupts()

    def clearMERR(self) -> None:
        self.modifyRegister(REGISTER.MCP_CANINTF, CANINTF.CANINTF_MERRF, 0)

    def clearERRIF(self) -> None:
        self.modifyRegister(REGISTER.MCP_CANINTF, CANINTF.CANINTF_ERRIF, 0)
        
    def cleanup(self) -> None:
        """Clean up resources"""
        self.SPI.cleanup()
