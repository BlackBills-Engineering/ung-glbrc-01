#!/usr/bin/env python3
"""
Decode Gilbarco Two-Wire Protocol Transaction Frame

This script decodes the given transaction frame according to the protocol specification.
"""


def decode_transaction_frame():
    # Raw frame data
    frame_hex = "FFF1F8EBE1E0E0E2F6E2F4F7E0E7E0E1F9E0E6E3E3E2E0FAE0E0E0E5E2E0FBECF0"

    print("=" * 60)
    print("Gilbarco Two-Wire Protocol Frame Decoder")
    print("=" * 60)
    print(f"Raw Frame: {frame_hex}")
    print(f"Frame Length: {len(frame_hex)} hex characters ({len(frame_hex)//2} bytes)")
    print()

    # Convert to bytes
    frame_bytes = bytes.fromhex(frame_hex)

    print("Byte-by-byte breakdown:")
    print("-" * 40)

    pos = 0
    for i, byte in enumerate(frame_bytes):
        print(f"Byte {i:2d}: 0x{byte:02X}")

    print()
    print("Protocol Analysis:")
    print("-" * 40)

    pos = 0

    # Parse according to Two-Wire Protocol
    while pos < len(frame_bytes):
        byte = frame_bytes[pos]

        if byte == 0xFF:
            if pos + 1 < len(frame_bytes) and frame_bytes[pos + 1] == 0xF1:
                print(
                    f"Pos {pos:2d}-{pos+1:2d}: 0xFF 0xF1 = STX (Start of Text) - Extended format"
                )
                pos += 2
            else:
                print(f"Pos {pos:2d}: 0x{byte:02X} = STX (Start of Text)")
                pos += 1
        elif byte == 0xF0:
            print(f"Pos {pos:2d}: 0x{byte:02X} = ETX (End of Text)")
            pos += 1
        elif byte == 0xF8:
            print(f"Pos {pos:2d}: 0x{byte:02X} = DCW - Pump ID data follows")
            pos += 1
            # Next 5 bytes are pump ID data
            if pos + 4 < len(frame_bytes):
                pump_data = frame_bytes[pos : pos + 5]
                print(
                    f"Pos {pos:2d}-{pos+4:2d}: Pump ID Data = {' '.join([f'0x{b:02X}' for b in pump_data])}"
                )

                # Decode pump info
                error_code = pump_data[0] & 0x0F  # EB -> 0x0B
                pump_number = pump_data[1] & 0x0F  # E0 -> 0x00
                error_status1 = pump_data[2] & 0x0F  # E0 -> 0x00
                error_status2 = pump_data[3] & 0x0F  # E0 -> 0x00
                error_status3 = pump_data[4] & 0x0F  # E2 -> 0x02

                print(f"    - Error Code: 0x{error_code:X}")
                print(f"    - Pump Number: {pump_number}")
                print(f"    - Error Status 1: 0x{error_status1:X}")
                print(f"    - Error Status 2: 0x{error_status2:X}")
                print(f"    - Error Status 3: 0x{error_status3:X}")
                pos += 5
        elif byte == 0xF6:
            print(f"Pos {pos:2d}: 0x{byte:02X} = DCW - Grade data follows")
            pos += 1
            if pos < len(frame_bytes):
                grade_byte = frame_bytes[pos]
                grade = grade_byte & 0x0F
                print(f"Pos {pos:2d}: 0x{grade_byte:02X} = Grade {grade}")
                pos += 1
        elif byte == 0xF4:
            print(f"Pos {pos:2d}: 0x{byte:02X} = DCW - Unknown/Reserved data follows")
            pos += 1
        elif byte == 0xF7:
            print(
                f"Pos {pos:2d}: 0x{byte:02X} = DCW - Price Per Unit (PPU) data follows"
            )
            pos += 1
            # Next 4 bytes are PPU in BCD
            if pos + 3 < len(frame_bytes):
                ppu_data = frame_bytes[pos : pos + 4]
                print(
                    f"Pos {pos:2d}-{pos+3:2d}: PPU Data = {' '.join([f'0x{b:02X}' for b in ppu_data])}"
                )

                # Decode BCD PPU (least significant digit first)
                ppu_value = 0
                for i, ppu_byte in enumerate(ppu_data):
                    digit = ppu_byte & 0x0F
                    ppu_value += digit * (10**i)
                ppu_decimal = ppu_value / 1000.0  # Assume 3 decimal places

                print(f"    - PPU (BCD): {ppu_value} -> ${ppu_decimal:.3f}")
                pos += 4
        elif byte == 0xF9:
            print(f"Pos {pos:2d}: 0x{byte:02X} = DCW - Volume data follows")
            pos += 1
            # Next 6 bytes are volume in BCD
            if pos + 5 < len(frame_bytes):
                volume_data = frame_bytes[pos : pos + 6]
                print(
                    f"Pos {pos:2d}-{pos+5:2d}: Volume Data = {' '.join([f'0x{b:02X}' for b in volume_data])}"
                )

                # Decode BCD Volume (least significant digit first)
                volume_value = 0
                for i, vol_byte in enumerate(volume_data):
                    digit = vol_byte & 0x0F
                    volume_value += digit * (10**i)
                volume_decimal = volume_value / 1000.0  # Convert to XXX.XXX format

                print(
                    f"    - Volume (BCD): {volume_value} -> {volume_decimal:.3f} gallons"
                )
                pos += 6
        elif byte == 0xFA:
            print(f"Pos {pos:2d}: 0x{byte:02X} = DCW - Money/Total amount data follows")
            pos += 1
            # Next 6 bytes are money in BCD
            if pos + 5 < len(frame_bytes):
                money_data = frame_bytes[pos : pos + 6]
                print(
                    f"Pos {pos:2d}-{pos+5:2d}: Money Data = {' '.join([f'0x{b:02X}' for b in money_data])}"
                )

                # Decode BCD Money (least significant digit first)
                money_value = 0
                for i, money_byte in enumerate(money_data):
                    digit = money_byte & 0x0F
                    money_value += digit * (10**i)
                money_decimal = money_value / 100.0  # Assume 2 decimal places

                print(f"    - Money (BCD): {money_value} -> ${money_decimal:.2f}")
                pos += 6
        elif byte == 0xFB:
            print(f"Pos {pos:2d}: 0x{byte:02X} = DCW - LRC checksum follows")
            pos += 1
            if pos < len(frame_bytes):
                lrc_byte = frame_bytes[pos]
                lrc = lrc_byte & 0x0F
                print(f"Pos {pos:2d}: 0x{lrc_byte:02X} = LRC Checksum: 0x{lrc:X}")
                pos += 1
        elif (byte & 0xF0) == 0xE0:
            # Data byte
            data_value = byte & 0x0F
            print(f"Pos {pos:2d}: 0x{byte:02X} = Data byte, value: 0x{data_value:X}")
            pos += 1
        else:
            print(f"Pos {pos:2d}: 0x{byte:02X} = Unknown/Unexpected byte")
            pos += 1

    print()
    print("Summary:")
    print("-" * 40)
    print("This appears to be a transaction data response containing:")
    print("- Pump identification and error status")
    print("- Grade selection")
    print("- Price per unit (PPU)")
    print("- Volume dispensed")
    print("- Total money amount")
    print("- LRC checksum for data integrity")
    print()
    print("The frame follows the Gilbarco Two-Wire Protocol format for")
    print("transaction data (Command 4 response) with BCD encoded values.")


if __name__ == "__main__":
    decode_transaction_frame()
