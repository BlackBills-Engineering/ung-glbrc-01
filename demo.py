#!/usr/bin/env python3
"""
Demo script to test the Gilbarco SK700-II API
"""

import requests
import json
import time
from datetime import datetime

# API base URL
BASE_URL = "http://localhost:8000"

def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)

def print_response(response, title="Response"):
    """Print formatted response"""
    print(f"\n{title}:")
    print(f"Status Code: {response.status_code}")
    try:
        data = response.json()
        print("Response Data:")
        print(json.dumps(data, indent=2, default=str))
    except:
        print("Response Text:", response.text)

def test_api_health():
    """Test API health endpoint"""
    print_header("Testing API Health")
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        print_response(response, "Health Check")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_pump_discovery():
    """Test pump discovery"""
    print_header("Testing Pump Discovery")
    
    try:
        # Test discovery with mock COM ports
        discovery_data = {
            "com_ports": ["COM1", "COM2", "COM3"],  # These likely don't exist but that's OK for testing
            "min_address": 1,
            "max_address": 4,
            "timeout": 1.0
        }
        
        response = requests.post(
            f"{BASE_URL}/pumps/discover",
            json=discovery_data
        )
        print_response(response, "Pump Discovery")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n📊 Discovery Results:")
            print(f"   Total found: {data.get('total_found', 0)}")
            print(f"   Scan duration: {data.get('scan_duration', 0):.2f}s")
            return True
        else:
            print("❌ Discovery failed")
            return False
            
    except Exception as e:
        print(f"❌ Discovery test failed: {e}")
        return False

def test_manual_pump_addition():
    """Test manually adding a pump"""
    print_header("Testing Manual Pump Addition")
    
    try:
        # Add a test pump
        pump_data = {
            "pump_id": 1,
            "address": 1,
            "com_port": "COM99",  # Non-existent port for testing
            "name": "Test Pump 1",
            "is_connected": False
        }
        
        response = requests.post(
            f"{BASE_URL}/pumps",
            json=pump_data
        )
        print_response(response, "Add Pump")
        
        return response.status_code in [200, 201]
        
    except Exception as e:
        print(f"❌ Manual pump addition failed: {e}")
        return False

def test_get_pumps():
    """Test getting all pumps"""
    print_header("Testing Get All Pumps")
    
    try:
        response = requests.get(f"{BASE_URL}/pumps")
        print_response(response, "Get All Pumps")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n📊 Found {len(data)} pumps in system")
            for pump in data:
                print(f"   Pump {pump['pump_id']}: {pump['name']} on {pump['com_port']}")
            return True
        else:
            return False
            
    except Exception as e:
        print(f"❌ Get pumps test failed: {e}")
        return False

def test_pump_status():
    """Test getting pump status"""
    print_header("Testing Pump Status")
    
    try:
        # Get all pump statuses
        response = requests.get(f"{BASE_URL}/pumps/status")
        print_response(response, "All Pump Statuses")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n📊 Status for {len(data)} pumps:")
            for status in data:
                print(f"   Pump {status['pump_id']}: {status['status']}")
                if status.get('error_message'):
                    print(f"      Error: {status['error_message']}")
        
        # Test specific pump status (if pump 1 exists)
        response = requests.get(f"{BASE_URL}/pumps/1/status")
        if response.status_code == 200:
            print_response(response, "Pump 1 Status")
        
        return True
        
    except Exception as e:
        print(f"❌ Pump status test failed: {e}")
        return False

def test_pump_connection():
    """Test pump connection"""
    print_header("Testing Pump Connection")
    
    try:
        # Try to connect to pump 1 (will fail since COM99 doesn't exist, but tests the API)
        response = requests.post(f"{BASE_URL}/pumps/1/connect")
        print_response(response, "Connect to Pump 1")
        
        # Test connect all
        response = requests.post(f"{BASE_URL}/pumps/connect-all")
        print_response(response, "Connect All Pumps")
        
        return True
        
    except Exception as e:
        print(f"❌ Pump connection test failed: {e}")
        return False

def test_api_documentation():
    """Test API documentation endpoints"""
    print_header("Testing API Documentation")
    
    try:
        # Test OpenAPI spec
        response = requests.get(f"{BASE_URL}/openapi.json")
        print(f"OpenAPI Spec: Status {response.status_code}")
        
        # Test docs page (just check if it's accessible)
        response = requests.get(f"{BASE_URL}/docs")
        print(f"Swagger UI: Status {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"❌ Documentation test failed: {e}")
        return False

def cleanup_test_data():
    """Remove test pump"""
    print_header("Cleanup Test Data")
    
    try:
        response = requests.delete(f"{BASE_URL}/pumps/1")
        print_response(response, "Remove Test Pump")
        return True
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        return False

def main():
    """Run all API tests"""
    print("🚗 Gilbarco SK700-II API Demo & Test Suite")
    print(f"Testing API at: {BASE_URL}")
    print(f"Time: {datetime.now()}")
    
    tests = [
        ("API Health", test_api_health),
        ("Pump Discovery", test_pump_discovery),
        ("Manual Pump Addition", test_manual_pump_addition),
        ("Get Pumps", test_get_pumps),
        ("Pump Status", test_pump_status),
        ("Pump Connection", test_pump_connection),
        ("API Documentation", test_api_documentation),
        ("Cleanup", cleanup_test_data),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            if test_func():
                print(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print_header("Test Results")
    print(f"Passed: {passed}/{total}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} tests failed")
    
    print(f"\n📖 View API documentation: {BASE_URL}/docs")
    print(f"🔧 Alternative docs: {BASE_URL}/redoc")

if __name__ == "__main__":
    # Give the server a moment to start up
    print("Waiting for server to be ready...")
    time.sleep(2)
    
    main()
