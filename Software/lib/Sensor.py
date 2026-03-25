import serial
from serial.tools import list_ports
import re
import time
import threading

import numpy as np

positions = [
    (2, 0),   # 1
    (2, -1),  # 2
    (1, -4),  # 3
    (0, 3),   # 4
    (-1, -1), # 5
    (-2, -3), # 6
    (-4, -1), # 7
    None,     # 8 (NTC)
    (2, 1),   # 9
    (3, -1),  # 10
    (1, -3),  # 11
    (0, 2),   # 12
    (-1, 0),  # 13
    (-3, -3), # 14
    (-4, 0),  # 15
    (-3, 2),  # 16
    (2, 2),   # 17
    (1, 0),   # 18
    (-1, -2), # 19
    (0, 4),   # 20
    (-1, 1),  # 21
    (-3, -2), # 22
    (-4, 1),  # 23
    (-2, 2),  # 24
    (2, 3),   # 25
    (1, 1),   # 26
    (0, -2),  # 27
    (-1, 4),  # 28
    (0, 0),   # 29
    (-3, -1), # 30
    (-3, 0),  # 31
    (-3, 3),  # 32
    None,     # 33 (NTC)
    (4, 0),   # 34
    (3, -3),  # 35
    (1, 2),   # 36
    (0, -1),  # 37
    (-1, -4), # 38
    (-2, -2), # 39
    (-2, 1),  # 40
    (4, 1),   # 41
    (4, -1),  # 42
    (2, -3),  # 43
    (1, 3),   # 44
    (1, -2),  # 45
    (-1, -3), # 46
    (-2, -1), # 47
    (-1, 3),  # 48
    (3, 3),   # 49
    (3, 1),   # 50
    (3, -2),  # 51
    None,     # 52 (Reference Diode)
    (1, -1),  # 53
    (0, -4),  # 54
    (-2, 0),  # 55
    (-1, 2),  # 56
    (3, 2),   # 57
    (3, 0),   # 58
    (2, -2),  # 59
    (1, 4),   # 60
    (0, 1),   # 61
    (0, -3),  # 62
    (-3, 1),  # 63
    (-2, 3)   # 64
]


def listPorts() -> list:
    '''gets all serial ports with attached devices'''
    return [port for port in list_ports.comports()]

