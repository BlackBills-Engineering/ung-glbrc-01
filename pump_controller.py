import serial
import time
import logging
import threading
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from abc import ABC, abstractmethod

from models import PumpStatus, PumpInfo, TransactionData, PumpStatusResponse


class GilbarcoTwoWireProtocol:
    """
    Gilbarco Two-Wire Protocol implementation for SK700-II dispensers
    Based on TWOTP-IS-IS2.26-P specification
    """
    
    # Command codes (hexadecimal)
    CMD_STATUS = 0x0           # Status poll
    CMD_AUTHORIZE = 0x1        # Authorize
    CMD_SEND_DATA = 0x2        # Send data to pump 
    CMD_STOP = 0x3             # Pump stop
    CMD_TRANSACTION = 0x4      # Request transaction data
    CMD_TOTALS = 0x5           # Request pump totals
    CMD_REAL_TIME = 0x6        # Request real-time money
    CMD_ALL_STOP_1 = 0xF       # All stop command part 1
    CMD_ALL_STOP_2 = 0xC       # All stop command part 2
    
    # Status codes (from pump responses)
    STATUS_DATA_ERROR = 0x0
    STATUS_OFF = 0x6
    STATUS_CALL = 0x7
    STATUS_AUTH = 0x8          # Authorized but not delivering
    STATUS_BUSY = 0x9          # Delivering product
    STATUS_PEOT = 0xA          # Transaction complete (PEOT)
    STATUS_FEOT = 0xB          # Transaction complete (FEOT)
    STATUS_STOP = 0xC          # Pump stop
    STATUS_SEND_DATA = 0xD     # Send data response
    
    # Data Control Words
    DCW_STX = 0xFF             # Start of text
    DCW_ETX = 0xF0             # End of text  
    DCW_LRC_NEXT = 0xFB        # LRC check character next
    DCW_PUMP_ID_NEXT = 0xF8    # Pump identifier next
    DCW_GRADE_NEXT = 0xF6      # Grade data next
    DCW_PPU_NEXT = 0xF7        # PPU data next
    DCW_VOLUME_NEXT = 0xF9     # Volume data next
    DCW_MONEY_NEXT = 0xFA      # Money data next
    
    # Protocol constants
    BAUDRATE = 5787            # Standard two-wire baud rate
    WORD_BITS = 11             # Start + 8 data + parity + stop
    PARITY = serial.PARITY_EVEN
    TIMEOUT_MS = 68            # Maximum response time
    
    @staticmethod
    def pump_id_to_nibble(pump_id: int) -> int:
        """Convert pump ID (1-16) to protocol nibble (1-F, 0)"""
        if pump_id == 16:
            return 0x0
        elif 1 <= pump_id <= 15:
            return pump_id
        else:
            raise ValueError(f"Invalid pump ID: {pump_id}")
    
    @staticmethod
    def nibble_to_pump_id(nibble: int) -> int:
        """Convert protocol nibble to pump ID"""
        if nibble == 0x0:
            return 16
        elif 1 <= nibble <= 15:
            return nibble
        else:
            raise ValueError(f"Invalid pump nibble: {nibble}")
    
    @staticmethod
    def build_status_command(pump_id: int) -> bytes:
        """Build status poll command: '0' '<p>'"""
        pump_nibble = GilbarcoTwoWireProtocol.pump_id_to_nibble(pump_id)
        command = (GilbarcoTwoWireProtocol.CMD_STATUS << 4) | pump_nibble
        return bytes([command])
    
    @staticmethod
    def build_authorize_command(pump_id: int) -> bytes:
        """Build authorize command: '1' '<p>'"""
        pump_nibble = GilbarcoTwoWireProtocol.pump_id_to_nibble(pump_id)
        command = (GilbarcoTwoWireProtocol.CMD_AUTHORIZE << 4) | pump_nibble
        return bytes([command])
    
    @staticmethod
    def build_stop_command(pump_id: int) -> bytes:
        """Build pump stop command: '3' '<p>'"""
        pump_nibble = GilbarcoTwoWireProtocol.pump_id_to_nibble(pump_id)
        command = (GilbarcoTwoWireProtocol.CMD_STOP << 4) | pump_nibble
        return bytes([command])
    
    @staticmethod
    def build_transaction_request(pump_id: int) -> bytes:
        """Build transaction data request: '4' '<p>'"""
        pump_nibble = GilbarcoTwoWireProtocol.pump_id_to_nibble(pump_id)
        command = (GilbarcoTwoWireProtocol.CMD_TRANSACTION << 4) | pump_nibble
        return bytes([command])
    
    @staticmethod
    def build_all_stop_command() -> bytes:
        """Build all stop command: 'F' 'C'"""
        return bytes([0xFC])  # F=15, C=12 combined
    
    @staticmethod
    def parse_status_response(response: bytes) -> Tuple[int, int]:
        """Parse status response to get pump ID and status"""
        if len(response) != 1:
            raise ValueError("Invalid status response length")
        
        word = response[0]
        status = (word >> 4) & 0xF
        pump_nibble = word & 0xF
        pump_id = GilbarcoTwoWireProtocol.nibble_to_pump_id(pump_nibble)
        
        return pump_id, status
    
    @staticmethod 
    def status_code_to_enum(status_code: int) -> PumpStatus:
        """Convert two-wire status code to PumpStatus enum"""
        status_map = {
            GilbarcoTwoWireProtocol.STATUS_DATA_ERROR: PumpStatus.ERROR,
            GilbarcoTwoWireProtocol.STATUS_OFF: PumpStatus.IDLE,
            GilbarcoTwoWireProtocol.STATUS_CALL: PumpStatus.CALLING,
            GilbarcoTwoWireProtocol.STATUS_AUTH: PumpStatus.AUTHORIZED,
            GilbarcoTwoWireProtocol.STATUS_BUSY: PumpStatus.DISPENSING,
            GilbarcoTwoWireProtocol.STATUS_PEOT: PumpStatus.COMPLETE,
            GilbarcoTwoWireProtocol.STATUS_FEOT: PumpStatus.COMPLETE,
            GilbarcoTwoWireProtocol.STATUS_STOP: PumpStatus.STOPPED,
            GilbarcoTwoWireProtocol.STATUS_SEND_DATA: PumpStatus.ERROR,  # Special state
        }
        return status_map.get(status_code, PumpStatus.OFFLINE)
    
    @staticmethod
    def calculate_lrc(data: List[int]) -> int:
        """Calculate LRC checksum for data block"""
        lrc = 0
        for byte in data:
            lrc ^= byte
        return lrc & 0xF  # 4-bit LRC
    
    @staticmethod
    def parse_transaction_data(data_block: bytes) -> Optional[Dict]:
        """Parse transaction data block from pump response"""
        try:
            if len(data_block) < 10:  # Minimum expected length
                return None
            
            pos = 0
            result = {}
            
            # Should start with STX
            if data_block[pos] != GilbarcoTwoWireProtocol.DCW_STX:
                return None
            pos += 1
            
            # Parse each section based on DCW
            while pos < len(data_block):
                if pos >= len(data_block):
                    break
                    
                dcw = data_block[pos]
                pos += 1
                
                if dcw == GilbarcoTwoWireProtocol.DCW_ETX:
                    break
                elif dcw == GilbarcoTwoWireProtocol.DCW_PUMP_ID_NEXT:
                    # Next 5 bytes are pump ID data
                    if pos + 5 <= len(data_block):
                        result['pump_data'] = data_block[pos:pos+5]
                        pos += 5
                elif dcw == GilbarcoTwoWireProtocol.DCW_GRADE_NEXT:
                    # Next byte is grade
                    if pos < len(data_block):
                        result['grade'] = data_block[pos] & 0xF
                        pos += 1
                elif dcw == GilbarcoTwoWireProtocol.DCW_VOLUME_NEXT:
                    # Next 6 bytes are volume (BCD)
                    if pos + 6 <= len(data_block):
                        result['volume'] = GilbarcoTwoWireProtocol.parse_bcd_volume(data_block[pos:pos+6])
                        pos += 6
                elif dcw == GilbarcoTwoWireProtocol.DCW_MONEY_NEXT:
                    # Next 6 bytes are money (BCD)
                    if pos + 6 <= len(data_block):
                        result['money'] = GilbarcoTwoWireProtocol.parse_bcd_money(data_block[pos:pos+6])
                        pos += 6
                elif dcw == GilbarcoTwoWireProtocol.DCW_PPU_NEXT:
                    # Next 4 bytes are price per unit (BCD)
                    if pos + 4 <= len(data_block):
                        result['ppu'] = GilbarcoTwoWireProtocol.parse_bcd_ppu(data_block[pos:pos+4])
                        pos += 4
                else:
                    # Skip unknown DCW + 1 data byte
                    pos += 1
            
            return result
            
        except Exception:
            return None
    
    @staticmethod
    def parse_bcd_volume(bcd_bytes: bytes) -> float:
        """Parse BCD volume data (XXX.XXX format)"""
        # Convert BCD bytes to decimal, LSB first
        volume = 0
        for i, byte in enumerate(bcd_bytes):
            digit = byte & 0xF
            volume += digit * (10 ** i)
        return volume / 1000.0  # Convert to XXX.XXX format
    
    @staticmethod
    def parse_bcd_money(bcd_bytes: bytes) -> float:
        """Parse BCD money data"""
        money = 0
        for i, byte in enumerate(bcd_bytes):
            digit = byte & 0xF
            money += digit * (10 ** i)
        return money / 100.0  # Assume 2 decimal places
    
    @staticmethod
    def parse_bcd_ppu(bcd_bytes: bytes) -> float:
        """Parse BCD price per unit data"""
        ppu = 0
        for i, byte in enumerate(bcd_bytes):
            digit = byte & 0xF
            ppu += digit * (10 ** i)
        return ppu / 1000.0  # Assume 3 decimal places


