import serial
from serial.tools import list_ports
import re
import time
import threading

import numpy as np
from matplotlib.figure import Figure

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
    None,     # 52 (Refference Diode)
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
    
    def getRaw(self) -> np.ndarray:
        '''requests one raw frame of sensor data and returns it as a numpy array of shape (64,) with dtype uint16.'''
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

    def getMap(self) -> np.ndarray:
        '''returns the latest sensor frame mapped to a 9x9 grid.'''
        raw = self.getRaw()
        array = np.full((9, 9), np.nan)
        for i, pos in enumerate(positions):
            if pos is not None:
                array[pos[0] + 4, pos[1] + 4] = raw[i]
        return array


    def plotRaster(self, autoRange: bool = False, logRange: bool = True) -> Figure:
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors
        from matplotlib.collections import LineCollection
        import numpy as np

        data = self.getMap().astype(float)
        rows, cols = data.shape
        nan_mask = np.isnan(data)
        valid_vals = data[~nan_mask]

        lo = float(valid_vals.min()) if autoRange and len(valid_vals) else (1.0 if logRange else 0.0)
        hi = float(valid_vals.max()) if autoRange and len(valid_vals) else 65535.0

        def make_cmap(lo, hi):
            if logRange:
                log_rng = np.log10(65535) - np.log10(1)
                lo_n = (np.log10(max(lo, 1)) - np.log10(1)) / log_rng
                hi_n = (np.log10(max(hi, 1)) - np.log10(1)) / log_rng
            else:
                lo_n, hi_n = lo / 65535.0, hi / 65535.0
            lo_n = float(np.clip(lo_n, 0.0, 1.0))
            hi_n = float(np.clip(hi_n, lo_n + 1e-6, 1.0))
            cmap = mcolors.LinearSegmentedColormap.from_list(
                'raster', [(0.0, 'black'), (lo_n, 'black'), (hi_n, 'white'), (1.0, 'white')]
            )
            cmap.set_bad('none')
            return cmap

        norm = mcolors.LogNorm(vmin=1, vmax=65535) if logRange else mcolors.Normalize(vmin=0, vmax=65535)

        fig, (ax, cax) = plt.subplots(1, 2, figsize=(8, 6), gridspec_kw={'width_ratios': [8, 1]})
        fig.subplots_adjust(wspace=0.05)

        im = ax.imshow(data, cmap=make_cmap(lo, hi), norm=norm, interpolation='nearest', aspect='equal')
        ax.set_xticks([]); ax.set_yticks([])

        # Grid lines via LineCollection (draw edge if at least one adjacent pixel is valid)
        def ok(i, j):
            return 0 <= i < rows and 0 <= j < cols and not nan_mask[i, j]

        segs = (
            [[(j-.5, i-.5), (j+.5, i-.5)] for i in range(rows+1) for j in range(cols) if ok(i-1,j) or ok(i,j)] +
            [[(j-.5, i-.5), (j-.5, i+.5)] for j in range(cols+1) for i in range(rows) if ok(i,j-1) or ok(i,j)]
        )
        if segs:
            ax.add_collection(LineCollection(segs, colors='black', lw=0.5))

        fig.colorbar(im, cax=cax)

        if not autoRange:
            state = {'drag': None, 'lo': lo, 'hi': hi}
            lo_line = cax.axhline(lo, color='cyan', lw=1.5)
            hi_line = cax.axhline(hi, color='cyan', lw=1.5)
            vmin_cb = 1 if logRange else 0

            def on_press(event):
                if event.inaxes != cax or event.ydata is None: return
                y = event.ydata
                state['drag'] = 'lo' if abs(y - state['lo']) <= abs(y - state['hi']) else 'hi'

            def on_motion(event):
                if not state['drag'] or event.inaxes != cax or event.ydata is None: return
                y = float(np.clip(event.ydata, vmin_cb, 65535))
                if state['drag'] == 'lo':
                    state['lo'] = min(y, state['hi'] * 0.999 if logRange else state['hi'] - 1)
                    lo_line.set_ydata([state['lo']] * 2)
                else:
                    state['hi'] = max(y, state['lo'] * 1.001 if logRange else state['lo'] + 1)
                    hi_line.set_ydata([state['hi']] * 2)
                im.set_cmap(make_cmap(state['lo'], state['hi']))
                fig.canvas.draw_idle()

            def on_release(event): state['drag'] = None

            fig.canvas.mpl_connect('button_press_event', on_press)
            fig.canvas.mpl_connect('motion_notify_event', on_motion)
            fig.canvas.mpl_connect('button_release_event', on_release)

        return fig
    

    def plotBar(self) -> Figure:
        import matplotlib.pyplot as plt
        data = self.getRaw()
        fig, ax = plt.subplots(figsize=(10, 5))
        
        indices = np.arange(1, 65)
        ax.bar(indices, data)
        ax.set_xlabel("Channel Index")
        ax.set_ylabel("Value")
        ax.set_title("Channel Values")
        ax.set_xlim(0, 65)
        
        return fig

    def plotTable(self) -> None:
        pass
            