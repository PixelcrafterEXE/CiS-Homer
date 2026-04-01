
import datetime
import serial
from serial.tools import list_ports
import re
import time
import threading
import numpy as np
from typing import Optional

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

# Ordered list of indices into `positions` for the 61 real photodiode channels.
# NTC entries (indices 7, 32) and the reference diode (index 51) are excluded.
valid_channel_indices: list[int] = [i for i, p in enumerate(positions) if p is not None]


def listPorts() -> list:
    '''gets all serial ports with attached devices'''
    return [port for port in list_ports.comports()]

class Sensor:
    def __init__(self, port: str = "auto", baud: int = 115200, device_id: str = "0403:6015"):
        self.port = port
        self.baud = baud
        self.device_id = device_id
        
        self.ser = None
        self.firmware_version: str = ""  # set on connect, cleared on disconnect
        self._serial_lock = threading.RLock()  # serialise all serial I/O; RLock allows re-entry from same thread
        self._calibration_cache: dict | None = None  # populated on connect and by readCalibration()

        self._running = True
        self._timer = None
        self._pollSerial()

    def _reconnect(self) -> None:
        if self.ser is not None:
            if self.ser.is_open:
                self.ser.close()
            self.ser = None
        self._calibration_cache = None
        self.firmware_version = ""

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
                    ser.reset_input_buffer()
                    ser.write(b"v")
                    ser.flush()
                    response = b""
                    deadline = time.monotonic() + 2.0
                    while time.monotonic() < deadline:
                        chunk = ser.read(ser.in_waiting or 1)
                        if chunk:
                            response += chunk
                            if b"\r" in response:
                                break
                    version = response.split(b"\r")[0].decode("ascii", errors="replace").strip()
                    if version.startswith("V"):
                        # Stop any stream the firmware was left in from a previous
                        # connection BEFORE advertising the port to the rest of the
                        # application.  If we set self.ser first, the UI thread sees
                        # sensor_active=True and immediately fires readCalibration()
                        # while the firmware is still streaming — the 257 bytes we
                        # read are then a mix of ASCII stream data and the actual
                        # calibration payload, producing corrupt values.
                        try:
                            ser.write(b'x')
                            ser.flush()
                            time.sleep(0.15)       # let the firmware finish the current frame
                            ser.reset_input_buffer()  # discard any buffered stream bytes
                        except OSError:
                            pass

                        self.firmware_version = version  # set before self.ser to avoid FW-version race
                        with self._serial_lock:
                            # Hold the lock while making the port visible AND reading calibration,
                            # so no measurement thread can acquire the lock (and thus touch the port)
                            # until the cache is fully populated.
                            self.ser = ser
                            print(f"Connected to sensor on {device} (firmware {version})")
                            try:
                                self.readCalibration()  # re-entrant (RLock); cache populated atomically
                            except Exception as _cache_err:
                                print(f"Could not pre-load calibration cache: {_cache_err}")
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
        '''requests one frame of 64 channels data and returns it as a numpy array.'''
        ser = self.ser
        if ser is None or not ser.is_open:
            raise RuntimeError("Serial connection is not open.")

        with self._serial_lock:
            ser.reset_input_buffer()
            #print(f"[SERIAL OUT] write: {command!r}")
            ser.write(command)
            ser.flush()

            # UPDATED REGEX: Added -? to allow for negative values
            pattern = re.compile(r"(\d+)\s*:\s*(-?\d+)")
            values = {}
            remainder = ""

            try:
                deadline = time.monotonic() + 5.0
                while len(values) < 64 and time.monotonic() < deadline:
                    chunk = ser.read(ser.in_waiting or 1)
                    if not chunk:
                        continue

