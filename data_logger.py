import serial
import serial.tools.list_ports
import struct
import time
import csv
import os
from datetime import datetime
import sys
import requests

# ---------------------------------------------------
# Configuration
# ---------------------------------------------------
BAUD_RATE = 9600
CSV_FILE = "air_quality_log.csv"
LOG_INTERVAL = 5  # seconds
GRAPH_WIDTH = 50

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"

# ---------------------------------------------------
# Initialize CSV with headers
# ---------------------------------------------------
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([
            "timestamp", "pm2_5", "pm10", "temperature", "humidity",
            "latitude", "longitude", "AQI_Level", "Category"
        ])

# Keep last readings for ASCII graph
pm2_5_history = []
pm10_history = []

# ---------------------------------------------------
# Utility Functions
# ---------------------------------------------------
def get_location():
    """Fetch approximate latitude and longitude using IP."""
    try:
        response = requests.get("https://ipinfo.io/json", timeout=5)
        data = response.json()
        loc = data.get("loc", "0,0").split(",")
        return float(loc[0]), float(loc[1])
    except Exception:
        return None, None


def compute_aqi(pm2_5):
    """Compute approximate AQI and category based on PM2.5."""
    if pm2_5 <= 12:
        return 50, "Good"
    elif pm2_5 <= 35.4:
        return 100, "Moderate"
    elif pm2_5 <= 55.4:
        return 150, "Unhealthy for Sensitive Groups"
    elif pm2_5 <= 150.4:
        return 200, "Unhealthy"
    elif pm2_5 <= 250.4:
        return 300, "Very Unhealthy"
    else:
        return 400, "Hazardous"


def color_bar(value):
    """Return color code based on AQI level."""
    if value <= 50:
        return GREEN
    elif value <= 100:
        return YELLOW
    else:
        return RED


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


def find_sds011_port():
    """Auto-detect SDS011 sensor port with proper protocol"""
    ports = serial.tools.list_ports.comports()
    if not ports:
        return None

    print(f"{BLUE}🔍 Scanning for SDS011 sensor...{RESET}")
    for port in ports:
        try:
            with serial.Serial(port.device, BAUD_RATE, timeout=3) as ser:
                # Wake up sensor
                wake_sds011(ser)
                time.sleep(1)
                
                # Set continuous mode
                set_sds011_continuous_mode(ser)
                time.sleep(1)
                
                # Try to read data to verify it's working
                for attempt in range(3):
                    data = ser.read(10)
                    if len(data) == 10 and data[0] == 0xAA and data[1] == 0xC0:
                        pm2_5 = (data[2] + data[3]*256) / 10.0
                        pm10 = (data[4] + data[5]*256) / 10.0
                        print(f"  ✅ SDS011 detected on {port.device} (PM2.5: {pm2_5:.1f}, PM10: {pm10:.1f})")
                        return port.device
                    time.sleep(0.5)
        except Exception:
            continue
    return None


def read_sds011(port, ser=None):
    """Read PM2.5 and PM10 from SDS011 sensor"""
    if port is None:
        return None, None, "No sensor port available"

    try:
        # Use existing serial connection or create new one
        if ser is None:
            ser = serial.Serial(port, BAUD_RATE, timeout=3)
            should_close = True
        else:
            should_close = False
        
        # Clear buffer
        ser.flushInput()
        ser.flushOutput()
        
        # Read data with multiple attempts
        for attempt in range(3):
            data = ser.read(10)
            if len(data) == 10 and data[0] == 0xAA and data[1] == 0xC0:
                pm25 = (data[2] + data[3] * 256) / 10.0
                pm10 = (data[4] + data[5] * 256) / 10.0
                if should_close:
                    ser.close()
                return pm25, pm10, "Success"
            time.sleep(0.1)
        
        if should_close:
            ser.close()
    except Exception as e:
        return None, None, f"Error: {e}"

    return None, None, "Read failed"


def draw_graph(history, label):
    """Return colored ASCII graph string for given history"""
    if not history:
        return ""
    max_val = max(max(history), 1)
    scale = GRAPH_WIDTH / max_val
    graph_str = ""
    for val in history:
        color = color_bar(val)
        graph_str += color + "█" * int(val * scale) + RESET + "\n"
    return f"{label}: {graph_str}"


# ---------------------------------------------------
# Main Logging Process
# ---------------------------------------------------
sensor_port = find_sds011_port()

if sensor_port is None:
    print(f"{RED}❌ No SDS011 sensor found!{RESET}")
    print(f"{YELLOW}Please check:{RESET}")
    print("1. Sensor connected via USB")
    print("2. USB-to-serial driver installed")
    print("3. Sensor powered ON")
    print("4. Try a different USB port")
    sys.exit(1)

print(f"{GREEN}✅ SDS011 sensor found on {sensor_port}{RESET}")
print(f"{BLUE}🟢 Logging SDS011 data every {LOG_INTERVAL}s (Press Ctrl+C to stop)\n{RESET}")

lat, lon = get_location()

# Initialize sensor connection once
sensor_ser = None
try:
    sensor_ser = serial.Serial(sensor_port, BAUD_RATE, timeout=3)
    wake_sds011(sensor_ser)
    time.sleep(1)
    set_sds011_continuous_mode(sensor_ser)
    time.sleep(1)
except Exception as e:
    print(f"{RED}Error initializing sensor: {e}{RESET}")
    sys.exit(1)

try:
    while True:
        pm2_5, pm10, status = read_sds011(sensor_port, sensor_ser)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if pm2_5 is not None and pm10 is not None:
            aqi_value, category = compute_aqi(pm2_5)

            # Save to CSV
            row = [timestamp, pm2_5, pm10, "", "", lat, lon, aqi_value, category]
            with open(CSV_FILE, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(row)

            # Update graph history
            pm2_5_history.append(pm2_5)
            pm10_history.append(pm10)
            if len(pm2_5_history) > GRAPH_WIDTH:
                pm2_5_history.pop(0)
                pm10_history.pop(0)

            # Build live output
            output = f"\n🕒 {timestamp}\n"
            output += f"PM2.5: {pm2_5:.1f} µg/m³ | PM10: {pm10:.1f} µg/m³\n"
            output += f"AQI: {aqi_value} ({category})\n"
            if lat and lon:
                output += f"📍 Location: {lat}, {lon}\n"
            output += draw_graph(pm2_5_history, "PM2.5") + "\n"
            output += draw_graph(pm10_history, "PM10") + "\n"

        else:
            output = f"\n⚠️ Sensor read failed: {status}\n"
            output += f"{YELLOW}Troubleshooting:{RESET}\n"
            output += " - Check sensor connection\n"
            output += " - Ensure sensor is powered ON\n"
            output += " - Try reconnecting USB cable\n"

        # Clear terminal and display
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.write(output)
        sys.stdout.flush()

        time.sleep(LOG_INTERVAL)

except KeyboardInterrupt:
    print(f"\n{BLUE}🛑 Logging stopped by user.{RESET}")
finally:
    if sensor_ser and sensor_ser.is_open:
        sensor_ser.close()