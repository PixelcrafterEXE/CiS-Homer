import serial
from serial.tools import list_ports
import re
import time
import threading

import numpy as np
from matplotlib.figure import Figure

def listPorts():
    '''gets all serial ports with attached devices'''
    return [port for port in list_ports.comports()]

class Sensor:
    def __init__(self, port: str = "auto", baud: int = 115200, device_id: str = "ALSKDJALSDKLKB"):
        self.port = port
        self.baud = baud
        self.device_id = device_id
        
        self.ser = None

        self._running = True
        self._timer = None
        self._pollSerial()

    def setBaud(self, baud: int):
        self.baud = baud
    
    def setPort(self, port: str):
        self.port = port
    
    def setDeviceID(self, device_id: str):
        self.device_id = device_id

    def stop(self):
        self._running = False
        if self._timer is not None:
            self._timer.cancel()
        
        #close serial connection if exists and open
        if self.ser is not None and self.ser.is_open:
            self.ser.close()

    def __del__(self):
        self.stop()
    
    def _pollSerial(self):
        '''runs scheduled to check for available devices if connection doesnt exist yet;'''
        if not self._running:
            return

        if self.ser is None:
            if self.port == "auto":
                ports = listPorts()
            else: 
                ports = [self.port]
            for port in ports:
                if self.device_id and self.device_id not in str(port.hwid):
                    continue
                try:
                    ser = serial.Serial(port.device, self.baud, timeout=1)
                    ser.write(b"r")
                    ser.flush()
                    time.sleep(0.1)
                    if ser.in_waiting > 0:
                        self.ser = ser
                        print(f"Connected to sensor on {port.device}")
                        break
                    else:
                        ser.close()
                except (serial.SerialException, OSError) as e:
                    print(f"Failed to connect to {port.device}: {e}")
        elif not self.ser.is_open:
            self.ser = None
        #todo: disconnect detection, timeout, etc. to set self.ser = None if connection is lost
        
        #rerun after 100ms
        if self._running:
            self._timer = threading.Timer(0.1, self._pollSerial)
            self._timer.start()
    
    def getRaw(self):
        ser = self.ser
        if ser is None or not ser.is_open:
            raise RuntimeError("Serial connection is not open.")

        # Discard stale bytes and request one raw frame.
        ser.reset_input_buffer()
        ser.write(b"r")
        ser.flush()

        # Parse tokens of the form "<channel>:<value>" until all 64 channels are available.
        pattern = re.compile(r"(\d+)\s*:\s*(\d+)")
        values = {}
        remainder = ""

        try:
            deadline = time.monotonic() + 3.0
            while len(values) < 64 and time.monotonic() < deadline:
                chunk = ser.read(ser.in_waiting or 1)
                if not chunk:
                    continue

                text = remainder + chunk.decode("ascii", errors="ignore")
                parts = re.split(r"[\r\n]+", text)
                remainder = parts.pop() if parts else ""

                for token in parts:
                    m = pattern.search(token)
                    if not m:
                        continue
                    idx = int(m.group(1))
                    val = int(m.group(2))
                    if 1 <= idx <= 64:
                        values[idx] = val

            if len(values) != 64:
                missing = [i for i in range(1, 65) if i not in values]
                raise ValueError(f"Incomplete sensor frame, missing channels: {missing}")

            return np.array([values[i] for i in range(1, 65)], dtype=np.uint16)
        except Exception as e:
            raise RuntimeError(f"Failed to read sensor data: {e}")

    def getMap(self):
        pass


    def plotMesh(self):
        pass

    def plotBar(self):
        pass

    def plotTable(self):
        pass
            