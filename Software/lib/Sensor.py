import serial
from serial.tools import list_ports
import re
import time

import numpy as np
from matplotlib.figure import Figure

def listPorts():
    '''gets all serial ports with attached devices'''
    return [port for port in list_ports.comports()]

class Sensor:
    def __init__(self, port: str = "auto", baud: int = 115200):
        
        #serial port handeling:
        self.ser = None
        if port == "auto":
            # Search all ports; prefer likely USB serial devices.
            port = None
            for p in listPorts():
                if p.hwid.startswith("USB VID:PID="):
                    port = p.device
                    break
        if port is None:
            raise RuntimeError("No compatible serial sensor found. Provide a port explicitly.")

        try:
            self.ser = serial.Serial(port, baud)
            if not self.ser.is_open:
                self.ser.open()
        except (serial.SerialException, OSError):
            self.ser = None

    def __del__(self):   
        #close serial connection if exists and open
        ser = getattr(self, "ser", None)
        if ser is not None and ser.is_open:
            ser.close()
    
    def getRaw(self):
        ser = getattr(self, "ser", None)
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

        old_timeout = ser.timeout
        if old_timeout is None:
            ser.timeout = 1.0

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
        finally:
            ser.timeout = old_timeout

    def getMap(self):
        pass


    def plotMesh(self):
        pass

    def plotBar(self):
        pass

    def plotTable(self):
        pass
            