from __future__ import annotations

import ttkbootstrap as tkk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

import lib.Sensor as Serial
from lib.Sensor import Sensor
from lib.Plotting import RasterFigure, BarFigure, TableFrame
from lib.UI_Options import *

class UI(tkk.Tk):
    def __init__(self) -> None:
        super().__init__()
        #delete window on close button
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._sensor: Sensor | None = None
        self._raster_fig: RasterFigure | None = None
        self._bar_fig: BarFigure | None = None
        self._measurement_rate = 100
        self._fetching_data = False
        try:
            self._sensor = Sensor()
        except RuntimeError:
            pass
        self.buildUI()
        self._update_loop()
        self._measurement_loop()

    def _measurement_loop(self) -> None:
        if hasattr(self, '_stream_toggle') and self._stream_toggle.value.get():
            self._update_measurement()
        self.after(self._measurement_rate, self._measurement_loop)

    def _update_measurement(self) -> None:
        sensor_active = bool(self._sensor and self._sensor.ser and self._sensor.ser.is_open)

        # Rebuild layout if sensor connection state changed
        if sensor_active != hasattr(self, '_tabview'):
            self._build_left_panel()

        if not sensor_active or not hasattr(self, '_tabview') or self._fetching_data:
            return

        self._fetching_data = True

        def fetch_and_update():
            try:
                current_tab = self._tabview.index("current")
                is_raw = self._raw_data_toggle.value.get() if hasattr(self, '_raw_data_toggle') else False
                if current_tab == 0 and getattr(self, '_raster_fig', None):
                    data = self._sensor.getMap(calibrated=not is_raw)
                    self.after(0, lambda: self._raster_fig.update_data(data))
                elif current_tab == 1 and getattr(self, '_bar_fig', None):
                    data = self._sensor.getRaw() if is_raw else self._sensor.getCalibrated()
                    self.after(0, lambda: self._bar_fig.update_data(data))
                elif current_tab == 2 and getattr(self, '_table_frame', None):
                    data = self._sensor.getMap(calibrated=not is_raw)
                    is_4in = self._4inch_toggle.value.get() if hasattr(self, '_4inch_toggle') else False
                    self.after(0, lambda d=data, i=is_4in: self._table_frame.update_data(d, i))
            except Exception as e:
                print(f"Error updating measurement: {e}")
                if self._sensor and self._sensor.ser:
                    try:
                        self._sensor.ser.close()
                    except Exception:
                        pass
                    self._sensor.ser = None
                self.after(0, self._build_left_panel)
            finally:
                self._fetching_data = False
                
        import threading
        threading.Thread(target=fetch_and_update, daemon=True).start()

    def _update_loop(self) -> None:
        changed = False
        for option in getattr(self, "_options", []):
            if option.check_visibility_change():
                changed = True
        
        if changed:
            # First remove all
            for option in self._options:
                option.pack_forget()
            # Then pack only the visible ones, in their original creation order
            for option in self._options:
                if option._is_visible:
                    option.pack(in_=option._parent_container, fill="x", padx=8, pady=5)
                    
        self.after(100, self._update_loop)

    def _on_closing(self) -> None:
        if self._sensor is not None:
            self._sensor.stop()
        self.quit()
        self.destroy()

    def buildUI(self) -> None:
        self.title("CiS HomeRPI")
        #self.attributes("-fullscreen", True)

        # Container roots for left and right panels 
        self._main = tkk.Frame(self)
        self._main.pack(fill="both", expand=True)
        self._main.columnconfigure(0, weight=4, uniform="group1")
        self._main.columnconfigure(1, weight=3, uniform="group1")
        self._main.rowconfigure(0, weight=1)

        self._build_right_panel()
        self._build_left_panel()

    def _build_left_panel(self) -> None:
        if hasattr(self, '_left_panel'):
            for widget in self._left_panel.winfo_children():
                widget.destroy()
        else:
            self._left_panel = tkk.Frame(self._main, padding=10)
            self._left_panel.grid(row=0, column=0, sticky="nsew")

        if self._sensor is None or not self._sensor.ser or not self._sensor.ser.is_open:
            error_label = tkk.Label(self._left_panel, text="No sensor detected", foreground="red")
            error_label.pack(expand=True)
            self._raster_canvas = None
            if hasattr(self, '_tabview'):
                delattr(self, '_tabview')
        else:
            self._tabview = tkk.Notebook(self._left_panel)
            self._tabview.pack(fill="both", expand=True)

            # Rasteransicht
            self._frame_raster_container = tkk.Frame(self._tabview)
            self._tabview.add(self._frame_raster_container, text="Rasteransicht")
            self._rebuild_raster_fig()

            # Balkenansicht
            self._frame_bar = tkk.Frame(self._tabview)
            self._bar_fig = BarFigure(np.zeros(64))
            canvas_bar = FigureCanvasTkAgg(self._bar_fig, master=self._frame_bar)
            canvas_bar.draw()
            canvas_bar.get_tk_widget().pack(fill="both", expand=True)
            self._tabview.add(self._frame_bar, text="Balkenansicht")

            # Tabellenansicht
            is_4in = self._4inch_toggle.value.get() if hasattr(self, '_4inch_toggle') else False
            self._table_frame = TableFrame(self._tabview, np.full((9, 9), np.nan), is_4in=is_4in)
            self._tabview.add(self._table_frame, text="Tabellenansicht")

    def _rebuild_raster_fig(self) -> None:
        if not self._sensor or not self._sensor.ser or not self._sensor.ser.is_open:
            return
        
        if hasattr(self, '_raster_canvas') and self._raster_canvas is not None:
            self._raster_canvas.get_tk_widget().destroy()

        auto_range = self._auto_range_toggle.value.get() if hasattr(self, '_auto_range_toggle') else False
        log_range = self._log_scale_toggle.value.get() if hasattr(self, '_log_scale_toggle') else True
        is_4in = self._4inch_toggle.value.get() if hasattr(self, '_4inch_toggle') else False
        
        self._raster_fig = RasterFigure(np.full((9, 9), np.nan), autoRange=auto_range, logRange=log_range, is_4in=is_4in)
        self._raster_canvas = FigureCanvasTkAgg(self._raster_fig, master=self._frame_raster_container)
        self._raster_canvas.draw()
        self._raster_canvas.get_tk_widget().pack(fill="both", expand=True)

        if hasattr(self, '_table_frame'):
            self._table_frame.update_data(np.full((9, 9), np.nan), is_4in=is_4in)

        if hasattr(self, '_stream_toggle') and not self._stream_toggle.value.get():
            self._update_measurement()

    def _build_right_panel(self) -> None:
        self._right_panel = tkk.Frame(self._main, padding=(0, 10, 10, 10))
        self._right_panel.grid(row=0, column=1, sticky="nsew")
        self._right_panel.rowconfigure(0, weight=1)
        self._right_panel.columnconfigure(0, weight=1)

        from ttkbootstrap.scrolled import ScrolledFrame
        self._options_container = ScrolledFrame(self._right_panel, autohide=True, bootstyle="round")
        self._options_container.grid(row=0, column=0, sticky="nsew")

        self._options: list[Option] = []

        serial_section = OptionSection(self._options_container, "Verbindung", persistent=True)
        self._add_option(serial_section)
        
        serial_section.add_option(
            OptionDropdown(
                serial_section.content_frame,
                "Serieller Port",
                ["auto"] + [port.device for port in Serial.listPorts()], #todo: show device name
                "auto",
                command=lambda port: self._sensor.setPort(port) if self._sensor else None,
                persistent=True
            )
        )

        messung_section = OptionSection(self._options_container, "Messung", persistent=True)
        self._add_option(messung_section)

        self._stream_toggle = OptionToggle(messung_section.content_frame, "Messdaten Streamen", initial=True, persistent=True)
        messung_section.add_option(self._stream_toggle)

        def set_freq(freq_str: str) -> None:
            self._measurement_rate = int(freq_str)
            
        messung_section.add_option(
            OptionDropdown(
                messung_section.content_frame,
                "Messintervall (ms)",
                ["50", "100", "200", "500", "1000", "2000"],
                "100",
                command=set_freq,
                visibility=lambda: self._stream_toggle.value.get(),
                persistent=True
            )
        )

        messung_section.add_option(
            OptionButton(
                messung_section.content_frame, 
                "Messen", 
                command=self._update_measurement,
                visibility=lambda: not self._stream_toggle.value.get()
            )
        )
        
        display_section = OptionSection(self._options_container, "Anzeige", persistent=True)
        self._add_option(display_section)
        
        self._auto_range_toggle = OptionToggle(
            display_section.content_frame, 
            "Autom. Range", 
            initial=False,
            command=lambda _: self._rebuild_raster_fig(),
            persistent=True
        )
        display_section.add_option(self._auto_range_toggle)
        
        self._log_scale_toggle = OptionToggle(
            display_section.content_frame, 
            "Log. Maßstab", 
            initial=True,
            command=lambda _: self._rebuild_raster_fig(),
            persistent=True
        )
        display_section.add_option(self._log_scale_toggle)

        self._4inch_toggle = OptionToggle(
            display_section.content_frame, 
            "4 Zoll Wafer", 
            initial=False,
            command=lambda _: self._rebuild_raster_fig(),
            persistent=True
        )
        display_section.add_option(self._4inch_toggle)

        export_section = OptionSection(self._options_container, "Exportieren", persistent=True)
        self._add_option(export_section)
        
        from lib.Export import is_usb_available, export_data
        
        btn = OptionButton(
            export_section.content_frame, 
            "Export CSV to USB", 
            command=lambda: export_data(self._sensor),
            visibility=is_usb_available
        )
        export_section.add_option(btn)
        
        lbl = OptionLabel(
            export_section.content_frame,
            text="Kein USB Speicher erkannt",
            foreground="red",
            visibility=lambda: not is_usb_available()
        )
        export_section.add_option(lbl)

        calibrate_section = OptionSection(self._options_container, "Kalibrierung", persistent=True)
        self._add_option(calibrate_section)

        self._raw_data_toggle = OptionToggle(
            calibrate_section.content_frame, 
            "Rohdaten anzeigen", 
            initial=False,
            command=lambda _: self._rebuild_raster_fig(),
            persistent=True
        )
        calibrate_section.add_option(self._raw_data_toggle)

        

    def _add_option(self, option: Option) -> None:
        self._options.append(option)
        option.add_to(self._options_container)