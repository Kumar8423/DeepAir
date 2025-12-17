#!/usr/bin/env python3
"""
SDS011 Sensor Fix Script
This script implements proper SDS011 wake-up and communication protocol.
"""

import serial
import serial.tools.list_ports
import time
import sys

def wake_sds011(ser):
    """Send wake command to SDS011 sensor"""
    # SDS011 wake command: AA B4 06 01 01 00 00 00 00 00 00 00 00 00 00 FF FF 06 AB
    wake_cmd = bytes([0xAA, 0xB4, 0x06, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0x06, 0xAB])
    ser.write(wake_cmd)
    time.sleep(0.1)

def set_sds011_continuous_mode(ser):
    """Set SDS011 to continuous reporting mode"""
    # Set reporting mode to continuous: AA B4 02 02 00 00 00 00 00 00 00 00 00 00 00 FF FF 02 AB
    continuous_cmd = bytes([0xAA, 0xB4, 0x02, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0x02, 0xAB])
    ser.write(continuous_cmd)
    time.sleep(0.1)

def read_sds011_data(ser):
    """Read data from SDS011 sensor with proper protocol"""
    # Clear any existing data
    ser.flushInput()
    ser.flushOutput()
    
    # Wait for start byte (0xAA)
    start_byte = ser.read(1)
    if not start_byte or start_byte[0] != 0xAA:
        return None, None
    
    # Read the rest of the data packet
    data = ser.read(9)
    if len(data) < 9:
        return None, None
    
    # Check if it's a data packet (0xC0)
    if data[0] != 0xC0:
        return None, None
    
    # Parse PM2.5 and PM10 values
    pm2_5 = (data[1] + data[2] * 256) / 10.0
    pm10 = (data[3] + data[4] * 256) / 10.0
    
    return pm2_5, pm10

def test_sds011_with_proper_protocol():
    """Test SDS011 with proper wake-up and communication protocol"""
    print("SDS011 Sensor Fix Tool")
    print("=" * 50)
    
    # Find COM ports
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("ERROR: No COM ports found!")
        return None
    
    print(f"Found {len(ports)} COM port(s):")
    for port in ports:
        print(f"  - {port.device}: {port.description}")
    
    # Try each port
    for port in ports:
        print(f"\nTesting {port.device}...")
        try:
            with serial.Serial(port.device, 9600, timeout=5) as ser:
                print(f"  Connected to {port.device}")
                
                # Step 1: Wake up the sensor
                print(f"  Step 1: Waking up sensor...")
                wake_sds011(ser)
                time.sleep(1)
                
                # Step 2: Set continuous mode
                print(f"  Step 2: Setting continuous mode...")
                set_sds011_continuous_mode(ser)
                time.sleep(1)
                
                # Step 3: Try to read data
                print(f"  Step 3: Attempting to read data...")
                
                # Try multiple times
                for attempt in range(5):
                    pm2_5, pm10 = read_sds011_data(ser)
                    if pm2_5 is not None and pm10 is not None:
                        print(f"  SUCCESS: SDS011 sensor working!")
                        print(f"    PM2.5: {pm2_5:.1f} ug/m3")
                        print(f"    PM10:  {pm10:.1f} ug/m3")
                        return port.device
                    else:
                        print(f"    Attempt {attempt + 1}: No valid data")
                        time.sleep(0.5)
                
                print(f"  ERROR: Could not read valid data from sensor")
                
        except serial.SerialException as e:
            print(f"  ERROR: Serial error: {e}")
        except Exception as e:
            print(f"  ERROR: {e}")
    
    print(f"\nERROR: No working SDS011 sensor found")
    return None

def continuous_test(port):
    """Test continuous reading with proper protocol"""
    print(f"\nTesting continuous reading from {port}...")
    print("Press Ctrl+C to stop")
    print("-" * 50)
    
    try:
        with serial.Serial(port, 9600, timeout=5) as ser:
            # Initialize sensor
            wake_sds011(ser)
            time.sleep(1)
            set_sds011_continuous_mode(ser)
            time.sleep(1)
            
            count = 0
            while True:
                pm2_5, pm10 = read_sds011_data(ser)
                if pm2_5 is not None and pm10 is not None:
                    count += 1
                    print(f"Reading {count:3d}: PM2.5={pm2_5:5.1f} ug/m3, PM10={pm10:5.1f} ug/m3")
                else:
                    print("No valid data received")
                time.sleep(2)
                
    except KeyboardInterrupt:
        print(f"\nSUCCESS: Test completed!")
    except Exception as e:
        print(f"\nERROR: {e}")

if __name__ == "__main__":
    sensor_port = test_sds011_with_proper_protocol()
    
    if sensor_port:
        print(f"\nSUCCESS: SDS011 sensor found on {sensor_port}!")
        
        try:
            response = input("\nTest continuous reading? (y/n): ").lower()
            if response in ['y', 'yes']:
                continuous_test(sensor_port)
        except KeyboardInterrupt:
            print(f"\nSUCCESS: Test completed!")
        except EOFError:
            # Handle case when running non-interactively
            print(f"\nSUCCESS: Sensor detected on {sensor_port}!")
    else:
        print(f"\nERROR: No working SDS011 sensor found!")
        print(f"\nTroubleshooting steps:")
        print(f"  1. Ensure sensor is connected and powered")
        print(f"  2. Check USB cable (try different cable)")
        print(f"  3. Install CH340 driver if not already installed")
        print(f"  4. Try different USB port")
        print(f"  5. Wait 30 seconds after connecting before testing")
        sys.exit(1)
