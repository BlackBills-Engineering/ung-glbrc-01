"""
Unit tests for the Gilbarco SK700-II Control System
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import serial
from datetime import datetime

from models import PumpInfo, PumpStatus, PumpStatusResponse
from pump_controller import GilbarcoProtocol, SerialConnection, PumpController
from pump_manager import PumpManager


class TestGilbarcoProtocol(unittest.TestCase):
    """Test cases for GilbarcoProtocol class"""
    
    def test_build_command(self):
        """Test command building"""
        command = GilbarcoProtocol.build_command(1, "S", "00")
        self.assertEqual(command, b"01S00\r")
        
        command = GilbarcoProtocol.build_command(15, "A", "12345")
        self.assertEqual(command, b"15A12345\r")
    
    def test_parse_response(self):
        """Test response parsing"""
        address, cmd, data = GilbarcoProtocol.parse_response(b"01S00IDLE")
        self.assertEqual(address, 1)
        self.assertEqual(cmd, "S")
        self.assertEqual(data, "00IDLE")
        
        # Test error case
        address, cmd, data = GilbarcoProtocol.parse_response(b"XX")
        self.assertEqual(address, 0)
        self.assertEqual(cmd, "ERR")
    
    def test_status_code_to_enum(self):
        """Test status code conversion"""
        self.assertEqual(
            GilbarcoProtocol.status_code_to_enum("00"), 
            PumpStatus.IDLE
        )
        self.assertEqual(
            GilbarcoProtocol.status_code_to_enum("03"), 
            PumpStatus.DISPENSING
        )
        self.assertEqual(
            GilbarcoProtocol.status_code_to_enum("99"), 
            PumpStatus.ERROR
        )


class TestSerialConnection(unittest.TestCase):
    """Test cases for SerialConnection class"""
    
    @patch('serial.Serial')
    def test_connect_success(self, mock_serial):
        """Test successful connection"""
        mock_connection = MagicMock()
        mock_connection.is_open = True
        mock_serial.return_value = mock_connection
        
        conn = SerialConnection("COM1")
        result = conn.connect()
        
        self.assertTrue(result)
        self.assertTrue(conn.is_connected)
        mock_serial.assert_called_once()
    
    @patch('serial.Serial')
    def test_connect_failure(self, mock_serial):
        """Test connection failure"""
        mock_serial.side_effect = serial.SerialException("Port not found")
        
        conn = SerialConnection("COM99")
        result = conn.connect()
        
        self.assertFalse(result)
        self.assertFalse(conn.is_connected)
    
    @patch('serial.Serial')
    def test_send_command(self, mock_serial):
        """Test sending command"""
        mock_connection = MagicMock()
        mock_connection.is_open = True
        mock_connection.read_all.return_value = b"01S00IDLE\r"
        mock_serial.return_value = mock_connection
        
        conn = SerialConnection("COM1")
        conn.connect()
        
        response = conn.send_command(b"01S00\r")
        
        self.assertEqual(response, b"01S00IDLE\r")
        mock_connection.write.assert_called_once_with(b"01S00\r")


class TestPumpController(unittest.TestCase):
    """Test cases for PumpController class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.pump_info = PumpInfo(
            pump_id=1,
            com_port="COM1",
            address=1,
            name="Test Pump",
            is_connected=False
        )
        self.controller = PumpController(self.pump_info)
    
    @patch.object(SerialConnection, 'send_command')
    @patch.object(SerialConnection, 'connect')
    def test_get_status_success(self, mock_connect, mock_send):
        """Test successful status retrieval"""
        mock_connect.return_value = True
        mock_send.return_value = b"01S00IDLE\r"
        
        status = self.controller.get_status()
        
        self.assertIsInstance(status, PumpStatusResponse)
        self.assertEqual(status.pump_id, 1)
        self.assertEqual(status.status, PumpStatus.IDLE)
    
    @patch.object(SerialConnection, 'send_command')
    @patch.object(SerialConnection, 'connect')
    def test_get_status_offline(self, mock_connect, mock_send):
        """Test status when pump is offline"""
        mock_connect.return_value = True
        mock_send.return_value = None  # No response
        
        status = self.controller.get_status()
        
        self.assertEqual(status.status, PumpStatus.OFFLINE)
        self.assertIsNotNone(status.error_message)


class TestPumpManager(unittest.TestCase):
    """Test cases for PumpManager class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.manager = PumpManager()
    
    def test_add_pump(self):
        """Test adding a pump"""
        pump_info = PumpInfo(
            pump_id=1,
            com_port="COM1",
            address=1,
            name="Test Pump"
        )
        
        result = self.manager.add_pump(pump_info)
        
        self.assertTrue(result)
        self.assertIn(1, self.manager.pumps)
    
    def test_remove_pump(self):
        """Test removing a pump"""
        pump_info = PumpInfo(
            pump_id=1,
            com_port="COM1",
            address=1,
            name="Test Pump"
        )
        
        self.manager.add_pump(pump_info)
        result = self.manager.remove_pump(1)
        
        self.assertTrue(result)
        self.assertNotIn(1, self.manager.pumps)
    
    def test_get_pump_list(self):
        """Test getting pump list"""
        pump_info = PumpInfo(
            pump_id=1,
            com_port="COM1",
            address=1,
            name="Test Pump"
        )
        
        self.manager.add_pump(pump_info)
        pump_list = self.manager.get_pump_list()
        
        self.assertEqual(len(pump_list), 1)
        self.assertEqual(pump_list[0].pump_id, 1)
    
    @patch('serial.tools.list_ports.comports')
    @patch.object(PumpManager, '_test_pump_connection')
    def test_discover_pumps(self, mock_test, mock_comports):
        """Test pump discovery"""
        # Mock available COM ports
        mock_port = Mock()
        mock_port.device = "COM1"
        mock_comports.return_value = [mock_port]
        
        # Mock successful pump test
        mock_test.return_value = True
        
        result = self.manager.discover_pumps(address_range=(1, 2))
        
        self.assertGreater(result.total_found, 0)
        self.assertEqual(len(result.discovered_pumps), 2)  # Address 1 and 2


if __name__ == '__main__':
    unittest.main()
