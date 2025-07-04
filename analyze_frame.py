#!/usr/bin/env python3
"""
Detailed Frame Analysis for the specific frame received
"""


def analyze_specific_frame():
    """Analyze the specific frame in detail"""

    frame_hex = "ff f1 f8 eb e3 e0 e0 e2 f6 e0 f4 f7 e0 e5 e1 e8 f9 e0 e7 e2 e1 e0 fa e0 e0 e0 e0 e1 fb ee f0"
    frame_bytes = bytes.fromhex(frame_hex.replace(" ", ""))

    print("=== Detailed Gilbarco Frame Analysis ===")
    print(f"Frame: {frame_hex}")
    print(f"Length: {len(frame_bytes)} bytes")
    print()

    pos = 0
    print("Byte-by-byte analysis:")

    while pos < len(frame_bytes):
        byte = frame_bytes[pos]

        if pos == 0:  # FF
            print(f"Byte {pos:2d}: 0x{byte:02X} - STX (Start of Text)")
        elif pos == 1:  # F1
            print(f"Byte {pos:2d}: 0x{byte:02X} - Unknown control/status")
        elif pos == 2:  # F8
            print(
                f"Byte {pos:2d}: 0x{byte:02X} - PUMP_ID_NEXT (Pump identifier data follows)"
            )
        elif pos == 3:  # EB
            print(f"Byte {pos:2d}: 0x{byte:02X} - Pump data byte 1 (BCD: {byte & 0xF})")
        elif pos == 4:  # E3
            print(f"Byte {pos:2d}: 0x{byte:02X} - Pump data byte 2 (BCD: {byte & 0xF})")
        elif pos == 5:  # E0
            print(f"Byte {pos:2d}: 0x{byte:02X} - Pump data byte 3 (BCD: {byte & 0xF})")
        elif pos == 6:  # E0
            print(f"Byte {pos:2d}: 0x{byte:02X} - Pump data byte 4 (BCD: {byte & 0xF})")
        elif pos == 7:  # E2
            print(f"Byte {pos:2d}: 0x{byte:02X} - Pump data byte 5 (BCD: {byte & 0xF})")
        elif pos == 8:  # F6
            print(f"Byte {pos:2d}: 0x{byte:02X} - GRADE_NEXT (Grade data follows)")
        elif pos == 9:  # E0
            print(
                f"Byte {pos:2d}: 0x{byte:02X} - Grade data (BCD: {byte & 0xF} = Grade 0)"
            )
        elif pos == 10:  # F4
            print(f"Byte {pos:2d}: 0x{byte:02X} - Unknown control")
        elif pos == 11:  # F7
            print(
                f"Byte {pos:2d}: 0x{byte:02X} - PPU_NEXT (Price Per Unit data follows)"
            )
        elif pos == 12:  # E0
            print(f"Byte {pos:2d}: 0x{byte:02X} - PPU digit 1 (BCD: {byte & 0xF})")
        elif pos == 13:  # E5
            print(f"Byte {pos:2d}: 0x{byte:02X} - PPU digit 2 (BCD: {byte & 0xF})")
        elif pos == 14:  # E1
            print(f"Byte {pos:2d}: 0x{byte:02X} - PPU digit 3 (BCD: {byte & 0xF})")
        elif pos == 15:  # E8
            print(f"Byte {pos:2d}: 0x{byte:02X} - PPU digit 4 (BCD: {byte & 0xF})")
        elif pos == 16:  # F9
            print(f"Byte {pos:2d}: 0x{byte:02X} - VOLUME_NEXT (Volume data follows)")
        elif pos == 17:  # E0
            print(f"Byte {pos:2d}: 0x{byte:02X} - Volume digit 1 (BCD: {byte & 0xF})")
        elif pos == 18:  # E7
            print(f"Byte {pos:2d}: 0x{byte:02X} - Volume digit 2 (BCD: {byte & 0xF})")
        elif pos == 19:  # E2
            print(f"Byte {pos:2d}: 0x{byte:02X} - Volume digit 3 (BCD: {byte & 0xF})")
        elif pos == 20:  # E1
            print(f"Byte {pos:2d}: 0x{byte:02X} - Volume digit 4 (BCD: {byte & 0xF})")
        elif pos == 21:  # E0
            print(f"Byte {pos:2d}: 0x{byte:02X} - Volume digit 5 (BCD: {byte & 0xF})")
        elif pos == 22:  # FA
            print(f"Byte {pos:2d}: 0x{byte:02X} - MONEY_NEXT (Money data follows)")
        elif pos == 23:  # E0
            print(f"Byte {pos:2d}: 0x{byte:02X} - Money digit 1 (BCD: {byte & 0xF})")
        elif pos == 24:  # E0
            print(f"Byte {pos:2d}: 0x{byte:02X} - Money digit 2 (BCD: {byte & 0xF})")
        elif pos == 25:  # E0
            print(f"Byte {pos:2d}: 0x{byte:02X} - Money digit 3 (BCD: {byte & 0xF})")
        elif pos == 26:  # E0
            print(f"Byte {pos:2d}: 0x{byte:02X} - Money digit 4 (BCD: {byte & 0xF})")
        elif pos == 27:  # E1
            print(f"Byte {pos:2d}: 0x{byte:02X} - Money digit 5 (BCD: {byte & 0xF})")
        elif pos == 28:  # FB
            print(f"Byte {pos:2d}: 0x{byte:02X} - LRC_NEXT (LRC checksum follows)")
        elif pos == 29:  # EE
            print(f"Byte {pos:2d}: 0x{byte:02X} - LRC checksum (BCD: {byte & 0xF})")
        elif pos == 30:  # F0
            print(f"Byte {pos:2d}: 0x{byte:02X} - ETX (End of Text)")
        else:
            print(f"Byte {pos:2d}: 0x{byte:02X} - Data (BCD: {byte & 0xF})")

        pos += 1

    print("\n=== Extracted Data ===")

    # Extract Price Per Unit (PPU)
    ppu_digits = [0, 5, 1, 8]  # From positions 12-15
    ppu_value = 0
    for i, digit in enumerate(ppu_digits):
        ppu_value += digit * (10**i)
    ppu_final = ppu_value / 1000.0
    print(f"Price Per Unit: {ppu_final:.3f} (from BCD: {ppu_digits})")

    # Extract Volume
    volume_digits = [
        0,
        7,
        2,
        1,
        0,
        1,
    ]  # From positions 17-22 (but we only have 5 digits)
    volume_digits = [0, 7, 2, 1, 0]  # Corrected
    volume_value = 0
    for i, digit in enumerate(volume_digits):
        volume_value += digit * (10**i)
    volume_final = volume_value / 1000.0
    print(f"Volume: {volume_final:.3f} (from BCD: {volume_digits})")

    # Extract Money
    money_digits = [0, 0, 0, 0, 1]  # From positions 23-27
    money_value = 0
    for i, digit in enumerate(money_digits):
        money_value += digit * (10**i)
    money_final = money_value / 100.0
    print(f"Money: {money_final:.2f} (from BCD: {money_digits})")

    # Extract Grade
    grade = 0  # From position 9
    print(f"Grade: {grade}")

    # Extract Pump ID data
    pump_id_digits = [11, 3, 0, 0, 2]  # From positions 3-7
    print(f"Pump ID data: {pump_id_digits}")

    print("\n=== Summary ===")
    print(f"This appears to be a transaction data response containing:")
    print(f"  - Grade: {grade}")
    print(f"  - Price Per Unit: ${ppu_final:.3f}")
    print(f"  - Volume: {volume_final:.3f} gallons")
    print(f"  - Money: ${money_final:.2f}")
    print(f"  - Pump ID data: {pump_id_digits}")

    # Calculate what the transaction should be
    calculated_money = volume_final * ppu_final
    print(f"\nCalculated money (Volume × PPU): ${calculated_money:.2f}")
    print(f"Reported money: ${money_final:.2f}")

    if abs(calculated_money - money_final) < 0.01:
        print("✓ Money calculation matches!")
    else:
        print("⚠ Money calculation doesn't match exactly")


if __name__ == "__main__":
    analyze_specific_frame()