class Sensor:
    def __init__(self, port: str = "auto", baud: int = 115200, device_id: str = "0403:6015"):
        self.port = port
        self.baud = baud
        self.device_id = device_id
        
        self.ser = None

        self._running = True
        self._timer = None
        self._pollSerial()

    def _reconnect(self) -> None:
        if self.ser is not None:
            if self.ser.is_open:
                self.ser.close()
            self.ser = None

    def setBaud(self, baud: int) -> None:
        print(f"Setting baud rate to {baud}...")
        if self.baud != baud:
            self.baud = baud
            self._reconnect()
    
    def setPort(self, port: str) -> None:
        if self.port != port:
            self.port = port
            self._reconnect()
    
    def setDeviceID(self, device_id: str) -> None:
        if self.device_id != device_id:
            self.device_id = device_id
            self._reconnect()

    def stop(self) -> None:
        self._running = False
        if self._timer is not None:
            self._timer.cancel()
        
        #close serial connection if exists and open
        if self.ser is not None and self.ser.is_open:
            self.ser.close()

    def __del__(self) -> None:
        self.stop()
    
    def _pollSerial(self) -> None:
        '''runs scheduled to check for available devices if connection doesnt exist yet;'''
        if not self._running:
            return

        if self.ser is None:
            print("Attempting to (re-)connect to sensor...")
            if self.port == "auto":
                ports = listPorts()
            else: 
                ports = [self.port]
            for port_info in ports:
                device = port_info.device if hasattr(port_info, 'device') else port_info
                hwid = port_info.hwid if hasattr(port_info, 'hwid') else self.device_id

                if self.device_id and self.device_id not in str(hwid):
                    continue
                try:
                    ser = serial.Serial(device, self.baud, timeout=1)
                    ser.write(b"r")
                    ser.flush()
                    time.sleep(0.1)
                    if ser.in_waiting > 0:
                        self.ser = ser
                        print(f"Connected to sensor on {device}")
                        break
                    else:
                        ser.close()
                except (serial.SerialException, OSError) as e:
                    print(f"Failed to connect to {device}: {e}")
        elif not self.ser.is_open:
            self.ser = None
        #todo: disconnect detection, timeout, etc. to set self.ser = None if connection is lost
        
        #rerun after 100ms
        if self._running:
            self._timer = threading.Timer(0.1, self._pollSerial)
            self._timer.start()
    
    def _read_64_channels(self, command: bytes) -> np.ndarray:
        '''requests one frame of 64 channels data and returns it as a numpy array with dtype uint16.'''
        ser = self.ser
        if ser is None or not ser.is_open:
            raise RuntimeError("Serial connection is not open.")

        # Discard stale bytes and request one frame.
        ser.reset_input_buffer()
        print(f"[SERIAL OUT] write: {command!r}")
        ser.write(command)
        ser.flush()

        # Parse tokens of the form "<channel>:<value>" until all 64 channels are available.
        pattern = re.compile(r"(\d+)\s*:\s*(\d+)")
        values = {}
        remainder = ""

        try:
            deadline = time.monotonic() + 5.0
            while len(values) < 64 and time.monotonic() < deadline:
                chunk = ser.read(ser.in_waiting or 1)
                if not chunk:
                    continue

                print(f"[SERIAL IN] read: {chunk!r}")
                text = remainder + chunk.decode("ascii", errors="ignore")
                parts = re.split(r"[\r\n]+", text)
                remainder = parts.pop() if parts else ""

                for token in parts:
                    for m in pattern.finditer(token):
                        idx = int(m.group(1))
                        val = int(m.group(2))
                        if 1 <= idx <= 64:
                            values[idx] = val

            # Also parse a potential final line even if it has no trailing newline.
            for m in pattern.finditer(remainder):
                idx = int(m.group(1))
                val = int(m.group(2))
                if 1 <= idx <= 64:
                    values[idx] = val

            print(f"[SERIAL OUT] write: {b'x\r'!r}")
            ser.write(b"x\r")
            ser.flush()

            if len(values) != 64:
                missing = [i for i in range(1, 65) if i not in values]
                raise ValueError(f"Incomplete sensor frame, missing channels: {missing}")

            return np.array([values[i] for i in range(1, 65)], dtype=np.uint16)
        except Exception as e:
            raise RuntimeError(f"Failed to read sensor data: {e}")

    def getRaw(self) -> np.ndarray:
        '''ADC Rohwerte auslesen für alle FD Kanäle (r)'''
        return self._read_64_channels(b"r")

    def getCalibrated(self) -> np.ndarray:
        '''ADC Rohwerte abzüglich Kalibrierwerte (m)'''
        return self._read_64_channels(b"m")

    def getOffset(self) -> np.ndarray:
        '''ADC Rohwerte abzüglich Offsetwerte (o)'''
        return self._read_64_channels(b"o")

    def measureOffset(self) -> None:
        '''Offsetwerte für 64 Kanäle messen und in EEProm speichern (d)'''
        if self.ser is None or not self.ser.is_open:
            raise RuntimeError("Serial connection is not open.")
        self.ser.write(b"d")
        self.ser.flush()

    def writeCalibration(self, data: np.ndarray) -> None:
        '''Kalibrierwerte in EEprom speichern (a), erwartet 64x uint16.'''
        if self.ser is None or not self.ser.is_open:
            raise RuntimeError("Serial connection is not open.")

        array = np.asarray(data)
        if array.shape != (64,):
            raise ValueError(f"Calibration data must have shape (64,), got {array.shape}")

        # Ensure 2-byte unsigned integer values and convert to 128-byte payload.
        if np.any(array < 0) or np.any(array > 65535):
            raise ValueError("Calibration values must be in range 0..65535")
        payload = array.astype("<u2", copy=False).tobytes()
        if len(payload) != 128:
            raise ValueError("Calibration payload must be exactly 128 bytes (64 x 2 bytes)")

        # Stop potential stream and clear stale data before binary command.
        self.ser.write(b"x\r")
        self.ser.flush()
        time.sleep(0.05)
        self.ser.reset_input_buffer()

        self.ser.write(b"a")
        self.ser.write(payload)
        self.ser.flush()

    def readCalibration(self) -> np.ndarray:
        '''Kalibrierwerte auslesen (k), gibt 64x uint16 zurück.'''
        if self.ser is None or not self.ser.is_open:
            raise RuntimeError("Serial connection is not open.")

        # Stop potential stream and clear stale data before binary command.
        self.ser.write(b"x\r")
        self.ser.flush()
        time.sleep(0.05)
        self.ser.reset_input_buffer()

        self.ser.write(b"k")
        self.ser.flush()

        # Expect 128 bytes (2x 64 bytes).
        deadline = time.monotonic() + 5.0
        data = bytearray()
        while len(data) < 128 and time.monotonic() < deadline:
            chunk = self.ser.read(128 - len(data))
            if chunk:
                data.extend(chunk)

        if len(data) != 128:
            raise RuntimeError(f"Failed to read calibration data, received {len(data)}/128 bytes")

        return np.frombuffer(bytes(data), dtype="<u2", count=64).astype(np.uint16, copy=True)

    def getMap(self, calibrated: bool = False, return_unmapped: bool = False, data_source: str | None = None):
        '''returns the latest sensor frame mapped to a 9x9 grid.
        If return_unmapped is True, also returns a dict of unmapped channel values.'''
        if data_source is None:
            raw = self.getCalibrated() if calibrated else self.getRaw()
        else:
            source = data_source.strip().lower()
            if source == "raw":
                raw = self.getRaw()
            elif source == "calibrated":
                raw = self.getCalibrated()
            elif source == "offset":
                raw = self.getOffset()
            else:
                raise ValueError(f"Unknown data_source '{data_source}'. Expected one of: raw, calibrated, offset")

        array = np.full((9, 9), np.nan)
        unmapped: dict[int, int] = {}
        for i, pos in enumerate(positions):
            channel = i + 1
            if pos is not None:
                array[pos[1] + 4, pos[0] + 4] = raw[i]
            else:
                unmapped[channel] = int(raw[i])

        if return_unmapped:
            return array, unmapped
        return array
            