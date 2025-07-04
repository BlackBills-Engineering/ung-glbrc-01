#!/usr/bin/env python3
"""
Logging Test Script for Gilbarco SK700-II System

This script demonstrates the enhanced logging capabilities by:
1. Testing protocol command building
2. Simulating serial communication 
3. Showing data block parsing
4. Demonstrating error handling with detailed logs
"""

import logging
import sys
import time
from pump_controller import GilbarcoTwoWireProtocol, SerialConnection, PumpController
from pump_manager import PumpManager
from models import PumpInfo


def setup_detailed_logging():
    """Configure detailed logging for demonstration"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('logging_test.log', mode='w')
        ]
    )
    
    # Set specific levels
    logging.getLogger("LoggingTest").setLevel(logging.INFO)
    logging.getLogger("PumpController").setLevel(logging.DEBUG)
    logging.getLogger("SerialConnection").setLevel(logging.DEBUG)
    logging.getLogger("PumpManager").setLevel(logging.INFO)


def test_protocol_logging():
    """Test protocol command building and parsing"""
    logger = logging.getLogger("LoggingTest")
    
    logger.info("=== Testing Protocol Command Building ===")
    
    # Test various commands
    commands = [
        ("Status Poll", GilbarcoTwoWireProtocol.build_status_command, 1),
        ("Authorize", GilbarcoTwoWireProtocol.build_authorize_command, 1), 
        ("Stop", GilbarcoTwoWireProtocol.build_stop_command, 1),
        ("Transaction Request", GilbarcoTwoWireProtocol.build_transaction_request, 1),
    ]
    
    for name, func, address in commands:
        try:
            command = func(address)
            logger.info(f"{name} command for address {address}: {command.hex().upper()}")
            
            # Parse if it's a status command
            if name == "Status Poll":
                # Simulate a response
                response = b'\x61'  # Status=6 (OFF), Pump=1
                pump_id, status = GilbarcoTwoWireProtocol.parse_status_response(response)
                status_enum = GilbarcoTwoWireProtocol.status_code_to_enum(status)
                logger.info(f"Simulated response: Pump {pump_id}, Status {status:X} ({status_enum.value})")
                
        except Exception as e:
            logger.error(f"Error testing {name}: {str(e)}", exc_info=True)


def test_data_block_parsing():
    """Test data block parsing with detailed logging"""
    logger = logging.getLogger("LoggingTest")
    
    logger.info("=== Testing Data Block Parsing ===")
    
    # Simulate a transaction data block
    test_data_block = bytes([
        0xFF,  # STX
        0xF8,  # Pump ID next
        0xE1, 0xE0, 0xE0, 0xE0, 0xE0,  # Pump ID data
        0xF6,  # Grade next
        0xE1,  # Grade 1
        0xF9,  # Volume next
        0xE1, 0xE2, 0xE3, 0xE0, 0xE0, 0xE0,  # Volume in BCD
        0xFA,  # Money next
        0xE5, 0xE0, 0xE0, 0xE0, 0xE0, 0xE0,  # Money in BCD
        0xF0   # ETX
    ])
    
    logger.info(f"Test data block: {test_data_block.hex().upper()}")
    
    # Parse the data block
    try:
        parsed_data = GilbarcoTwoWireProtocol.parse_transaction_data(test_data_block)
        if parsed_data:
            logger.info("Successfully parsed transaction data:")
            for key, value in parsed_data.items():
                logger.info(f"  {key}: {value}")
        else:
            logger.warning("Failed to parse transaction data")
    except Exception as e:
        logger.error(f"Error parsing data block: {str(e)}", exc_info=True)


def test_pump_controller_logging():
    """Test pump controller with simulated errors"""
    logger = logging.getLogger("LoggingTest")
    
    logger.info("=== Testing Pump Controller Logging ===")
    
    # Create a pump info for a non-existent port
    pump_info = PumpInfo(
        pump_id=99,
        com_port="COM99",  # Non-existent port
        address=1,
        name="Test Pump"
    )
    
    logger.info(f"Creating pump controller for {pump_info.name}")
    controller = PumpController(pump_info)
    
    # Try to get status (will fail and show error logging)
    logger.info("Attempting to get status (will demonstrate error logging)...")
    status = controller.get_status()
    
    logger.info(f"Status result: {status.status.value}")
    if status.error_message:
        logger.info(f"Error message: {status.error_message}")


def test_discovery_logging():
    """Test pump discovery with detailed logging"""
    logger = logging.getLogger("LoggingTest")
    
    logger.info("=== Testing Pump Discovery Logging ===")
    
    manager = PumpManager()
    
    # Test discovery on non-existent ports to show logging
    result = manager.discover_pumps(
        com_ports=["COM98", "COM99"],  # Non-existent ports
        address_range=(1, 3),          # Limited range for faster testing
        timeout=0.5                    # Short timeout
    )
    
    logger.info(f"Discovery completed: {result.total_found} pumps found")


def main():
    """Run all logging tests"""
    setup_detailed_logging()
    
    logger = logging.getLogger("LoggingTest")
    logger.info("=== Gilbarco SK700-II Logging Test Started ===")
    
    try:
        test_protocol_logging()
        test_data_block_parsing()
        test_pump_controller_logging()
        test_discovery_logging()
        
        logger.info("=== All Logging Tests Completed Successfully ===")
        logger.info("Check 'logging_test.log' for complete log output")
        
    except Exception as e:
        logger.error(f"Test suite error: {str(e)}", exc_info=True)


if __name__ == "__main__":
    main()
