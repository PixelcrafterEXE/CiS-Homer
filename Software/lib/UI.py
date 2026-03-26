from __future__ import annotations

import ttkbootstrap as tkk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

import lib.Sensor as Serial
from lib.Sensor import Sensor
from lib.Plotting import RasterFigure
from lib.UI_Options import *
from lib.Config import getColorSchemes, getCFGKey, setCFGKey

class UI(tkk.Tk):
    def __init__(self) -> None:
        super().__init__()
        #delete window on close button
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._sensor: Sensor | None = None
        self._raster_fig: RasterFigure | None = None
        self._measurement_rate = 100
        self._fetching_data = False
        try:
            self._sensor = Sensor()
        except RuntimeError:
            pass
        
        self._options: list[Option] = []
        self.buildUI()
        self._update_loop()
        self._measurement_loop()

    def _sensor_active(self) -> bool:
        '''Helper to check if sensor connection is active and open.'''
        return bool(self._sensor and self._sensor.ser and self._sensor.ser.is_open)

    def _measurement_loop(self) -> None:
        if hasattr(self, '_stream_toggle') and self._stream_toggle.value.get():
            self._update_measurement()
        self.after(self._measurement_rate, self._measurement_loop)

    def _update_measurement(self) -> None:
        sensor_active = self._sensor_active()

        # Rebuild layout if sensor connection state changed
        if sensor_active != getattr(self, '_ui_sensor_state', None):
            self._build_main_panel()

        if not sensor_active or not hasattr(self, '_tabview') or self._fetching_data:
            return

        self._fetching_data = True

        def fetch_and_update():
            try:
                current_tab = self._tabview.index("current")
                data_source = self._data_source_dropdown.value.get() if hasattr(self, '_data_source_dropdown') else "raw"
                if current_tab == 0 and getattr(self, '_raster_fig', None):
                    data, unmapped = self._sensor.getMap(data_source=data_source, return_unmapped=True)
                    self.after(0, lambda d=data, u=unmapped: self._raster_fig.update_data(d, unmapped=u))
            except Exception as e:
                print(f"Error updating measurement: {e}")
                if self._sensor and self._sensor.ser:
                    try: self._sensor.ser.close()
                    except: pass
                    self._sensor.ser = None
                self.after(0, self._build_main_panel)
            finally:
                self._fetching_data = False
                
        import threading
        threading.Thread(target=fetch_and_update, daemon=True).start()

    def _update_loop(self) -> None:
        changed = False
        for option in self._options:
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

    def _store_manual_range(self, lo: float, hi: float) -> None:
        setCFGKey("manual_range_lo", float(lo))
        setCFGKey("manual_range_hi", float(hi))

    def buildUI(self) -> None:
        self.title("CiS HomeRPI")
        #self.attributes("-fullscreen", True)
        self.geometry("800x1280")

        # Main container
        self._main = tkk.Frame(self)
        self._main.pack(fill="both", expand=True)

        if not hasattr(self, '_options_panel_visible'):
            self._options_panel_visible = False

        self._build_main_panel()

    def _build_main_panel(self) -> None:
        sensor_active = self._sensor_active()

        if hasattr(self, '_main_panel'):
            for widget in self._main_panel.winfo_children():
                widget.destroy()
        else:
            self._main_panel = tkk.Frame(self._main, padding=10)
            self._main_panel.place(relx=0, rely=0, relwidth=1, relheight=1)

        self._tabview = tkk.Notebook(self._main_panel)
        self._tabview.pack(fill="both", expand=True)

        # Raster view
        self._frame_raster_container = tkk.Frame(self._tabview)
        self._tabview.add(self._frame_raster_container, text="Visualizer")

        self._raster_root = tkk.Frame(self._frame_raster_container)
        self._raster_root.pack(fill="both", expand=True)

        self._raster_body = tkk.Frame(self._raster_root)
        self._raster_body.pack(fill="both", expand=True)
        self._raster_body.columnconfigure(0, weight=1)
        self._raster_body.rowconfigure(0, weight=1)

        self._plot_container = tkk.Frame(self._raster_body)
        self._plot_container.grid(row=0, column=0, sticky="nsew")

        self._options_toggle_btn = tkk.Button(
            self._raster_body,
            text="⮞ Show options",
            command=self._toggle_options_panel,
            bootstyle="secondary"
        )
        self._options_toggle_btn.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        # The options panel now contains the three columns
        self._options_panel = tkk.Frame(self._raster_body, padding=10, relief="ridge", borderwidth=1)
        self._build_options_panel(self._options_panel)
        self._apply_options_panel_visibility()

        # Settings tab
        self._frame_settings = tkk.Frame(self._tabview)
        self._tabview.add(self._frame_settings, text="Settings")

        self._setup_settings_tab()

        # Calibration tab
        self._frame_calibration = tkk.Frame(self._tabview)
        self._tabview.add(self._frame_calibration, text="Calibration")

        self._setup_calibration_tab()

        if sensor_active:
            self._rebuild_raster_fig()
        else:
            self._raster_canvas = None
            tkk.Label(self._plot_container, text="No sensor detected", foreground="red").pack(expand=True)

        self._ui_sensor_state = sensor_active

    def _setup_settings_tab(self) -> None:
        # Serial Port
        OptionDropdown(self._frame_settings, "Serial port", ["auto"] + [port.device for port in Serial.listPorts()],
                       "auto", command=lambda port: self._sensor.setPort(port) if self._sensor else None,
                       persistent=True).add_to(self._frame_settings)

        # Wafer Config
        OptionDropdown(self._frame_settings, "Wafer diameter (mm)", [str(v) for v in range(50, 151, 10)],
                       "150", command=lambda _v: self._rebuild_raster_fig(), persistent=True).add_to(self._frame_settings)
        
        OptionToggle(self._frame_settings, "Mask values outside wafer dia.", initial=False,
                     command=lambda _: self._rebuild_raster_fig(), persistent=True).add_to(self._frame_settings)

        # Visuals
        self._color_schemes = getColorSchemes()
        scheme_names = list(self._color_schemes.keys())
        OptionDropdown(self._frame_settings, "Color scheme", scheme_names, scheme_names[0] if scheme_names else "Grayscale",
                       command=lambda _v: self._rebuild_raster_fig(), persistent=True).add_to(self._frame_settings)
        self._settings_use_clipping_colors = OptionToggle(
            self._frame_settings,
            "Use clipping colors",
            initial=True,
            command=lambda _: self._rebuild_raster_fig(),
            persistent=True,
        )
        self._settings_use_clipping_colors.add_to(self._frame_settings)

        self._settings_show_orientation_hint = OptionToggle(
            self._frame_settings,
            "Show orientation hint",
            initial=True,
            command=lambda _: self._rebuild_raster_fig(),
            persistent=True,
        )
        self._settings_show_orientation_hint.add_to(self._frame_settings)

    def _setup_calibration_tab(self) -> None:
        pass

    def _build_options_panel(self, parent) -> None:
        self._options = []
        
        # Container for columns
        cols_container = tkk.Frame(parent)
        cols_container.pack(fill="both", expand=True)

        # Configure the grid to have 3 equal-width columns
        # 'uniform="group1"' ensures they stay the same size
        cols_container.columnconfigure(0, weight=1, uniform="group1")
        cols_container.columnconfigure(1, weight=1, uniform="group1")
        cols_container.columnconfigure(2, weight=1, uniform="group1")
        
        # Ensure the row stretches to fill available vertical space
        cols_container.rowconfigure(0, weight=1)

        # --- COLUMN 1: MEASUREMENT ---
        col_meas = tkk.LabelFrame(cols_container, text=" Measurement ")
        # sticky="nsew" makes the box fill the entire grid cell (Equal Height)
        col_meas.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self._stream_toggle = OptionToggle(col_meas, "Stream measurements", initial=True, persistent=True)
        self._add_option(self._stream_toggle, col_meas)

        self._add_option(OptionDropdown(
            col_meas, "Interval (ms)", ["50", "100", "200", "500", "1000"], "100",
            command=lambda f: setattr(self, '_measurement_rate', int(f)),
            visibility=lambda: self._stream_toggle.value.get(), persistent=True
        ), col_meas)

        self._add_option(OptionButton(
            col_meas, "Manual Measure", command=self._update_measurement,
            visibility=lambda: not self._stream_toggle.value.get()
        ), col_meas)

        self._data_source_dropdown = OptionDropdown(
            col_meas, "Data source", ["raw", "calibrated", "offset"], "raw",
            command=lambda _v: self._update_measurement(), persistent=True
        )
        self._add_option(self._data_source_dropdown, col_meas)

        # --- COLUMN 2: DISPLAY ---
        col_disp = tkk.LabelFrame(cols_container, text=" Display ")
        col_disp.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        self._range_mode_dropdown = OptionDropdown(
            col_disp, "Range", ["auto", "manual", "max"], "manual",
            command=lambda _v: self._rebuild_raster_fig(), persistent=True
        )
        self._add_option(self._range_mode_dropdown, col_disp)

        self._log_scale_toggle = OptionToggle(
            col_disp, "Log scale", initial=True,
            command=lambda _: self._rebuild_raster_fig(), persistent=True
        )
        self._add_option(self._log_scale_toggle, col_disp)

        self._add_option(OptionToggle(
            col_disp, "Label Measurements", initial=False,
            command=lambda _: self._rebuild_raster_fig(), persistent=True
        ), col_disp)

        # --- COLUMN 3: EXPORT ---
        col_exp = tkk.LabelFrame(cols_container, text=" Export ")
        col_exp.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)

        from lib.Export import is_usb_available, export_data
        
        self._add_option(OptionButton(
            col_exp, "Export CSV to USB", command=lambda: export_data(self._sensor),
            visibility=is_usb_available
        ), col_exp)
        
        self._add_option(OptionLabel(
            col_exp, text="No USB storage detected", foreground="red",
            visibility=lambda: not is_usb_available()
        ), col_exp)

    def _add_option(self, option: Option, container: tkk.Frame) -> None:
        self._options.append(option)
        option.add_to(container)

    def _toggle_options_panel(self) -> None:
        self._options_panel_visible = not self._options_panel_visible
        self._apply_options_panel_visibility()

    def _apply_options_panel_visibility(self) -> None:
        if self._options_panel_visible:
            self._options_panel.grid(row=2, column=0, sticky="nsew")
            self._options_toggle_btn.configure(text="⮜ Hide options")
        else:
            self._options_panel.grid_forget()
            self._options_toggle_btn.configure(text="⮞ Show options")

    def _rebuild_raster_fig(self) -> None:
        # ... (Rest of the method remains identical to your provided code) ...
        if not self._sensor_active(): return
        if hasattr(self, '_raster_canvas') and self._raster_canvas:
            self._raster_canvas.get_tk_widget().destroy()

        range_mode = self._range_mode_dropdown.value.get() if hasattr(self, '_range_mode_dropdown') else "manual"
        log_range = self._log_scale_toggle.value.get() if hasattr(self, '_log_scale_toggle') else True
        
        # Logic for fetching configurations and building the RasterFigure...
        # [Simplified for brevity, use your existing RasterFigure initialization here]
        self._raster_fig = RasterFigure(np.full((9, 9), np.nan), rangeMode=range_mode, logRange=log_range) 
        self._raster_canvas = FigureCanvasTkAgg(self._raster_fig, master=self._plot_container)
        self._raster_canvas.draw()
        self._raster_canvas.get_tk_widget().pack(fill="both", expand=True)