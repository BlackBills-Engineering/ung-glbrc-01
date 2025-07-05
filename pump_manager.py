import serial.tools.list_ports
import logging
import asyncio
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from models import PumpInfo, PumpStatusResponse, PumpDiscoveryResult, TransactionData
from pump_controller import TwoWireManagerRegistry, TwoWireManager


class PumpManager:
    """Manages multiple pumps and provides high-level operations in cascade mode"""

    def __init__(self):
        self.pumps: Dict[int, PumpInfo] = {}
        self.managers: Dict[str, TwoWireManager] = {}
        self._next_pump_id = 1
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.logger = logging.getLogger("PumpManager")
        self._cascade_config = {
            "com_ports": None,
            "address_range": (1, 16),
            "timeout": 2.0,
        }

    def discover_pumps(
        self,
        com_ports: Optional[List[str]] = None,
        address_range: Tuple[int, int] = (1, 16),
        timeout: float = 2.0,
    ) -> PumpDiscoveryResult:
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
            available_ports = [
                port.device for port in serial.tools.list_ports.comports()
            ]
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
                scanned_ports=[],
            )

        self.logger.info(f"Starting scan of {len(available_ports)} COM ports...")

        for port_index, com_port in enumerate(available_ports, 1):
            self.logger.info(
                f"[{port_index}/{len(available_ports)}] Scanning {com_port}..."
            )

            # Test each address on this COM port
            port_pumps_found = 0
            for address in range(address_range[0], address_range[1] + 1):
                self.logger.debug(f"  Testing address {address} on {com_port}")

                pump_info = PumpInfo(
                    pump_id=self._next_pump_id,
                    com_port=com_port,
                    address=address,
                    name=f"Pump {self._next_pump_id}",
                    is_connected=False,
                )

                # Test if pump responds at this address
                if self._test_pump_connection(pump_info, timeout):
                    discovered_pumps.append(pump_info)
                    port_pumps_found += 1
                    self.logger.info(
                        f"✓ Found pump at {com_port}, address {address} (ID: {self._next_pump_id})"
                    )
                    self._next_pump_id += 1
                else:
                    self.logger.debug(f"  No response at {com_port}, address {address}")

            self.logger.info(
                f"  Port {com_port} scan complete: {port_pumps_found} pumps found"
            )

        scan_duration = time.time() - start_time

        result = PumpDiscoveryResult(
            discovered_pumps=discovered_pumps,
            total_found=len(discovered_pumps),
            scan_duration=scan_duration,
            scanned_ports=available_ports,
            timestamp=datetime.now(),
        )

        self.logger.info("=== Discovery Summary ===")
        self.logger.info(f"Total pumps found: {len(discovered_pumps)}")
        self.logger.info(f"Scan duration: {scan_duration:.2f}s")
        self.logger.info(f"Ports scanned: {len(available_ports)}")
        for pump in discovered_pumps:
            self.logger.info(
                f"  - Pump {pump.pump_id}: {pump.com_port} @ address {pump.address}"
            )
        self.logger.info("=== End Discovery ===")

        return result

    def _test_pump_connection(self, pump_info: PumpInfo, timeout: float) -> bool:
        """Test if a pump responds at the given COM port and address"""
        try:
            self.logger.debug(
                f"Testing connection to {pump_info.com_port} @ address {pump_info.address}"
            )

            # Get or create manager for this COM port
            manager = TwoWireManagerRegistry.get_manager(
                pump_info.com_port, timeout=timeout
            )

            if manager.connect():
                self.logger.debug(f"Connected to {pump_info.com_port}")

                for attempt in range(3):
                    try:
                        status_response = manager.get_pump_status(
                            pump_info.address, pump_info.pump_id
                        )
                        self.logger.debug(
                            f"Status attempt {attempt + 1}: {status_response.status.value}"
                        )

                        if status_response.status.value != "OFFLINE":
                            self.logger.debug(
                                f"Pump confirmed at {pump_info.com_port} @ {pump_info.address}"
                            )
                            return True
                    except Exception as e:
                        self.logger.debug(
                            f"Status attempt {attempt + 1} failed: {str(e)}"
                        )

                    time.sleep(0.1)
            else:
                self.logger.debug(f"Failed to connect to {pump_info.com_port}")

            return False

        except Exception as e:
            self.logger.debug(
                f"Test failed for {pump_info.com_port}:{pump_info.address}: {str(e)}"
            )
            return False

    def auto_discover_and_manage(
        self,
        com_ports: Optional[List[str]] = None,
        address_range: Tuple[int, int] = (1, 16),
        timeout: float = 2.0,
    ) -> PumpDiscoveryResult:
        """
        Auto-discover pumps and automatically add them to management

        This is the main method for cascade mode operation - it finds all pumps
        and automatically starts managing them.

        Args:
            com_ports: List of COM ports to scan. If None, scan all available ports
            address_range: Range of pump addresses to test (start, end)
            timeout: Timeout for each pump test

        Returns:
            PumpDiscoveryResult with discovered pumps
        """
        discovery_result = self.discover_pumps(com_ports, address_range, timeout)

        self.disconnect_all_ports()
        self.pumps.clear()
        self.managers.clear()

        for pump_info in discovery_result.discovered_pumps:
            self.pumps[pump_info.pump_id] = pump_info

            if pump_info.com_port not in self.managers:
                manager = TwoWireManagerRegistry.get_manager(pump_info.com_port)
                self.managers[pump_info.com_port] = manager

            self.logger.info(f"Auto-added pump {pump_info.pump_id} to management")

        self.logger.info(
            f"Auto-discovery complete: {len(self.pumps)} pumps under management"
        )
        return discovery_result

    def get_pump_info(self, pump_id: int) -> Optional[PumpInfo]:
        """Get pump info for a specific pump"""
        return self.pumps.get(pump_id)

    def get_pump_list(self) -> List[PumpInfo]:
        """Get list of all managed pumps"""
        return list(self.pumps.values())

    def get_pump_status(self, pump_id: int) -> Optional[PumpStatusResponse]:
        """Get status of a specific pump"""
        if pump_id not in self.pumps:
            return None

        try:
            pump_info = self.pumps[pump_id]
            manager = self.managers.get(pump_info.com_port)
            if not manager:
                manager = TwoWireManagerRegistry.get_manager(pump_info.com_port)
                self.managers[pump_info.com_port] = manager

            return manager.get_pump_status(pump_info.address, pump_id)
        except Exception as e:
            self.logger.error(f"Error getting status for pump {pump_id}: {str(e)}")
            return None

    def get_transaction_data(self, pump_id: int) -> Optional[TransactionData]:
        """Get transaction data for a specific pump"""
        if pump_id not in self.pumps:
            return None

        try:
            pump_info = self.pumps[pump_id]
            manager = self.managers.get(pump_info.com_port)
            if not manager:
                manager = TwoWireManagerRegistry.get_manager(pump_info.com_port)
                self.managers[pump_info.com_port] = manager

            return manager.get_transaction_data(pump_info.address, pump_id)
        except Exception as e:
            self.logger.error(
                f"Error getting transaction data for pump {pump_id}: {str(e)}"
            )
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

    def connect_all_ports(self) -> Dict[str, bool]:
        """Connect to all COM ports used by managed pumps"""
        results = {}

        # Get unique COM ports
        com_ports = set(pump_info.com_port for pump_info in self.pumps.values())

        for com_port in com_ports:
            manager = self.managers.get(com_port)
            if not manager:
                manager = TwoWireManagerRegistry.get_manager(com_port)
                self.managers[com_port] = manager

            success = manager.connect()
            results[com_port] = success
            self.logger.info(
                f"COM port {com_port}: {'Connected' if success else 'Failed to connect'}"
            )

        return results

    def disconnect_all_ports(self):
        """Disconnect from all COM ports"""
        TwoWireManagerRegistry.disconnect_all()
        self.managers.clear()
        self.logger.info("Disconnected from all COM ports")

    def connect_port(self, com_port: str) -> bool:
        """Connect to a specific COM port"""
        manager = self.managers.get(com_port)
        if not manager:
            manager = TwoWireManagerRegistry.get_manager(com_port)
            self.managers[com_port] = manager

        success = manager.connect()
        self.logger.info(
            f"COM port {com_port}: {'Connected' if success else 'Failed to connect'}"
        )
        return success

    def disconnect_port(self, com_port: str) -> bool:
        """Disconnect from a specific COM port"""
        manager = self.managers.get(com_port)
        if manager:
            manager.disconnect()
            self.logger.info(f"Disconnected from COM port {com_port}")
            return True
        return False

    def get_connected_ports(self) -> List[str]:
        """Get list of currently connected COM ports"""
        connected = []
        for com_port, manager in self.managers.items():
            if manager.connection.is_connected:
                connected.append(com_port)
        return connected

    def shutdown(self):
        """Shutdown pump manager"""
        self.logger.info("Shutting down pump manager...")
        self.disconnect_all_ports()
        self.executor.shutdown(wait=True)
        self.logger.info("Pump manager shutdown complete")
