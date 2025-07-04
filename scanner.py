#!/usr/bin/env python3

import serial
import time
import logging
from enum import Enum
from typing import Tuple

COM_PORT = "COM3"
BAUDRATE = 5787
TIMEOUT = 1.0
ADDRESS_RANGE = (1, 16)

CMD_STATUS = 0x0  # Status request command code
STATUS_CODES = {
    0x0: "DATA_ERROR",
    0x6: "OFF",
    0x7: "CALL",
    0x8: "AUTHORIZED",
    0x9: "BUSY",
    0xA: "PEOT",
    0xB: "FEOT",
    0xC: "STOP",
}


class PumpStatus(Enum):
    """Pump status enumeration"""

    DATA_ERROR = "DATA_ERROR"
    OFF = "OFF"
    CALL = "CALL"
    AUTHORIZED = "AUTHORIZED"
    BUSY = "BUSY"
    PEOT = "PEOT"
    FEOT = "FEOT"
    STOP = "STOP"
    OFFLINE = "OFFLINE"


def setup_logging():
    """Setup detailed logging"""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/pump_scanner.log", mode="w"),
        ],
    )
    return logging.getLogger("PumpScanner")


def pump_id_to_nibble(pump_id: int) -> int:
    """Convert pump ID (1-16) to nibble (1-15, 0)"""
    if pump_id == 16:
        return 0
    elif 1 <= pump_id <= 15:
        return pump_id
    else:
        raise ValueError(f"Invalid pump ID: {pump_id}")


def nibble_to_pump_id(nibble: int) -> int:
    """Convert nibble (1-15, 0) to pump ID (1-16)"""
    if nibble == 0:
        return 16
    elif 1 <= nibble <= 15:
        return nibble
    else:
        raise ValueError(f"Invalid pump nibble: {nibble}")


def build_status_command(pump_id: int) -> bytes:
    """Build status poll command: '0' '<p>'"""
    pump_nibble = pump_id_to_nibble(pump_id)
    command = (CMD_STATUS << 4) | pump_nibble
    return bytes([command])


def parse_status_response(response: bytes) -> Tuple[int, int]:
    """Parse status response to get pump ID and status"""
    if len(response) != 1:
        raise ValueError("Invalid status response length")

    word = response[0]
    status = (word >> 4) & 0xF
    pump_nibble = word & 0xF
    pump_id = nibble_to_pump_id(pump_nibble)

    return pump_id, status


def status_code_to_enum(status_code: int) -> PumpStatus:
    """Convert status code to PumpStatus enum"""
    status_map = {
        0x0: PumpStatus.DATA_ERROR,
        0x6: PumpStatus.OFF,
        0x7: PumpStatus.CALL,
        0x8: PumpStatus.AUTHORIZED,
        0x9: PumpStatus.BUSY,
        0xA: PumpStatus.PEOT,
        0xB: PumpStatus.FEOT,
        0xC: PumpStatus.STOP,
    }
    return status_map.get(status_code, PumpStatus.OFFLINE)


def format_hex_bytes(data: bytes) -> str:
    """Format bytes as hex string for logging"""
    return " ".join(f"{b:02X}" for b in data)


def main():
    """Main scanner function"""
    logger = setup_logging()

    logger.info("=" * 60)
    logger.info("Gilbarco SK700-II Standalone Pump Scanner")
    logger.info("=" * 60)
    logger.info(f"COM Port: {COM_PORT}")
    logger.info(f"Baudrate: {BAUDRATE}")
    logger.info(f"Timeout: {TIMEOUT}s")
    logger.info(f"Address Range: {ADDRESS_RANGE[0]} to {ADDRESS_RANGE[1]}")
    logger.info("=" * 60)

    try:
        logger.info(f"Opening serial port {COM_PORT}...")
        ser = serial.Serial(
            port=COM_PORT,
            baudrate=BAUDRATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE,
            timeout=TIMEOUT,
        )
        logger.info(f"✓ Successfully opened {COM_PORT}")
        logger.info(
            f"  Port settings: {ser.baudrate} baud, {ser.bytesize} data bits, {ser.parity} parity, {ser.stopbits} stop bits"
        )

    except Exception as e:
        logger.error(f"✗ Failed to open COM port {COM_PORT}: {e}")
        return

    discovered_pumps = []

    try:
        for pump_address in range(ADDRESS_RANGE[0], ADDRESS_RANGE[1] + 1):
            logger.info(f"\n--- Testing Pump Address {pump_address} ---")

            command = build_status_command(pump_address)
            logger.info(f"Built status command: 0x{format_hex_bytes(command)}")
            logger.debug(
                f"Command breakdown: CMD=0x{CMD_STATUS:X} (STATUS), PUMP_ID={pump_address}"
            )

            logger.info(f"Sending status command to pump {pump_address}...")
            ser.write(command)
            ser.flush()
            logger.debug(f"TX: {format_hex_bytes(command)}")

            time.sleep(0.1)  # Small delay as per protocol

            try:
                response = ser.read(1)  # Expect 1 byte response

                if response:
                    logger.debug(f"RX: {format_hex_bytes(response)}")

                    try:
                        response_pump_id, status_code = parse_status_response(response)
                        status = status_code_to_enum(status_code)

                        logger.info(f"✓ Response received from pump {response_pump_id}")
                        logger.info(
                            f"  Status Code: 0x{status_code:X} ({STATUS_CODES.get(status_code, 'UNKNOWN')})"
                        )
                        logger.info(f"  Status: {status.value}")

                        if response_pump_id == pump_address:
                            logger.info(f"✓ Pump ID matches request")
                            if status != PumpStatus.OFFLINE:
                                discovered_pumps.append(
                                    {
                                        "address": pump_address,
                                        "status": status,
                                        "status_code": status_code,
                                        "response_raw": response,
                                    }
                                )
                                logger.info(
                                    f"✓ Pump {pump_address} added to discovered list"
                                )
                            else:
                                logger.info(f"  Pump {pump_address} is offline")
                        else:
                            logger.warning(
                                f"⚠ Pump ID mismatch: expected {pump_address}, got {response_pump_id}"
                            )

                    except Exception as e:
                        logger.error(f"✗ Failed to parse response: {e}")
                        logger.error(f"  Raw response: {format_hex_bytes(response)}")

                else:
                    logger.info(f"  No response from pump {pump_address}")

            except Exception as e:
                logger.error(f"✗ Error reading response: {e}")

            ser.reset_input_buffer()
            time.sleep(0.05)

    finally:
        logger.info(f"\nClosing serial port...")
        ser.close()
        logger.info(f"✓ Serial port closed")

    logger.info("\n" + "=" * 60)
    logger.info("SCAN SUMMARY")
    logger.info("=" * 60)
    logger.info(f"COM Port: {COM_PORT}")
    logger.info(
        f"Addresses scanned: {ADDRESS_RANGE[0]}-{ADDRESS_RANGE[1]} ({ADDRESS_RANGE[1] - ADDRESS_RANGE[0] + 1} addresses)"
    )
    logger.info(f"Pumps discovered: {len(discovered_pumps)}")

    if discovered_pumps:
        logger.info("\nDiscovered Pumps:")
        for pump in discovered_pumps:
            logger.info(
                f"  Address {pump['address']}: {pump['status'].value} (0x{pump['status_code']:02X})"
            )
    else:
        logger.info("No pumps discovered")

    logger.info("=" * 60)
    logger.info("Scan complete!")


if __name__ == "__main__":
    main()
