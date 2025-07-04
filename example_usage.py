#!/usr/bin/env python3
"""
Example script demonstrating how to use the Gilbarco SK700-II Control System
"""

import asyncio
import requests
import time
import json
from typing import Dict, Any

# API base URL
BASE_URL = "http://localhost:8000"


def print_response(title: str, response: requests.Response):
    """Helper function to print API responses"""
    print(f"\n=== {title} ===")
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        try:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2, default=str)}")
        except:
            print(f"Response: {response.text}")
    else:
        print(f"Error: {response.text}")


def check_api_health():
    """Check if the API is running"""
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        print_response("API Health Check", response)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"API not available: {e}")
        return False


def discover_pumps(com_ports=None, address_range=(1, 8)):
    """Discover pumps on specified COM ports"""
    params = {
        "address_range_start": address_range[0],
        "address_range_end": address_range[1],
        "timeout": 2.0
    }
    
    if com_ports:
        # Convert to query parameter format
        params["com_ports"] = com_ports
    
    try:
        response = requests.post(f"{BASE_URL}/api/pumps/discover", params=params, timeout=30)
        print_response("Pump Discovery", response)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("discovered_pumps", [])
        
    except requests.exceptions.RequestException as e:
        print(f"Discovery failed: {e}")
    
    return []


def get_all_pumps():
    """Get list of all managed pumps"""
    try:
        response = requests.get(f"{BASE_URL}/api/pumps")
        print_response("All Pumps", response)
        
        if response.status_code == 200:
            return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to get pumps: {e}")
    
    return []


def get_pump_status(pump_id: int):
    """Get status of a specific pump"""
    try:
        response = requests.get(f"{BASE_URL}/api/pumps/{pump_id}/status")
        print_response(f"Pump {pump_id} Status", response)
        
        if response.status_code == 200:
            return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to get pump {pump_id} status: {e}")
    
    return None


def get_all_pump_statuses():
    """Get status of all pumps"""
    try:
        response = requests.get(f"{BASE_URL}/api/pumps/status")
        print_response("All Pump Statuses", response)
        
        if response.status_code == 200:
            return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to get pump statuses: {e}")
    
    return {}


def connect_to_pump(pump_id: int):
    """Connect to a specific pump"""
    try:
        response = requests.post(f"{BASE_URL}/api/pumps/{pump_id}/connect")
        print_response(f"Connect to Pump {pump_id}", response)
        return response.status_code == 200
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to connect to pump {pump_id}: {e}")
        return False


def disconnect_from_pump(pump_id: int):
    """Disconnect from a specific pump"""
    try:
        response = requests.post(f"{BASE_URL}/api/pumps/{pump_id}/disconnect")
        print_response(f"Disconnect from Pump {pump_id}", response)
        return response.status_code == 200
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to disconnect from pump {pump_id}: {e}")
        return False


def connect_all_pumps():
    """Connect to all pumps"""
    try:
        response = requests.post(f"{BASE_URL}/api/pumps/connect-all")
        print_response("Connect to All Pumps", response)
        return response.status_code == 200
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to connect to all pumps: {e}")
        return False


def monitor_pumps(duration_seconds: int = 60):
    """Monitor pump statuses for a specified duration"""
    print(f"\n=== Monitoring Pumps for {duration_seconds} seconds ===")
    
    start_time = time.time()
    while time.time() - start_time < duration_seconds:
        statuses = get_all_pump_statuses()
        
        if statuses:
            print(f"\n--- Status Update at {time.strftime('%H:%M:%S')} ---")
            for pump_id, status in statuses.items():
                print(f"Pump {pump_id}: {status['status']} (Updated: {status['last_updated']})")
        
        time.sleep(10)  # Check every 10 seconds


def main():
    """Main example workflow"""
    print("Gilbarco SK700-II Control System - Example Usage")
    print("=" * 50)
    
    # Step 1: Check API health
    if not check_api_health():
        print("API is not available. Please start the server with: python main.py")
        return
    
    # Step 2: Discover pumps
    print("\n1. Discovering pumps...")
    discovered_pumps = discover_pumps(
        com_ports=["COM1", "COM2", "COM3"],  # Specify your COM ports
        address_range=(1, 4)  # Check addresses 1-4
    )
    
    if not discovered_pumps:
        print("No pumps discovered. Please check your connections and try again.")
        # For demo purposes, let's continue anyway
        print("Continuing with existing pumps...")
    
    # Step 3: Get all managed pumps
    print("\n2. Getting all managed pumps...")
    all_pumps = get_all_pumps()
    
    if not all_pumps:
        print("No pumps are currently managed.")
        return
    
    # Step 4: Connect to all pumps
    print("\n3. Connecting to all pumps...")
    connect_all_pumps()
    
    # Step 5: Get individual pump status
    print("\n4. Getting individual pump statuses...")
    for pump in all_pumps:
        pump_id = pump["pump_id"]
        get_pump_status(pump_id)
    
    # Step 6: Get all pump statuses
    print("\n5. Getting all pump statuses...")
    get_all_pump_statuses()
    
    # Step 7: Monitor pumps (optional)
    monitor_choice = input("\nWould you like to monitor pumps for 30 seconds? (y/n): ")
    if monitor_choice.lower() == 'y':
        monitor_pumps(30)
    
    # Step 8: Disconnect from all pumps
    print("\n6. Disconnecting from all pumps...")
    response = requests.post(f"{BASE_URL}/api/pumps/disconnect-all")
    print_response("Disconnect All", response)
    
    print("\nExample completed!")


def interactive_mode():
    """Interactive mode for manual testing"""
    print("\nInteractive Mode - Available Commands:")
    print("1. health - Check API health")
    print("2. discover - Discover pumps")
    print("3. list - List all pumps")
    print("4. status <pump_id> - Get pump status")
    print("5. status-all - Get all pump statuses")
    print("6. connect <pump_id> - Connect to pump")
    print("7. disconnect <pump_id> - Disconnect from pump")
    print("8. connect-all - Connect to all pumps")
    print("9. disconnect-all - Disconnect from all pumps")
    print("10. monitor <seconds> - Monitor pumps")
    print("11. quit - Exit")
    
    while True:
        try:
            command = input("\nEnter command: ").strip().split()
            
            if not command:
                continue
            
            cmd = command[0].lower()
            
            if cmd == "quit":
                break
            elif cmd == "health":
                check_api_health()
            elif cmd == "discover":
                discover_pumps()
            elif cmd == "list":
                get_all_pumps()
            elif cmd == "status":
                if len(command) > 1:
                    pump_id = int(command[1])
                    get_pump_status(pump_id)
                else:
                    print("Usage: status <pump_id>")
            elif cmd == "status-all":
                get_all_pump_statuses()
            elif cmd == "connect":
                if len(command) > 1:
                    pump_id = int(command[1])
                    connect_to_pump(pump_id)
                else:
                    print("Usage: connect <pump_id>")
            elif cmd == "disconnect":
                if len(command) > 1:
                    pump_id = int(command[1])
                    disconnect_from_pump(pump_id)
                else:
                    print("Usage: disconnect <pump_id>")
            elif cmd == "connect-all":
                connect_all_pumps()
            elif cmd == "disconnect-all":
                response = requests.post(f"{BASE_URL}/api/pumps/disconnect-all")
                print_response("Disconnect All", response)
            elif cmd == "monitor":
                duration = 30
                if len(command) > 1:
                    duration = int(command[1])
                monitor_pumps(duration)
            else:
                print(f"Unknown command: {cmd}")
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_mode()
    else:
        main()
