#!/usr/bin/env python3
"""
COM Port Testing Suite for Gilbarco SK700-II System

This script provides extensive testing of COM port connections and Gilbarco protocol communication.
Designed to run on Windows systems with actual COM ports.

Features:
- COM port discovery and availability testing
- Serial connection parameter validation
- Gilbarco Two-Wire Protocol command testing
- Loopback testing (if supported)
- Error handling and detailed logging
- Performance benchmarking
- Hardware compatibility checks

Usage:
    python test_comport.py
    python test_comport.py --port COM1
    python test_comport.py --scan-all
    python test_comport.py --verbose
"""

import sys
import time
import serial
import serial.tools.list_ports
import logging
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import threading
import json

# Import our Gilbarco protocol classes
try:
    from pump_controller import GilbarcoTwoWireProtocol, SerialConnection, TwoWireManagerRegistry
    from models import PumpInfo, PumpStatus
    from config import Config
except ImportError as e:
    print(f"Warning: Could not import Gilbarco modules: {e}")
    print("Some tests will be skipped. Make sure you're running from the project directory.")


class COMPortTester:
    """COM port testing suite"""
    
    def __init__(self, log_level: str = "INFO"):
        self.setup_logging(log_level)
        self.logger = logging.getLogger("COMPortTester")
        self.test_results = {}
        self.start_time = datetime.now()
        
    def setup_logging(self, level: str):
        """Configure detailed logging"""
        log_filename = f"logs/comport_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_filename, mode='w', encoding='utf-8')
            ]
        )
        
        # Set specific logger levels
        logging.getLogger("COMPortTester").setLevel(getattr(logging, level.upper()))
        logging.getLogger("SerialConnection").setLevel(logging.DEBUG)
        logging.getLogger("TwoWireManager").setLevel(logging.DEBUG)
        
        print(f"Logging to: {log_filename}")
    
    def discover_com_ports(self) -> List[Dict]:
        """Discover all available COM ports with detailed information"""
        self.logger.info("=== COM Port Discovery ===")
        
        ports = []
        com_ports = serial.tools.list_ports.comports()
        
        if not com_ports:
            self.logger.warning("No COM ports found on this system")
            return ports
        
        self.logger.info(f"Found {len(com_ports)} COM ports:")
        
        for port in com_ports:
            port_info = {
                'device': port.device,
                'description': port.description,
                'hwid': port.hwid,
                'manufacturer': getattr(port, 'manufacturer', 'Unknown'),
                'product': getattr(port, 'product', 'Unknown'),
                'serial_number': getattr(port, 'serial_number', 'Unknown'),
                'location': getattr(port, 'location', 'Unknown'),
                'vid': getattr(port, 'vid', None),
                'pid': getattr(port, 'pid', None)
            }
            ports.append(port_info)
            
            self.logger.info(f"Port: {port.device}")
            self.logger.info(f"  Description: {port.description}")
            self.logger.info(f"  Hardware ID: {port.hwid}")
            if port_info['manufacturer'] != 'Unknown':
                self.logger.info(f"  Manufacturer: {port_info['manufacturer']}")
            if port_info['vid'] and port_info['pid']:
                self.logger.info(f"  VID:PID: {port_info['vid']:04X}:{port_info['pid']:04X}")
            self.logger.info("")
        
        return ports
    
    def test_basic_connection(self, port_name: str, baudrate: int = 9600) -> Dict:
        """Test basic serial connection to a COM port"""
        self.logger.info(f"=== Testing Basic Connection to {port_name} ===")
        
        result = {
            'port': port_name,
            'baudrate': baudrate,
            'connection_successful': False,
            'error_message': None,
            'connection_time': None,
            'port_settings': {}
        }
        
        try:
            start_time = time.time()
            
            self.logger.info(f"Attempting to open {port_name} at {baudrate} baud...")
            
            # Test various common configurations
            configurations = [
                {'parity': serial.PARITY_NONE, 'name': '8N1'},
                {'parity': serial.PARITY_EVEN, 'name': '8E1 (Gilbarco)'},
                {'parity': serial.PARITY_ODD, 'name': '8O1'},
            ]
            
            for config in configurations:
                try:
                    self.logger.info(f"Testing {config['name']} configuration...")
                    
                    ser = serial.Serial(
                        port=port_name,
                        baudrate=baudrate,
                        bytesize=serial.EIGHTBITS,
                        parity=config['parity'],
                        stopbits=serial.STOPBITS_ONE,
                        timeout=1.0,
                        write_timeout=1.0
                    )
                    
                    connection_time = time.time() - start_time
                    
                    # Get port settings
                    port_settings = {
                        'is_open': ser.is_open,
                        'baudrate': ser.baudrate,
                        'bytesize': ser.bytesize,
                        'parity': ser.parity,
                        'stopbits': ser.stopbits,
                        'timeout': ser.timeout,
                        'write_timeout': ser.write_timeout,
                        'in_waiting': ser.in_waiting,
                        'out_waiting': ser.out_waiting
                    }
                    
                    self.logger.info(f"✓ Successfully opened {port_name} with {config['name']}")
                    self.logger.info(f"Connection time: {connection_time:.3f}s")
                    self.logger.info(f"Port settings: {port_settings}")
                    
                    result.update({
                        'connection_successful': True,
                        'connection_time': connection_time,
                        'port_settings': port_settings,
                        'successful_config': config['name']
                    })
                    
                    ser.close()
                    self.logger.info(f"✓ Successfully closed {port_name}")
                    break
                    
                except serial.SerialException as e:
                    self.logger.warning(f"Failed to open {port_name} with {config['name']}: {str(e)}")
                    continue
            
            if not result['connection_successful']:
                result['error_message'] = "All configuration attempts failed"
                
        except Exception as e:
            result['error_message'] = str(e)
            self.logger.error(f"Unexpected error testing {port_name}: {str(e)}")
        
        return result
    
    def test_gilbarco_protocol(self, port_name: str) -> Dict:
        """Test Gilbarco Two-Wire Protocol communication"""
        self.logger.info(f"=== Testing Gilbarco Protocol on {port_name} ===")
        
        result = {
            'port': port_name,
            'protocol_test_successful': False,
            'commands_tested': [],
            'responses_received': [],
            'error_message': None
        }
        
        try:
            # Create pump info for testing
            pump_info = PumpInfo(
                pump_id=999,
                com_port=port_name,
                address=1,
                name="Test Pump",
                is_connected=False
            )
            
            # Create manager for this COM port
            manager = TwoWireManagerRegistry.get_manager(port_name)
            
            # Test commands
            test_commands = [
                ('Status Poll (Address 1)', GilbarcoTwoWireProtocol.build_status_command, 1),
                ('Status Poll (Address 2)', GilbarcoTwoWireProtocol.build_status_command, 2),
                ('Authorize (Address 1)', GilbarcoTwoWireProtocol.build_authorize_command, 1),
                ('Stop (Address 1)', GilbarcoTwoWireProtocol.build_stop_command, 1),
                ('Transaction Request', GilbarcoTwoWireProtocol.build_transaction_request, 1),
            ]
            
            self.logger.info("Testing Gilbarco protocol commands...")
            
            for test_name, command_func, address in test_commands:
                try:
                    self.logger.info(f"Testing: {test_name}")
                    
                    # Build command
                    command = command_func(address)
                    command_hex = command.hex().upper()
                    
                    self.logger.info(f"Command bytes: {command_hex}")
                    result['commands_tested'].append({
                        'name': test_name,
                        'command_hex': command_hex,
                        'address': address
                    })
                    
                    # Try to send command (will fail if no pump connected, but tests the protocol)
                    if manager.connect():
                        response = manager.connection.send_command(command, expect_response=True)
                        
                        if response:
                            response_hex = response.hex().upper()
                            self.logger.info(f"Response received: {response_hex}")
                            result['responses_received'].append({
                                'command': test_name,
                                'response_hex': response_hex
                            })
                            
                            # Try to parse response if it's a status command
                            if 'Status Poll' in test_name and len(response) == 1:
                                try:
                                    pump_id, status = GilbarcoTwoWireProtocol.parse_status_response(response)
                                    status_enum = GilbarcoTwoWireProtocol.status_code_to_enum(status)
                                    self.logger.info(f"Parsed: Pump {pump_id}, Status 0x{status:X} ({status_enum.value})")
                                except Exception as e:
                                    self.logger.warning(f"Could not parse response: {str(e)}")
                        else:
                            self.logger.info("No response received (expected if no pump connected)")
                        
                        manager.disconnect()
                    else:
                        self.logger.warning(f"Could not connect to {port_name}")
                    
                except Exception as e:
                    self.logger.error(f"Error testing {test_name}: {str(e)}")
            
            result['protocol_test_successful'] = len(result['commands_tested']) > 0
            
        except Exception as e:
            result['error_message'] = str(e)
            self.logger.error(f"Protocol test failed: {str(e)}")
        
        return result
    
    def test_loopback(self, port_name: str) -> Dict:
        """Test loopback communication (requires loopback adapter or jumper)"""
        self.logger.info(f"=== Testing Loopback on {port_name} ===")
        
        result = {
            'port': port_name,
            'loopback_successful': False,
            'bytes_sent': 0,
            'bytes_received': 0,
            'error_message': None,
            'test_data': []
        }
        
        try:
            ser = serial.Serial(
                port=port_name,
                baudrate=9600,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0
            )
            
            # Test data patterns
            test_patterns = [
                b'\x00',  # Null byte
                b'\xFF',  # All bits set
                b'\xAA',  # Alternating bits
                b'\x55',  # Alternating bits (inverse)
                b'\x01\x02\x03\x04\x05',  # Sequential bytes
                b'Hello',  # ASCII text
                GilbarcoTwoWireProtocol.build_status_command(1),  # Gilbarco command
            ]
            
            self.logger.info("Testing loopback with various patterns...")
            
            successful_tests = 0
            
            for i, pattern in enumerate(test_patterns):
                try:
                    pattern_hex = pattern.hex().upper()
                    self.logger.info(f"Test {i+1}: Sending {pattern_hex}")
                    
                    # Clear buffers
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()
                    
                    # Send data
                    bytes_written = ser.write(pattern)
                    ser.flush()
                    
                    # Wait for echo
                    time.sleep(0.1)
                    
                    # Read response
                    response = ser.read(len(pattern))
                    
                    if response == pattern:
                        self.logger.info(f"✓ Loopback successful for pattern {pattern_hex}")
                        successful_tests += 1
                        result['test_data'].append({
                            'pattern': pattern_hex,
                            'success': True,
                            'response': response.hex().upper()
                        })
                    else:
                        response_hex = response.hex().upper() if response else "NO_RESPONSE"
                        self.logger.warning(f"✗ Loopback failed: sent {pattern_hex}, got {response_hex}")
                        result['test_data'].append({
                            'pattern': pattern_hex,
                            'success': False,
                            'response': response_hex
                        })
                    
                    result['bytes_sent'] += bytes_written
                    result['bytes_received'] += len(response)
                    
                except Exception as e:
                    self.logger.error(f"Error in loopback test {i+1}: {str(e)}")
            
            result['loopback_successful'] = successful_tests > 0
            
            if successful_tests == len(test_patterns):
                self.logger.info(f"✓ All {len(test_patterns)} loopback tests passed!")
            elif successful_tests > 0:
                self.logger.info(f"⚠ {successful_tests}/{len(test_patterns)} loopback tests passed")
            else:
                self.logger.warning("✗ No loopback tests passed (loopback adapter may not be connected)")
            
            ser.close()
            
        except Exception as e:
            result['error_message'] = str(e)
            self.logger.error(f"Loopback test failed: {str(e)}")
        
        return result
    
    def test_baudrate_compatibility(self, port_name: str) -> Dict:
        """Test various baud rates for compatibility"""
        self.logger.info(f"=== Testing Baud Rate Compatibility on {port_name} ===")
        
        result = {
            'port': port_name,
            'tested_baudrates': [],
            'supported_baudrates': [],
            'error_message': None
        }
        
        # Common baud rates for industrial/fuel dispenser systems
        test_baudrates = [
            1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200,
            5787,  # Gilbarco standard (may not be supported by all adapters)
        ]
        
        try:
            for baudrate in test_baudrates:
                try:
                    self.logger.info(f"Testing {baudrate} baud...")
                    
                    ser = serial.Serial(
                        port=port_name,
                        baudrate=baudrate,
                        timeout=0.5
                    )
                    
                    # Verify the baud rate was set correctly
                    actual_baudrate = ser.baudrate
                    
                    result['tested_baudrates'].append(baudrate)
                    
                    if actual_baudrate == baudrate:
                        self.logger.info(f"✓ {baudrate} baud supported")
                        result['supported_baudrates'].append(baudrate)
                    else:
                        self.logger.warning(f"⚠ {baudrate} baud requested, but got {actual_baudrate}")
                    
                    ser.close()
                    
                except serial.SerialException as e:
                    self.logger.warning(f"✗ {baudrate} baud not supported: {str(e)}")
                except Exception as e:
                    self.logger.error(f"Error testing {baudrate} baud: {str(e)}")
        
        except Exception as e:
            result['error_message'] = str(e)
            self.logger.error(f"Baud rate test failed: {str(e)}")
        
        self.logger.info(f"Supported baud rates: {result['supported_baudrates']}")
        
        return result
    
    def test_performance(self, port_name: str, duration: int = 10) -> Dict:
        """Test communication performance and timing"""
        self.logger.info(f"=== Testing Performance on {port_name} ===")
        
        result = {
            'port': port_name,
            'duration': duration,
            'bytes_sent': 0,
            'bytes_received': 0,
            'commands_sent': 0,
            'successful_commands': 0,
            'average_response_time': 0,
            'min_response_time': float('inf'),
            'max_response_time': 0,
            'error_count': 0,
            'throughput_bps': 0,
            'error_message': None
        }
        
        try:
            ser = serial.Serial(
                port=port_name,
                baudrate=9600,
                parity=serial.PARITY_EVEN,  # Gilbarco standard
                timeout=0.1
            )
            
            self.logger.info(f"Running performance test for {duration} seconds...")
            
            start_time = time.time()
            end_time = start_time + duration
            response_times = []
            
            command = GilbarcoTwoWireProtocol.build_status_command(1)
            
            while time.time() < end_time:
                try:
                    # Clear buffers
                    ser.reset_input_buffer()
                    
                    # Send command and measure response time
                    cmd_start = time.time()
                    bytes_written = ser.write(command)
                    ser.flush()
                    
                    # Try to read response
                    response = ser.read(1)
                    cmd_end = time.time()
                    
                    response_time = cmd_end - cmd_start
                    response_times.append(response_time)
                    
                    result['bytes_sent'] += bytes_written
                    result['bytes_received'] += len(response)
                    result['commands_sent'] += 1
                    
                    if response:
                        result['successful_commands'] += 1
                    
                    # Update timing stats
                    result['min_response_time'] = min(result['min_response_time'], response_time)
                    result['max_response_time'] = max(result['max_response_time'], response_time)
                    
                    # Small delay to prevent overwhelming
                    time.sleep(0.01)
                    
                except Exception as e:
                    result['error_count'] += 1
                    if result['error_count'] % 100 == 0:  # Log every 100th error
                        self.logger.warning(f"Performance test error #{result['error_count']}: {str(e)}")
            
            actual_duration = time.time() - start_time
            
            if response_times:
                result['average_response_time'] = sum(response_times) / len(response_times)
            
            if result['min_response_time'] == float('inf'):
                result['min_response_time'] = 0
            
            total_bytes = result['bytes_sent'] + result['bytes_received']
            result['throughput_bps'] = total_bytes / actual_duration
            
            self.logger.info(f"Performance test completed:")
            self.logger.info(f"  Commands sent: {result['commands_sent']}")
            self.logger.info(f"  Successful: {result['successful_commands']}")
            self.logger.info(f"  Errors: {result['error_count']}")
            self.logger.info(f"  Avg response time: {result['average_response_time']*1000:.2f}ms")
            self.logger.info(f"  Min response time: {result['min_response_time']*1000:.2f}ms")
            self.logger.info(f"  Max response time: {result['max_response_time']*1000:.2f}ms")
            self.logger.info(f"  Throughput: {result['throughput_bps']:.2f} bytes/sec")
            
            ser.close()
            
        except Exception as e:
            result['error_message'] = str(e)
            self.logger.error(f"Performance test failed: {str(e)}")
        
        return result
    
    def runc_test(self, port_name: str) -> Dict:
        """Run all tests on a specific COM port"""
        self.logger.info(f"=== Test Suite for {port_name} ===")
        
        port_results = {
            'port': port_name,
            'test_start_time': datetime.now().isoformat(),
            'basic_connection': None,
            'gilbarco_protocol': None,
            'loopback': None,
            'baudrate_compatibility': None,
            'performance': None,
            'test_end_time': None,
            'total_duration': None
        }
        
        try:
            # Basic connection test
            port_results['basic_connection'] = self.test_basic_connection(port_name)
            
            # Only continue if basic connection works
            if port_results['basic_connection']['connection_successful']:
                
                # Gilbarco protocol test
                port_results['gilbarco_protocol'] = self.test_gilbarco_protocol(port_name)
                
                # Loopback test (optional - may fail without loopback adapter)
                port_results['loopback'] = self.test_loopback(port_name)
                
                # Baud rate compatibility
                port_results['baudrate_compatibility'] = self.test_baudrate_compatibility(port_name)
                
                # Performance test
                port_results['performance'] = self.test_performance(port_name, duration=5)
                
            else:
                self.logger.warning(f"Skipping advanced tests for {port_name} - basic connection failed")
        
        except Exception as e:
            self.logger.error(f"Test failed for {port_name}: {str(e)}")
        
        port_results['test_end_time'] = datetime.now().isoformat()
        
        return port_results
    
    def generate_report(self):
        """Generate test report"""
        self.logger.info("=== Generating Test Report ===")
        
        total_duration = datetime.now() - self.start_time
        
        report = {
            'test_session': {
                'start_time': self.start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'duration': str(total_duration),
                'hostname': None,
                'python_version': sys.version,
                'platform': sys.platform
            },
            'discovered_ports': [],
            'port_test_results': self.test_results,
            'summary': {
                'total_ports_found': 0,
                'total_ports_tested': 0,
                'successful_connections': 0,
                'gilbarco_compatible_ports': 0,
                'loopback_capable_ports': 0
            }
        }
        
        # Get hostname
        try:
            import socket
            report['test_session']['hostname'] = socket.gethostname()
        except:
            pass
        
        # Discover ports for report
        report['discovered_ports'] = self.discover_com_ports()
        report['summary']['total_ports_found'] = len(report['discovered_ports'])
        
        # Calculate summary statistics
        for port_name, results in self.test_results.items():
            report['summary']['total_ports_tested'] += 1
            
            if results.get('basic_connection', {}).get('connection_successful'):
                report['summary']['successful_connections'] += 1
            
            if results.get('gilbarco_protocol', {}).get('protocol_test_successful'):
                report['summary']['gilbarco_compatible_ports'] += 1
            
            if results.get('loopback', {}).get('loopback_successful'):
                report['summary']['loopback_capable_ports'] += 1
        
        # Save report to JSON file
        report_filename = f"logs/comport_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(report_filename, 'w') as f:
                json.dump(report, f, indent=2)
            
            self.logger.info(f"Test report saved to: {report_filename}")
            
        except Exception as e:
            self.logger.error(f"Failed to save report: {str(e)}")
        
        # Print summary
        self.logger.info("=== TEST SUMMARY ===")
        self.logger.info(f"Total test duration: {total_duration}")
        self.logger.info(f"COM ports found: {report['summary']['total_ports_found']}")
        self.logger.info(f"COM ports tested: {report['summary']['total_ports_tested']}")
        self.logger.info(f"Successful connections: {report['summary']['successful_connections']}")
        self.logger.info(f"Gilbarco compatible: {report['summary']['gilbarco_compatible_ports']}")
        self.logger.info(f"Loopback capable: {report['summary']['loopback_capable_ports']}")
        
        return report


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="COM Port Testing Suite")
    parser.add_argument('--port', type=str, help="Specific COM port to test (e.g., COM1)")
    parser.add_argument('--scan-all', action='store_true', help="Test all available COM ports")
    parser.add_argument('--verbose', action='store_true', help="Enable verbose logging")
    parser.add_argument('--log-level', type=str, default='INFO', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help="Set logging level")
    
    args = parser.parse_args()
    
    # Set log level
    log_level = 'DEBUG' if args.verbose else args.log_level
    
    # Create tester
    tester = COMPortTester(log_level=log_level)
    
    print("="*60)
    print("Gilbarco SK700-II COM Port Testing Suite")
    print("="*60)
    print(f"Start time: {datetime.now()}")
    print(f"Log level: {log_level}")
    print()
    
    try:
        if args.port:
            # Test specific port
            tester.logger.info(f"Testing specific port: {args.port}")
            results = tester.runc_test(args.port)
            tester.test_results[args.port] = results
            
        elif args.scan_all:
            # Test all available ports
            ports = tester.discover_com_ports()
            
            if not ports:
                tester.logger.error("No COM ports found. Cannot run tests.")
                return 1
            
            tester.logger.info(f"Testing all {len(ports)} available ports...")
            
            for port_info in ports:
                port_name = port_info['device']
                tester.logger.info(f"Testing {port_name}...")
                results = tester.runc_test(port_name)
                tester.test_results[port_name] = results
        
        else:
            # Interactive mode - discover and ask user
            ports = tester.discover_com_ports()
            
            if not ports:
                tester.logger.error("No COM ports found. Cannot run tests.")
                return 1
            
            print("\nAvailable COM ports:")
            for i, port_info in enumerate(ports, 1):
                print(f"{i}. {port_info['device']} - {port_info['description']}")
            
            print(f"{len(ports)+1}. Test all ports")
            print("0. Exit")
            
            try:
                choice = input("\nSelect port to test (number): ").strip()
                
                if choice == '0':
                    return 0
                elif choice == str(len(ports)+1):
                    # Test all ports
                    for port_info in ports:
                        port_name = port_info['device']
                        results = tester.runc_test(port_name)
                        tester.test_results[port_name] = results
                else:
                    # Test specific port
                    port_index = int(choice) - 1
                    if 0 <= port_index < len(ports):
                        port_name = ports[port_index]['device']
                        results = tester.runc_test(port_name)
                        tester.test_results[port_name] = results
                    else:
                        tester.logger.error("Invalid selection")
                        return 1
                        
            except (ValueError, KeyboardInterrupt):
                tester.logger.info("Test cancelled by user")
                return 0
        
        # Generate final report
        report = tester.generate_report()
        
        print("\n" + "="*60)
        print("Testing completed successfully!")
        print("Check the log files and JSON report for detailed results.")
        print("="*60)
        
        return 0
        
    except KeyboardInterrupt:
        tester.logger.info("Testing interrupted by user")
        return 0
    except Exception as e:
        tester.logger.error(f"Fatal error: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
