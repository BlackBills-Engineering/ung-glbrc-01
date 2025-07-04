#!/usr/bin/env python3
"""
Gilbarco Frame Decoder
Decodes pump communication frames using the Gilbarco Two-Wire Protocol
"""

import sys
from typing import Dict
from pump_controller import GilbarcoTwoWireProtocol


def hex_string_to_bytes(hex_string: str) -> bytes:
    """Convert hex string to bytes"""
    # Remove spaces and convert to bytes
    hex_clean = hex_string.replace(" ", "").replace("\n", "")
    return bytes.fromhex(hex_clean)


def decode_frame(frame_bytes: bytes) -> Dict:
    """Decode a Gilbarco frame"""
    result = {
        "raw_hex": frame_bytes.hex().upper(),
        "length": len(frame_bytes),
        "decoded_data": {},
        "errors": [],
    }

    print(f"=== Decoding Gilbarco Frame ===")
    print(f"Raw frame: {result['raw_hex']}")
    print(f"Length: {result['length']} bytes")
    print()

    # Try to identify frame type
    if len(frame_bytes) == 0:
        result["errors"].append("Empty frame")
        return result

    # Check if it's a simple status response (1 byte)
    if len(frame_bytes) == 1:
        try:
            pump_id, status = GilbarcoTwoWireProtocol.parse_status_response(frame_bytes)
            result["decoded_data"] = {
                "type": "status_response",
                "pump_id": pump_id,
                "status_code": status,
                "status_name": GilbarcoTwoWireProtocol.status_code_to_enum(
                    status
                ).value,
            }
            print(f"Status Response:")
            print(f"  Pump ID: {pump_id}")
            print(f"  Status Code: 0x{status:X}")
            print(f"  Status: {result['decoded_data']['status_name']}")
            return result
        except Exception as e:
            result["errors"].append(f"Failed to parse as status response: {e}")

    # Check if it starts with STX (0xFF) - transaction data
    if frame_bytes[0] == GilbarcoTwoWireProtocol.DCW_STX:
        print("Detected transaction data frame (starts with STX 0xFF)")
        try:
            transaction_data = GilbarcoTwoWireProtocol.parse_transaction_data(
                frame_bytes
            )
            if transaction_data:
                result["decoded_data"] = {
                    "type": "transaction_data",
                    **transaction_data,
                }
                print(f"Transaction Data:")
                for key, value in transaction_data.items():
                    print(f"  {key}: {value}")
                return result
            else:
                result["errors"].append("Failed to parse transaction data")
        except Exception as e:
            result["errors"].append(f"Transaction data parsing error: {e}")

    # Manual parsing of the frame structure
    print("Attempting manual frame analysis...")

    pos = 0
    while pos < len(frame_bytes):
        byte = frame_bytes[pos]

        # Check for Data Control Words (DCW)
        if byte == GilbarcoTwoWireProtocol.DCW_STX:
            print(f"Byte {pos:2d} (0x{byte:02X}): STX - Start of Text")
        elif byte == GilbarcoTwoWireProtocol.DCW_ETX:
            print(f"Byte {pos:2d} (0x{byte:02X}): ETX - End of Text")
        elif byte == GilbarcoTwoWireProtocol.DCW_LRC_NEXT:
            print(f"Byte {pos:2d} (0x{byte:02X}): LRC - LRC Check Character Next")
        elif byte == GilbarcoTwoWireProtocol.DCW_PUMP_ID_NEXT:
            print(f"Byte {pos:2d} (0x{byte:02X}): PUMP_ID - Pump Identifier Next")
        elif byte == GilbarcoTwoWireProtocol.DCW_GRADE_NEXT:
            print(f"Byte {pos:2d} (0x{byte:02X}): GRADE - Grade Data Next")
        elif byte == GilbarcoTwoWireProtocol.DCW_PPU_NEXT:
            print(f"Byte {pos:2d} (0x{byte:02X}): PPU - Price Per Unit Next")
        elif byte == GilbarcoTwoWireProtocol.DCW_VOLUME_NEXT:
            print(f"Byte {pos:2d} (0x{byte:02X}): VOLUME - Volume Data Next")
        elif byte == GilbarcoTwoWireProtocol.DCW_MONEY_NEXT:
            print(f"Byte {pos:2d} (0x{byte:02X}): MONEY - Money Data Next")
        else:
            # Try to interpret as data
            if 0xE0 <= byte <= 0xEF:
                print(f"Byte {pos:2d} (0x{byte:02X}): DATA - BCD digit {byte & 0xF}")
            elif 0xF0 <= byte <= 0xFF:
                print(f"Byte {pos:2d} (0x{byte:02X}): DCW/CONTROL - {byte & 0xF}")
            else:
                print(f"Byte {pos:2d} (0x{byte:02X}): UNKNOWN - Raw data")

        pos += 1

    # Try to extract BCD data sequences
    print("\n=== BCD Data Analysis ===")
    bcd_sequences = []
    current_sequence = []

    for i, byte in enumerate(frame_bytes):
        if 0xE0 <= byte <= 0xEF:  # BCD data
            current_sequence.append((i, byte & 0xF))
        else:
            if current_sequence:
                bcd_sequences.append(current_sequence)
                current_sequence = []

    if current_sequence:
        bcd_sequences.append(current_sequence)

    for i, seq in enumerate(bcd_sequences):
        positions = [pos for pos, _ in seq]
        digits = [digit for _, digit in seq]
        print(f"BCD Sequence {i+1} (positions {positions}): {digits}")

        # Try to interpret as different data types
        if len(digits) == 6:
            # Could be volume or money
            value = 0
            for j, digit in enumerate(digits):
                value += digit * (10**j)
            print(f"  As volume: {value/1000.0:.3f}")
            print(f"  As money: {value/100.0:.2f}")
        elif len(digits) == 4:
            # Could be PPU
            value = 0
            for j, digit in enumerate(digits):
                value += digit * (10**j)
            print(f"  As PPU: {value/1000.0:.3f}")
        elif len(digits) == 5:
            # Could be pump ID data
            print(f"  As pump ID data: {digits}")

    return result


def main():
    """Main function"""
    frame_hex = "ff f1 f8 eb e3 e0 e0 e2 f6 e0 f4 f7 e0 e5 e1 e8 f9 e0 e7 e2 e1 e0 fa e0 e0 e0 e0 e1 fb ee f0"

    print("Gilbarco Frame Decoder")
    print("=" * 50)

    try:
        frame_bytes = hex_string_to_bytes(frame_hex)
        result = decode_frame(frame_bytes)

        if result["errors"]:
            print("\nErrors encountered:")
            for error in result["errors"]:
                print(f"  - {error}")

        print("\nDecoding complete!")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