# Legacy alias for compatibility
GilbarcoProtocol = GilbarcoTwoWireProtocol


class SerialConnection:
    """
    Manages serial connection to a pump using Gilbarco Two-Wire Protocol
    Note: Real two-wire uses current loop interface, this is RS232/485 adapter version
    """
    
    def __init__(self, com_port: str, baudrate: int = None, timeout: float = 0.068):
        self.com_port = com_port
        # Use standard two-wire baud rate, fallback to common rates
        self.baudrate = baudrate or GilbarcoTwoWireProtocol.BAUDRATE
        if self.baudrate == GilbarcoTwoWireProtocol.BAUDRATE:
            # Most adapters don't support 5787, use closest standard rate
            self.baudrate = 9600
        self.timeout = timeout
        self.connection: Optional[serial.Serial] = None
        self.is_connected = False
        self.lock = threading.Lock()
        self.logger = logging.getLogger(f"SerialConnection-{com_port}")
    
    def connect(self) -> bool:
        """Establish serial connection with two-wire protocol settings"""
        try:
            with self.lock:
                if self.connection and self.connection.is_open:
                    self.logger.debug(f"[{self.com_port}] Already connected")
                    return True
                
                self.logger.info(f"[{self.com_port}] Attempting to connect with Gilbarco Two-Wire Protocol settings")
                self.logger.debug(f"[{self.com_port}] Connection parameters:")
                self.logger.debug(f"  - Port: {self.com_port}")
                self.logger.debug(f"  - Baudrate: {self.baudrate}")
                self.logger.debug(f"  - Parity: {GilbarcoTwoWireProtocol.PARITY}")
                self.logger.debug(f"  - Timeout: {self.timeout}s")
                
                self.connection = serial.Serial(
                    port=self.com_port,
                    baudrate=self.baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=GilbarcoTwoWireProtocol.PARITY,  # Even parity for two-wire
                    stopbits=serial.STOPBITS_ONE,
                    timeout=self.timeout,
                    write_timeout=self.timeout
                )
                
                self.is_connected = True
                self.logger.info(f"[{self.com_port}] Successfully connected (two-wire protocol)")
                self.logger.debug(f"[{self.com_port}] Serial port settings verified:")
                self.logger.debug(f"  - Is Open: {self.connection.is_open}")
                self.logger.debug(f"  - In Waiting: {self.connection.in_waiting}")
                self.logger.debug(f"  - Out Waiting: {self.connection.out_waiting}")
                
                return True
                
        except serial.SerialException as e:
            self.logger.error(f"[{self.com_port}] Serial connection failed: {str(e)}")
            self.is_connected = False
            return False
        except Exception as e:
            self.logger.error(f"[{self.com_port}] Unexpected error during connection: {str(e)}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """Close serial connection"""
        try:
            with self.lock:
                if self.connection and self.connection.is_open:
                    self.logger.info(f"[{self.com_port}] Disconnecting from serial port")
                    
                    # Log final port statistics
                    try:
                        self.logger.debug(f"[{self.com_port}] Final port statistics:")
                        self.logger.debug(f"  - Bytes in buffer: {self.connection.in_waiting}")
                        self.logger.debug(f"  - Bytes out buffer: {self.connection.out_waiting}")
                    except:
                        pass
                    
                    self.connection.close()
                    self.logger.info(f"[{self.com_port}] Successfully disconnected")
                else:
                    self.logger.debug(f"[{self.com_port}] Already disconnected")
                    
                self.is_connected = False
                self.connection = None
                
        except serial.SerialException as e:
            self.logger.error(f"[{self.com_port}] Serial error during disconnect: {str(e)}")
        except Exception as e:
            self.logger.error(f"[{self.com_port}] Unexpected error during disconnect: {str(e)}")
        finally:
            self.is_connected = False
    
    def send_command(self, command: bytes, expect_response: bool = True) -> Optional[bytes]:
        """Send two-wire command and receive response"""
        if not self.is_connected:
            self.logger.info(f"Port {self.com_port} not connected, attempting to connect...")
            if not self.connect():
                self.logger.error(f"Failed to connect to {self.com_port} before sending command")
                return None
        
        try:
            with self.lock:
                if not self.connection or not self.connection.is_open:
                    self.logger.error(f"Serial connection {self.com_port} is not open")
                    return None
                
                # Log command details
                cmd_hex = command.hex().upper()
                self.logger.info(f"[{self.com_port}] Sending command: {cmd_hex} ({len(command)} bytes)")
                self.logger.debug(f"[{self.com_port}] Command breakdown: {' '.join([f'0x{b:02X}' for b in command])}")
                
                # Clear input buffer
                self.connection.reset_input_buffer()
                self.logger.debug(f"[{self.com_port}] Input buffer cleared")
                
                # Send command
                bytes_written = self.connection.write(command)
                self.connection.flush()
                self.logger.debug(f"[{self.com_port}] Wrote {bytes_written} bytes to serial port")
                
                if not expect_response:
                    self.logger.info(f"[{self.com_port}] Command sent successfully (no response expected)")
                    return b''
                
                # Wait for response with proper timing
                timeout_seconds = GilbarcoTwoWireProtocol.TIMEOUT_MS / 1000.0
                self.logger.debug(f"[{self.com_port}] Waiting {timeout_seconds}s for response...")
                time.sleep(timeout_seconds)
                
                # Read response (typically 1 byte for status)
                response = self.connection.read(1)
                
                if response:
                    resp_hex = response.hex().upper()
                    self.logger.info(f"[{self.com_port}] Received response: {resp_hex} ({len(response)} bytes)")
                    self.logger.debug(f"[{self.com_port}] Response breakdown: {' '.join([f'0x{b:02X}' for b in response])}")
                    
                    # Decode response for logging
                    if len(response) == 1:
                        word = response[0]
                        status = (word >> 4) & 0xF
                        pump_nibble = word & 0xF
                        self.logger.debug(f"[{self.com_port}] Decoded: Status=0x{status:X}, Pump={pump_nibble:X}")
                    
                    return response
                else:
                    self.logger.warning(f"[{self.com_port}] No response received to command: {cmd_hex}")
                    return None
                    
        except serial.SerialException as e:
            self.logger.error(f"[{self.com_port}] Serial communication error: {str(e)}")
            self.is_connected = False
            return None
        except Exception as e:
            self.logger.error(f"[{self.com_port}] Unexpected error during communication: {str(e)}")
            self.is_connected = False
            return None
    
    def send_command_with_data_response(self, command: bytes, max_response_length: int = 50) -> Optional[bytes]:
        """Send command expecting a data block response (transaction data, totals, etc.)"""
        if not self.is_connected:
            self.logger.info(f"Port {self.com_port} not connected, attempting to connect...")
            if not self.connect():
                self.logger.error(f"Failed to connect to {self.com_port} before sending data command")
                return None
        
        try:
            with self.lock:
                if not self.connection or not self.connection.is_open:
                    self.logger.error(f"Serial connection {self.com_port} is not open")
                    return None
                
                # Log command details
                cmd_hex = command.hex().upper()
                self.logger.info(f"[{self.com_port}] Sending data request command: {cmd_hex}")
                self.logger.debug(f"[{self.com_port}] Expecting data block response (max {max_response_length} bytes)")
                
                # Clear input buffer
                self.connection.reset_input_buffer()
                self.logger.debug(f"[{self.com_port}] Input buffer cleared")
                
                # Send command
                bytes_written = self.connection.write(command)
                self.connection.flush()
                self.logger.debug(f"[{self.com_port}] Wrote {bytes_written} bytes to serial port")
                
                # Wait for response
                timeout_seconds = GilbarcoTwoWireProtocol.TIMEOUT_MS / 1000.0
                time.sleep(timeout_seconds)
                
                # Read response data block
                response = b''
                start_time = time.time()
                bytes_read = 0
                
                self.logger.debug(f"[{self.com_port}] Starting data block read...")
                
                while len(response) < max_response_length and (time.time() - start_time) < 1.0:
                    chunk = self.connection.read(1)
                    if chunk:
                        response += chunk
                        bytes_read += 1
                        self.logger.debug(f"[{self.com_port}] Read byte {bytes_read}: 0x{chunk[0]:02X}")
                        
                        # Check for ETX (end of data block)
                        if chunk[0] == GilbarcoTwoWireProtocol.DCW_ETX:
                            self.logger.debug(f"[{self.com_port}] Found ETX, data block complete")
                            break
                    else:
                        # Small delay between reads
                        time.sleep(0.001)
                
                if response:
                    resp_hex = response.hex().upper()
                    self.logger.info(f"[{self.com_port}] Received data block: {resp_hex} ({len(response)} bytes)")
                    self.logger.debug(f"[{self.com_port}] Data block breakdown: {' '.join([f'0x{b:02X}' for b in response])}")
                    
                    # Log data block structure
                    self._log_data_block_structure(response)
                    
                    return response
                else:
                    self.logger.warning(f"[{self.com_port}] No data block response to command: {cmd_hex}")
                    return None
                    
        except serial.SerialException as e:
            self.logger.error(f"[{self.com_port}] Serial communication error during data transfer: {str(e)}")
            self.is_connected = False
            return None
        except Exception as e:
            self.logger.error(f"[{self.com_port}] Unexpected error during data communication: {str(e)}")
            self.is_connected = False
            return None

    def _log_data_block_structure(self, data_block: bytes):
        """Log the structure of a received data block for debugging"""
        if not data_block:
            return
            
        self.logger.debug(f"[{self.com_port}] === Data Block Analysis ===")
        pos = 0
        
        for i, byte in enumerate(data_block):
            dcw_name = "UNKNOWN"
            if byte == GilbarcoTwoWireProtocol.DCW_STX:
                dcw_name = "STX (Start of Text)"
            elif byte == GilbarcoTwoWireProtocol.DCW_ETX:
                dcw_name = "ETX (End of Text)"
            elif byte == GilbarcoTwoWireProtocol.DCW_LRC_NEXT:
                dcw_name = "LRC_NEXT"
            elif byte == GilbarcoTwoWireProtocol.DCW_PUMP_ID_NEXT:
                dcw_name = "PUMP_ID_NEXT"
            elif byte == GilbarcoTwoWireProtocol.DCW_GRADE_NEXT:
                dcw_name = "GRADE_NEXT"
            elif byte == GilbarcoTwoWireProtocol.DCW_PPU_NEXT:
                dcw_name = "PPU_NEXT"
            elif byte == GilbarcoTwoWireProtocol.DCW_VOLUME_NEXT:
                dcw_name = "VOLUME_NEXT"
            elif byte == GilbarcoTwoWireProtocol.DCW_MONEY_NEXT:
                dcw_name = "MONEY_NEXT"
            elif (byte & 0xF0) == 0xF0:
                dcw_name = f"DCW (0xF{byte & 0x0F:X})"
            elif (byte & 0xF0) == 0xE0:
                dcw_name = f"DATA (0xE{byte & 0x0F:X})"
            
            self.logger.debug(f"[{self.com_port}] Byte {i:2d}: 0x{byte:02X} = {dcw_name}")
        
        self.logger.debug(f"[{self.com_port}] === End Data Block Analysis ===")


class PumpController:
    """Controls a single pump"""
    
    def __init__(self, pump_info: PumpInfo):
        self.pump_info = pump_info
        self.connection = SerialConnection(pump_info.com_port)
        self.last_status = PumpStatus.OFFLINE
        self.last_status_update = datetime.now()
        self.logger = logging.getLogger(f"PumpController-{pump_info.pump_id}")
    
    def connect(self) -> bool:
        """Connect to pump"""
        connected = self.connection.connect()
        self.pump_info.is_connected = connected
        return connected
    
    def disconnect(self):
        """Disconnect from pump"""
        self.connection.disconnect()
        self.pump_info.is_connected = False
        self.last_status = PumpStatus.OFFLINE
    
    def get_status(self) -> PumpStatusResponse:
        """Get current pump status using two-wire protocol"""
        try:
            self.logger.info(f"Requesting status for pump {self.pump_info.pump_id} (address {self.pump_info.address})")
            
            # Build status command using two-wire protocol
            command = GilbarcoTwoWireProtocol.build_status_command(self.pump_info.address)
            self.logger.debug(f"Built status command for pump {self.pump_info.address}: {command.hex().upper()}")
            
            # Send command
            response = self.connection.send_command(command)
            
            if response and len(response) >= 1:
                try:
                    pump_id, status_code = GilbarcoTwoWireProtocol.parse_status_response(response)
                    self.logger.debug(f"Parsed status response: pump_id={pump_id}, status_code=0x{status_code:X}")
                    
                    # Verify pump ID matches
                    if pump_id != self.pump_info.address:
                        self.logger.warning(f"Pump ID mismatch: expected {self.pump_info.address}, got {pump_id}")
                    
                    # Convert status code to enum
                    status = GilbarcoTwoWireProtocol.status_code_to_enum(status_code)
                    self.logger.info(f"Pump {self.pump_info.pump_id} status: {status.value} (code 0x{status_code:X})")
                    
                    self.last_status = status
                    self.last_status_update = datetime.now()
                    
                    return PumpStatusResponse(
                        pump_id=self.pump_info.pump_id,
                        status=status,
                        last_updated=self.last_status_update,
                        error_message=None if status != PumpStatus.ERROR else f"Data error (code {status_code:X})"
                    )
                    
                except ValueError as e:
                    self.logger.error(f"Invalid status response for pump {self.pump_info.pump_id}: {str(e)}")
                    self.last_status = PumpStatus.ERROR
                    return PumpStatusResponse(
                        pump_id=self.pump_info.pump_id,
                        status=PumpStatus.ERROR,
                        last_updated=datetime.now(),
                        error_message=f"Invalid response: {str(e)}"
                    )
            
            # No response or invalid response
            self.logger.warning(f"No valid response from pump {self.pump_info.pump_id}")
            self.last_status = PumpStatus.OFFLINE
            return PumpStatusResponse(
                pump_id=self.pump_info.pump_id,
                status=PumpStatus.OFFLINE,
                last_updated=datetime.now(),
                error_message="No response from pump"
            )
            
        except Exception as e:
            self.logger.error(f"Error getting status for pump {self.pump_info.pump_id}: {str(e)}", exc_info=True)
            self.last_status = PumpStatus.ERROR
            return PumpStatusResponse(
                pump_id=self.pump_info.pump_id,
                status=PumpStatus.ERROR,
                last_updated=datetime.now(),
                error_message=str(e)
            )
    
    def get_transaction_data(self) -> Optional[TransactionData]:
        """Get transaction data from pump using two-wire protocol"""
        try:
            self.logger.info(f"Requesting transaction data for pump {self.pump_info.pump_id}")
            
            # Build transaction request command
            command = GilbarcoTwoWireProtocol.build_transaction_request(self.pump_info.address)
            self.logger.debug(f"Built transaction request for pump {self.pump_info.address}: {command.hex().upper()}")
            
            # Send command and expect data block response
            response = self.connection.send_command_with_data_response(command)
            
            if response:
                self.logger.info(f"Received transaction data block from pump {self.pump_info.pump_id}")
                
                # Parse transaction data block
                transaction_data = GilbarcoTwoWireProtocol.parse_transaction_data(response)
                
                if transaction_data:
                    self.logger.info(f"Successfully parsed transaction data for pump {self.pump_info.pump_id}:")
                    self.logger.info(f"  - Volume: {transaction_data.get('volume')}")
                    self.logger.info(f"  - PPU: {transaction_data.get('ppu')}")
                    self.logger.info(f"  - Money: {transaction_data.get('money')}")
                    self.logger.info(f"  - Grade: {transaction_data.get('grade')}")
                    
                    return TransactionData(
                        pump_id=self.pump_info.pump_id,
                        volume=transaction_data.get('volume'),
                        price_per_unit=transaction_data.get('ppu'),
                        total_amount=transaction_data.get('money'),
                        grade=transaction_data.get('grade'),
                        timestamp=datetime.now()
                    )
                else:
                    self.logger.warning(f"Failed to parse transaction data for pump {self.pump_info.pump_id}")
            else:
                self.logger.warning(f"No transaction data response from pump {self.pump_info.pump_id}")
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting transaction data for pump {self.pump_info.pump_id}: {str(e)}", exc_info=True)
            return None
    
    def authorize_pump(self) -> bool:
        """Authorize pump for dispensing"""
        try:
            self.logger.info(f"Authorizing pump {self.pump_info.pump_id} (address {self.pump_info.address})")
            
            command = GilbarcoTwoWireProtocol.build_authorize_command(self.pump_info.address)
            self.logger.debug(f"Built authorize command: {command.hex().upper()}")
            
            # Authorization is a single word command with no response
            self.connection.send_command(command, expect_response=False)
            self.logger.info(f"Authorize command sent to pump {self.pump_info.pump_id}")
            
            # Wait a moment then check status to verify authorization
            time.sleep(0.1)
            self.logger.debug(f"Checking status after authorization for pump {self.pump_info.pump_id}")
            status_response = self.get_status()
            
            authorized = status_response.status in [PumpStatus.AUTHORIZED, PumpStatus.DISPENSING]
            
            if authorized:
                self.logger.info(f"Pump {self.pump_info.pump_id} successfully authorized (status: {status_response.status.value})")
            else:
                self.logger.warning(f"Pump {self.pump_info.pump_id} authorization may have failed (status: {status_response.status.value})")
            
            return authorized
            
        except Exception as e:
            self.logger.error(f"Error authorizing pump {self.pump_info.pump_id}: {str(e)}", exc_info=True)
            return False
    
    def stop_pump(self) -> bool:
        """Stop pump dispensing"""
        try:
            self.logger.info(f"Stopping pump {self.pump_info.pump_id} (address {self.pump_info.address})")
            
            command = GilbarcoTwoWireProtocol.build_stop_command(self.pump_info.address)
            self.logger.debug(f"Built stop command: {command.hex().upper()}")
            
            # Stop is a single word command with no response  
            self.connection.send_command(command, expect_response=False)
            self.logger.info(f"Stop command sent to pump {self.pump_info.pump_id}")
            
            # Wait a moment then check status to verify stop
            time.sleep(0.1)
            self.logger.debug(f"Checking status after stop for pump {self.pump_info.pump_id}")
            status_response = self.get_status()
            
            stopped = status_response.status in [PumpStatus.STOPPED, PumpStatus.IDLE]
            
            if stopped:
                self.logger.info(f"Pump {self.pump_info.pump_id} successfully stopped (status: {status_response.status.value})")
            else:
                self.logger.warning(f"Pump {self.pump_info.pump_id} stop may have failed (status: {status_response.status.value})")
            
            return stopped
            
        except Exception as e:
            self.logger.error(f"Error stopping pump {self.pump_info.pump_id}: {str(e)}", exc_info=True)
            return False
