#!/usr/bin/env python3
"""
SDS011 Sensor Test Script
This script helps diagnose SDS011 sensor connection issues.
"""

import serial
import serial.tools.list_ports
import time
import sys

def test_com_ports():
    """Test all available COM ports for SDS011 sensor"""
    print("Scanning for SDS011 sensor...")
    print("=" * 50)
    
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("ERROR: No COM ports found!")
        print("\nTroubleshooting:")
        print("  • Check if sensor is connected via USB")
        print("  • Install USB-to-serial driver (CH340/CP2102)")
        print("  • Try different USB port")
        return None
    
    print(f"Found {len(ports)} COM port(s):")
    for i, port in enumerate(ports, 1):
        print(f"  {i}. {port.device} - {port.description}")
    
    print("\nTesting each port for SDS011 sensor...")
    print("-" * 50)
    
    for port in ports:
        print(f"\nTesting {port.device}...")
        try:
            with serial.Serial(port.device, 9600, timeout=2) as ser:
                print(f"  OK: Port {port.device} is accessible")
                
                # Clear buffer
                ser.flushInput()
                ser.flushOutput()
                
                # Try to read data
                print(f"  Attempting to read sensor data...")
                data = ser.read(10)
                
                if len(data) == 10:
                    print(f"  Received {len(data)} bytes: {data.hex()}")
                    
                    # Check SDS011 protocol
                    if data[0] == 0xAA and data[1] == 0xC0:
                        pm2_5 = (data[2] + data[3]*256) / 10.0
                        pm10 = (data[4] + data[5]*256) / 10.0
                        print(f"  SUCCESS: SDS011 sensor detected!")
                        print(f"     PM2.5: {pm2_5:.1f} ug/m3")
                        print(f"     PM10:  {pm10:.1f} ug/m3")
                        return port.device
                    else:
                        print(f"  ERROR: Not SDS011 protocol (expected 0xAA 0xC0)")
                else:
                    print(f"  WARNING: Received {len(data)} bytes (expected 10)")
                    
        except serial.SerialException as e:
            print(f"  ERROR: Serial error: {e}")
        except Exception as e:
            print(f"  ERROR: {e}")
    
    print(f"\nERROR: No SDS011 sensor found on any port")
    return None

def test_sensor_reading(port):
    """Test continuous reading from sensor"""
    print(f"\nTesting continuous reading from {port}...")
    print("Press Ctrl+C to stop")
    print("-" * 50)
    
    try:
        with serial.Serial(port, 9600, timeout=3) as ser:
            count = 0
            while True:
                data = ser.read(10)
                if len(data) == 10 and data[0] == 0xAA and data[1] == 0xC0:
                    pm2_5 = (data[2] + data[3]*256) / 10.0
                    pm10 = (data[4] + data[5]*256) / 10.0
                    count += 1
                    print(f"Reading {count:3d}: PM2.5={pm2_5:5.1f} ug/m3, PM10={pm10:5.1f} ug/m3")
                else:
                    print(f"Invalid data: {data.hex() if data else 'No data'}")
                time.sleep(1)
                
    except KeyboardInterrupt:
        print(f"\nSUCCESS: Test completed successfully!")
    except Exception as e:
        print(f"\nERROR: Error during reading: {e}")

if __name__ == "__main__":
    print("SDS011 Sensor Diagnostic Tool")
    print("=" * 50)
    
    # Test COM ports
    sensor_port = test_com_ports()
    
    if sensor_port:
        print(f"\nSUCCESS: SDS011 sensor found on {sensor_port}!")
        
        # Ask user if they want to test continuous reading
        try:
            response = input("\nTest continuous reading? (y/n): ").lower()
            if response in ['y', 'yes']:
                test_sensor_reading(sensor_port)
        except KeyboardInterrupt:
            print(f"\nSUCCESS: Test completed!")
    else:
        print(f"\nERROR: No SDS011 sensor detected!")
        print(f"\nNext steps:")
        print(f"  1. Check sensor connection")
        print(f"  2. Install USB-to-serial driver")
        print(f"  3. Try different USB port")
        print(f"  4. Check sensor power")
        sys.exit(1)