#                    print(f"[SERIAL IN] read: {chunk!r}")
                    text = remainder + chunk.decode("ascii", errors="ignore")
                    parts = re.split(r"[\r\n]+", text)
                    remainder = parts.pop() if parts else ""

                    for token in parts:
                        for m in pattern.finditer(token):
                            idx = int(m.group(1))
                            val = int(m.group(2))
                            if 1 <= idx <= 64:
                                values[idx] = val

                for m in pattern.finditer(remainder):
                    idx = int(m.group(1))
                    val = int(m.group(2))
                    if 1 <= idx <= 64:
                        values[idx] = val

                #print(f"[SERIAL OUT] write: {b'x\r'!r}")
                ser.write(b"x")
                ser.flush()

                if len(values) != 64:
                    missing = [i for i in range(1, 65) if i not in values]
                    raise ValueError(f"Incomplete sensor frame, missing channels: {missing}")

                # UPDATED DTYPE: Changed to int32 to safely store negative offsets
                return np.array([values[i] for i in range(1, 65)], dtype=np.int32)
            except Exception as e:
                raise RuntimeError(f"Failed to read sensor data: {e}") 
   
    def getRaw(self) -> np.ndarray:
        '''ADC Rohwerte auslesen für alle FD Kanäle (r)'''
        return self._read_64_channels(b"r")

    def getCalibrated(self) -> np.ndarray:
        '''Irradiance in µW/mm² for each sensor channel, linearly interpolated from EEPROM calibration.

        Maps each channel's raw ADC reading to irradiance (µW/mm²) using the per-channel
        bright and dark ADC reference points and the two global setpoints:
          setpoint_1 = bright reference irradiance (µW/mm²)
          setpoint_2 = dark reference irradiance (µW/mm²)

        Formula per channel:
          t         = (raw - dark_adc) / (bright_adc - dark_adc)
          irradiance = setpoint_2 + t * (setpoint_1 - setpoint_2)

        Channels without calibration data (NTC: 8, 33; Reference Diode: 52) retain their
        raw ADC value so that getMap's unmapped-channel handling continues to work correctly.
        Pixels where bright_adc == dark_adc (no calibration stored) are set to NaN.
        '''
        raw = self.getRaw()          # shape (64,), dtype int32
        cal = self._calibration_cache
        if cal is None:
            cal = self.readCalibration()  # populates _calibration_cache as a side-effect

        sp1 = float(cal["setpoint_1"])  # bright irradiance reference (µW/mm²)
        sp2 = float(cal["setpoint_2"])  # dark  irradiance reference (µW/mm²)

        # Default: keep raw value (covers NTC / reference-diode channels that are
        # not in valid_channel_indices; getMap needs int(raw[i]) for those).
        result = raw.astype(float)

        for ch_idx, sensor_idx in enumerate(valid_channel_indices):
            bright_adc = float(cal["channel_values"][ch_idx, 0])
            dark_adc   = float(cal["channel_values"][ch_idx, 1])
            denom = bright_adc - dark_adc
            if denom == 0.0:
                result[sensor_idx] = np.nan   # uncalibrated pixel
                continue
            t = (float(raw[sensor_idx]) - dark_adc) / denom
            result[sensor_idx] = sp2 + t * (sp1 - sp2)

        return result

    def readCalibration(self) -> dict:
        '''Liest allgemeine Kalibrierinfos und Kalibrierkanalwerte aus dem EEPROM.

        Sendet Keyword 'k' und empfängt 257 Byte

        Byte-Layout (0-indiziert):
          [0]      Kalibrierzähler
          [1]      Tag
          [2]      Monat
          [3]      Jahr (letzte 2 Stellen)
          [4]      Stunde
          [5]      Minute
          [6]      Sekunde
          [7:9]    Gain (uint16 LE, kΩ)
          [9:11]   Sollwert Kalibrator 1 (uint16 LE, µW/mm²)
          [11:13]  Sollwert Kalibrator 2 (uint16 LE, µW/mm²)
          [13:257] 61 Kanäle × 4 Byte: je 2 Byte cal1 (BE uint16), 2 Byte cal2 (BE uint16)

        Gibt ein Dict zurück:
          counter, day, month, year, hour, minute, second,
          gain, setpoint_1, setpoint_2,
          channel_values – np.ndarray shape (61, 2), dtype uint16
            [:, 0] = Kalibrierwert Kalibrierstärke 1 (hell)
            [:, 1] = Kalibrierwert Kalibrierstärke 2 (dunkel)
          Kanalreihenfolge entspricht valid_channel_indices (None-Einträge übersprungen).
        '''
        ser = self.ser
        if ser is None or not ser.is_open:
            raise RuntimeError("Serial connection is not open.")

        with self._serial_lock:
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                ser.reset_input_buffer()
                ser.write(b'k')
                ser.flush()

                data = b''
                deadline = time.monotonic() + 5.0
                while len(data) < 257 and time.monotonic() < deadline:
                    chunk = ser.read(257 - len(data))
                    if chunk:
                        data += chunk

                if len(data) >= 257:
                    break

                if attempt < max_attempts:
                    print(f"Calibration read attempt {attempt} incomplete "
                          f"({len(data)}/257 bytes), retrying...")
                    time.sleep(0.2)

            if len(data) < 257:
                raise RuntimeError(
                    f"Incomplete calibration read: received {len(data)}/257 bytes "
                    f"after {max_attempts} attempts."
                )

            channel_values = np.zeros((61, 2), dtype=np.uint16)
            for ch in range(61):
                base = 13 + ch * 4
                channel_values[ch, 0] = int.from_bytes(data[base:base + 2],     "big")
                channel_values[ch, 1] = int.from_bytes(data[base + 2:base + 4], "big")

            result = {
                "counter":        data[0],
                "day":            data[1],
                "month":          data[2],
                "year":           data[3],
                "hour":           data[4],
                "minute":         data[5],
                "second":         data[6],
                "gain":           int.from_bytes(data[7:9],   "little"),
                "setpoint_1":     int.from_bytes(data[9:11],  "little"),
                "setpoint_2":     int.from_bytes(data[11:13], "little"),
                "channel_values": channel_values,
            }
            self._calibration_cache = result
            return result
    
    
    def writeCalibration(self,
                         gain: int | None = None,
                         setpoint_1: int | None = None,
                         setpoint_2: int | None = None,
                         channel_values: "np.ndarray | None" = None,
                         day: int | None = None,
                         month: int | None = None,
                         year: int | None = None,
                         hour: int | None = None,
                         minute: int | None = None,
                         second: int | None = None) -> None:
        '''Schreibt Kalibrierinfos und Kalibrierkanalwerte in den EEPROM (Keyword 'a').

        Felder die nicht übergeben werden (None) werden automatisch befüllt:
          Datum/Uhrzeit → aktuelle Systemzeit
          gain, setpoint_1, setpoint_2, channel_values → einmalig per 'k' aus dem EEPROM gelesen

        Protokoll:
          1. Python sendet 'a'
          2. Firmware antwortet mit 'c\r' (ACK, bereit zum Empfang)
          3. Python sendet 256-Byte-Payload
          4. Firmware schreibt EEPROM, antwortet mit 's\r' (done)

        Byte-Layout des 256-Byte-Payloads (0-indiziert):
          [0]      Tag
          [1]      Monat
          [2]      Jahr (letzte 2 Stellen)
          [3]      Stunde
          [4]      Minute
          [5]      Sekunde
          [6:8]    Gain (uint16 BE, kΩ)            ← Firmware: Rx[6]<<8 | Rx[7]
          [8:10]   Sollwert Kalibrator 1 (uint16 BE, µW/mm²)
          [10:12]  Sollwert Kalibrator 2 (uint16 BE, µW/mm²)
          [12:256] 61 Kanäle × 4 Byte: je 2 Byte cal1 (BE uint16), 2 Byte cal2 (BE uint16)
                   ← Firmware: KalibWerte[i] = Rx[12+4i]<<24|Rx[13+4i]<<16|Rx[14+4i]<<8|Rx[15+4i]
        '''
        ser = self.ser
        if ser is None or not ser.is_open:
            raise RuntimeError("Serial connection is not open.")

        # Fill missing data fields — prefer the in-memory cache to avoid an extra serial round trip.
        if any(v is None for v in (gain, setpoint_1, setpoint_2, channel_values)):
            existing = self._calibration_cache or self.readCalibration()
            if gain           is None: gain           = existing["gain"]
            if setpoint_1     is None: setpoint_1     = existing["setpoint_1"]
            if setpoint_2     is None: setpoint_2     = existing["setpoint_2"]
            if channel_values is None: channel_values = existing["channel_values"]

        if channel_values.shape != (61, 2):
            raise ValueError(
                f"channel_values must have shape (61, 2), got {channel_values.shape}"
            )

        # Fill missing time fields from current system time.
        now = datetime.datetime.now()
        if day    is None: day    = now.day
        if month  is None: month  = now.month
        if year   is None: year   = now.year % 100
        if hour   is None: hour   = now.hour
        if minute is None: minute = now.minute
        if second is None: second = now.second

        payload = bytearray(256)
        payload[0] = int(day)    & 0xFF
        payload[1] = int(month)  & 0xFF
        payload[2] = int(year)   & 0xFF
        payload[3] = int(hour)   & 0xFF
        payload[4] = int(minute) & 0xFF
        payload[5] = int(second) & 0xFF
        payload[6:8]   = int(gain).to_bytes(2,       "big")  # firmware: Rx[6]<<8 | Rx[7]
        payload[8:10]  = int(setpoint_1).to_bytes(2, "big")
        payload[10:12] = int(setpoint_2).to_bytes(2, "big")

        for ch in range(61):
            base = 12 + ch * 4
            payload[base:base + 2]     = int(channel_values[ch, 0]).to_bytes(2, "big")
            payload[base + 2:base + 4] = int(channel_values[ch, 1]).to_bytes(2, "big")

        with self._serial_lock:
            # Step 1: send command, wait for 'c\r' ACK before transmitting payload
            ser.reset_input_buffer()
            ser.write(b'a')
            ser.flush()

            ack = b''
            deadline = time.monotonic() + 2.0
            while b'\r' not in ack and time.monotonic() < deadline:
                chunk = ser.read(ser.in_waiting or 1)
                if chunk:
                    ack += chunk
            if b'c' not in ack:
                raise RuntimeError(f"No 'c\\r' ACK from firmware for 'a' command, got: {ack!r}")

            # Step 2: send the 256-byte payload
            ser.write(bytes(payload))
            ser.flush()

            # Step 3: wait for 's\r' done response from SetEEPROM
            resp = b''
            deadline = time.monotonic() + 5.0
            while b'\r' not in resp and time.monotonic() < deadline:
                chunk = ser.read(ser.in_waiting or 1)
                if chunk:
                    resp += chunk
            if b's' not in resp:
                print(f"Warning: no 's\\r' completion from firmware after 'a' command, got: {resp!r}")

        # Update in-memory cache to reflect what was just written to EEPROM.
        # Use .copy() so later mutations to the caller's array cannot corrupt the cache.
        self._calibration_cache = {
            **(self._calibration_cache or {}),
            "gain": gain, "setpoint_1": setpoint_1, "setpoint_2": setpoint_2,
            "channel_values": channel_values.copy(),
            "day": day, "month": month, "year": year,
            "hour": hour, "minute": minute, "second": second,
        }

    def getCalibrationArray(self) -> np.ndarray:
        '''Gibt Kalibrierwerte als (2, 64) Array zurück.

        [0, i] = Kalibrierstärke 1 (hell) für Kanal i+1
        [1, i] = Kalibrierstärke 2 (dunkel) für Kanal i+1
        NaN an den ungültigen Indizes (NTC: 7, 32 / Referenzdiode: 51).
        '''
        cal = self.readCalibration()
        arr = np.full((2, 64), np.nan)
        for ch_idx, sensor_idx in enumerate(valid_channel_indices):
            arr[0, sensor_idx] = float(cal["channel_values"][ch_idx, 0])
            arr[1, sensor_idx] = float(cal["channel_values"][ch_idx, 1])
        return arr

    def writeCalibrationArray(self, cal_array: np.ndarray) -> None:
        '''Schreibt Kalibrierwerte aus (2, 64) Array in EEPROM.

        [0, i] = Kalibrierstärke 1 (hell) für Kanal i+1
        [1, i] = Kalibrierstärke 2 (dunkel) für Kanal i+1
        NaN-Einträge werden als 0 geschrieben.
        '''
        channel_values = np.zeros((61, 2), dtype=np.uint16)
        for ch_idx, sensor_idx in enumerate(valid_channel_indices):
            v0 = cal_array[0, sensor_idx]
            v1 = cal_array[1, sensor_idx]
            channel_values[ch_idx, 0] = 0 if np.isnan(v0) else int(np.clip(v0, 0, 65535))
            channel_values[ch_idx, 1] = 0 if np.isnan(v1) else int(np.clip(v1, 0, 65535))
        self.writeCalibration(channel_values=channel_values)

    def getCalibrationCounter(self) -> int:
        '''Liest den Kalibrierungszähler aus. Liest dafür einmal Keyword 'k'.'''
        return int(self.readCalibration()["counter"])

    def getTime(self) -> datetime.datetime:
        '''Liest Datum/Uhrzeit aus dem EEPROM (Keyword 'k') und setzt sie im Betriebssystem.'''
        import subprocess
        cal = self.readCalibration()
        year = cal["year"]
        if year < 100:
            year += 2000
        dt = datetime.datetime(year, cal["month"], cal["day"],
                               cal["hour"], cal["minute"], cal["second"])
        subprocess.run( #needs permissions; todo: configure OS to allow
            ["date", "-s", dt.strftime("%Y-%m-%d %H:%M:%S")],
            check=True,
        )
        return dt

    def setTime(self, day: int, month: int, year: int,
                hour: int, minute: int, second: int) -> None:
        '''Schreibt Datum/Uhrzeit in das EEPROM'''
        self.writeCalibration(
            day=day, month=month, year=year % 100,
            hour=hour, minute=minute, second=second,
        )

    def getVersion(self) -> str:
        '''liest die MCU-Firmware Version aus (Keyword 'v').

        Sendet 'v', empfängt bis zu 16 Byte bis zum ersten \r und gibt den
        String ohne \r zurück (z.B. "V100").
        '''
        ser = self.ser
        if ser is None or not ser.is_open:
            raise RuntimeError("Serial connection is not open.")

        with self._serial_lock:
            ser.reset_input_buffer()
            ser.write(b'v')
            ser.flush()

            response = b''
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                chunk = ser.read(ser.in_waiting or 1)
                if chunk:
                    response += chunk
                    if b'\r' in response:
                        break

            return response.split(b'\r')[0].decode('ascii', errors='replace').strip()

    def getGain(self) -> int:
        '''liest den Verstärkungsfaktor der Hardware aus EEPROM aus.'''
        return int(self.readCalibration()["gain"])

    def writeGain(self, gain: int) -> None:
        '''schreibt den Verstärkungsfaktor der Hardware in EEPROM.'''
        self.writeCalibration(gain=int(gain))

    def getCalibrationReference(self) -> np.ndarray:
        '''Bestrahlungsstärke ersten und zweiten Kalibrierung in µW/mm².

        Gibt np.ndarray([setpoint_1, setpoint_2], dtype=uint16) zurück.
        '''
        cal = self.readCalibration()
        return np.array([cal["setpoint_1"], cal["setpoint_2"]], dtype=np.uint16)

    def writeCalibrationReference(self, setpoint_1: int, setpoint_2: int) -> None:
        '''schreibt die Bestrahlungsstärke für die erste und zweite Kalibrierung in µW/mm² in EEPROM.'''
        self.writeCalibration(setpoint_1=int(setpoint_1), setpoint_2=int(setpoint_2))

    def getMap(self, calibrated: bool = False, return_unmapped: bool = False, data_source: Optional[str] = None):
        '''returns the latest sensor frame mapped to a 9x9 grid.
        If return_unmapped is True, also returns a dict of unmapped channel values.'''
        if data_source is None:
            raw = self.getCalibrated() if calibrated else self.getRaw()
        else:
            source = data_source.strip().lower()
            if source == "raw":
                raw = self.getRaw()
            elif source == "calibrated" or source.startswith("irradiance"):
                raw = self.getCalibrated()
            else:
                raise ValueError(f"Unknown data_source '{data_source}'. Expected one of: raw, irradiance, offset")

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
            