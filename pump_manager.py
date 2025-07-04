import serial.tools.list_ports
import logging
import asyncio
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from models import PumpInfo, PumpStatusResponse, PumpDiscoveryResult
from pump_controller import PumpController, GilbarcoProtocol


class PumpManager:
    """Manages multiple pumps and provides high-level operations"""
    
    def __init__(self):
        self.pumps: Dict[int, PumpController] = {}
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.logger = logging.getLogger("PumpManager")
        self._next_pump_id = 1
    
    def discover_pumps(self, 
                      com_ports: Optional[List[str]] = None,
                      address_range: Tuple[int, int] = (1, 16),
                      timeout: float = 2.0) -> PumpDiscoveryResult:
        """
        Discover pumps on COM ports
        
        Args:
            com_ports: List of COM ports to scan. If None, scan all available ports
            address_range: Range of pump addresses to test (start, end)
            timeout: Timeout for each pump test
        
        Returns:
            PumpDiscoveryResult with discovered pumps
        """
        start_time = time.time()
        discovered_pumps = []
        
        self.logger.info("=== Starting Pump Discovery ===")
        self.logger.info(f"Address range: {address_range[0]} to {address_range[1]}")
        self.logger.info(f"Timeout per pump: {timeout}s")
        
        # Get COM ports to scan
        if com_ports is None:
            available_ports = [port.device for port in serial.tools.list_ports.comports()]
            self.logger.info("Scanning all available COM ports:")
            for port in serial.tools.list_ports.comports():
                self.logger.info(f"  - {port.device}: {port.description}")
        else:
            available_ports = com_ports
            self.logger.info(f"Scanning specified COM ports: {com_ports}")
        
        if not available_ports:
            self.logger.warning("No COM ports available for scanning")
            return PumpDiscoveryResult(
                discovered_pumps=[],
                total_found=0,
                scan_duration=time.time() - start_time,
                scanned_ports=[]
            )
        
        self.logger.info(f"Starting scan of {len(available_ports)} COM ports...")
        
        for port_index, com_port in enumerate(available_ports, 1):
            self.logger.info(f"[{port_index}/{len(available_ports)}] Scanning {com_port}...")
            
            # Test each address on this COM port
            port_pumps_found = 0
            for address in range(address_range[0], address_range[1] + 1):
                self.logger.debug(f"  Testing address {address} on {com_port}")
                
                pump_info = PumpInfo(
                    pump_id=self._next_pump_id,
                    com_port=com_port,
                    address=address,
                    name=f"Pump {self._next_pump_id}",
                    is_connected=False
                )
                
                # Test if pump responds at this address
                if self._test_pump_connection(pump_info, timeout):
                    discovered_pumps.append(pump_info)
                    port_pumps_found += 1
                    self.logger.info(f"✓ Found pump at {com_port}, address {address} (ID: {self._next_pump_id})")
                    self._next_pump_id += 1
                else:
                    self.logger.debug(f"  No response at {com_port}, address {address}")
            
            self.logger.info(f"  Port {com_port} scan complete: {port_pumps_found} pumps found")
        
        scan_duration = time.time() - start_time
        
        result = PumpDiscoveryResult(
            discovered_pumps=discovered_pumps,
            total_found=len(discovered_pumps),
            scan_duration=scan_duration,
            scanned_ports=available_ports,
            timestamp=datetime.now()
        )
        
        self.logger.info("=== Discovery Summary ===")
        self.logger.info(f"Total pumps found: {len(discovered_pumps)}")
        self.logger.info(f"Scan duration: {scan_duration:.2f}s")
        self.logger.info(f"Ports scanned: {len(available_ports)}")
        for pump in discovered_pumps:
            self.logger.info(f"  - Pump {pump.pump_id}: {pump.com_port} @ address {pump.address}")
        self.logger.info("=== End Discovery ===")
        
        return result
    
    def _test_pump_connection(self, pump_info: PumpInfo, timeout: float) -> bool:
        """Test if a pump responds at the given COM port and address"""
        try:
            self.logger.debug(f"Testing connection to {pump_info.com_port} @ address {pump_info.address}")
            
            controller = PumpController(pump_info)
            controller.connection.timeout = timeout
            
            if controller.connect():
                self.logger.debug(f"Connected to {pump_info.com_port} @ address {pump_info.address}")
                
                # Try to get status with retries
                for attempt in range(3):
                    try:
                        status_response = controller.get_status()
                        self.logger.debug(f"Status attempt {attempt + 1}: {status_response.status.value}")
                        
                        # If we got a valid response (not OFFLINE), pump exists
                        if status_response.status.value != "OFFLINE":
                            self.logger.debug(f"Pump confirmed at {pump_info.com_port} @ {pump_info.address}")
                            controller.disconnect()
                            return True
                    except Exception as e:
                        self.logger.debug(f"Status attempt {attempt + 1} failed: {str(e)}")
                    
                    time.sleep(0.1)  # Small delay between retries
                
                controller.disconnect()
            else:
                self.logger.debug(f"Failed to connect to {pump_info.com_port} @ address {pump_info.address}")
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Test failed for {pump_info.com_port}:{pump_info.address}: {str(e)}")
            return False
    
    def add_pump(self, pump_info: PumpInfo) -> bool:
        """Add a pump to management"""
        try:
            if pump_info.pump_id in self.pumps:
                self.logger.warning(f"Pump {pump_info.pump_id} already exists")
                return False
            
            controller = PumpController(pump_info)
            self.pumps[pump_info.pump_id] = controller
            
            self.logger.info(f"Added pump {pump_info.pump_id} ({pump_info.com_port}:{pump_info.address})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add pump {pump_info.pump_id}: {str(e)}")
            return False
    
    def remove_pump(self, pump_id: int) -> bool:
        """Remove a pump from management"""
        if pump_id in self.pumps:
            controller = self.pumps[pump_id]
            controller.disconnect()
            del self.pumps[pump_id]
            self.logger.info(f"Removed pump {pump_id}")
            return True
        return False
    
    def get_pump_list(self) -> List[PumpInfo]:
        """Get list of all managed pumps"""
        return [controller.pump_info for controller in self.pumps.values()]
    
    def get_pump_status(self, pump_id: int) -> Optional[PumpStatusResponse]:
        """Get status of a specific pump"""
        if pump_id not in self.pumps:
            return None
        
        try:
            return self.pumps[pump_id].get_status()
        except Exception as e:
            self.logger.error(f"Error getting status for pump {pump_id}: {str(e)}")
            return None
    
    def get_all_pump_statuses(self) -> Dict[int, PumpStatusResponse]:
        """Get status of all pumps (threaded for performance)"""
        def get_status(pump_id):
            return pump_id, self.get_pump_status(pump_id)
        
        futures = []
        for pump_id in self.pumps.keys():
            future = self.executor.submit(get_status, pump_id)
            futures.append(future)
        
        results = {}
        for future in futures:
            try:
                pump_id, status = future.result(timeout=5.0)
                if status:
                    results[pump_id] = status
            except Exception as e:
                self.logger.error(f"Error getting pump status: {str(e)}")
        
        return results
    
    def connect_pump(self, pump_id: int) -> bool:
        """Connect to a specific pump"""
        if pump_id not in self.pumps:
            return False
        
        return self.pumps[pump_id].connect()
    
    def disconnect_pump(self, pump_id: int) -> bool:
        """Disconnect from a specific pump"""
        if pump_id not in self.pumps:
            return False
        
        self.pumps[pump_id].disconnect()
        return True
    
    def connect_all_pumps(self) -> Dict[int, bool]:
        """Connect to all pumps"""
        results = {}
        for pump_id in self.pumps.keys():
            results[pump_id] = self.connect_pump(pump_id)
        return results
    
    def disconnect_all_pumps(self):
        """Disconnect from all pumps"""
        for controller in self.pumps.values():
            controller.disconnect()
    
    def shutdown(self):
        """Shutdown pump manager"""
        self.logger.info("Shutting down pump manager...")
        self.disconnect_all_pumps()
        self.executor.shutdown(wait=True)
        self.logger.info("Pump manager shutdown complete")
