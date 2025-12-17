import serial
import struct
import time
from datetime import datetime

class SDS011:
    def __init__(self, port="COM3", baudrate=9600, timeout=2):
        try:
            self.ser = serial.Serial(port, baudrate=baudrate, timeout=timeout)
            print(f"✅ SDS011 connected on {port}")
        except Exception as e:
            print(f"❌ Error connecting to SDS011: {e}")
            self.ser = None

    def read(self):
        if self.ser is None:
            return None, None

        while True:
            byte = self.ser.read(1)
            if byte == b"\xaa":  # Start frame
                data = self.ser.read(9)
                if len(data) < 9:
                    continue
                if data[0] == 0xc0:  # Data frame
                    pm25 = (data[1] + data[2] * 256) / 10.0
                    pm10 = (data[3] + data[4] * 256) / 10.0
                    return pm25, pm10

    def close(self):
        if self.ser:
            self.ser.close()

if __name__ == "__main__":
    sensor = SDS011(port="COM3")  # Change COM port if needed

    try:
        while True:
            pm25, pm10 = sensor.read()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print("\n-------------------------------")
            print(f"⏳ Time: {timestamp}")
            print(f"🌫 PM2.5: {pm25} µg/m³ (Fine Particles)")
            print(f"🌪 PM10: {pm10} µg/m³ (Coarse Particles)")
            print("-------------------------------")
            time.sleep(10)  # reading every 10 seconds
    except KeyboardInterrupt:
        print("\n✅ Stopped reading.")
        sensor.close()
