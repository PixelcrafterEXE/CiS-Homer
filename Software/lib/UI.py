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
                    data, unmapped = self._sensor.getMap(calibrated=not is_raw, return_unmapped=True)
                    self.after(0, lambda d=data, u=unmapped: self._raster_fig.update_data(d, unmapped=u))
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

    def _store_manual_range(self, lo: float, hi: float) -> None:
        setCFGKey("manual_range_lo", float(lo))
        setCFGKey("manual_range_hi", float(hi))

    def buildUI(self) -> None:
        self.title("CiS HomeRPI")
        #self.attributes("-fullscreen", True)

        # Main container
        self._main = tkk.Frame(self)
        self._main.pack(fill="both", expand=True)

        if not hasattr(self, '_options_panel_visible'):
            self._options_panel_visible = False

        self._build_left_panel()

    def _build_left_panel(self) -> None:
        if hasattr(self, '_left_panel'):
            for widget in self._left_panel.winfo_children():
                widget.destroy()
        else:
            self._left_panel = tkk.Frame(self._main, padding=10)
            self._left_panel.place(relx=0, rely=0, relwidth=1, relheight=1)

        if self._sensor is None or not self._sensor.ser or not self._sensor.ser.is_open:
            error_label = tkk.Label(self._left_panel, text="No sensor detected", foreground="red")
            error_label.pack(expand=True)
            self._raster_canvas = None
            if hasattr(self, '_tabview'):
                delattr(self, '_tabview')
        else:
            self._tabview = tkk.Notebook(self._left_panel)
            self._tabview.pack(fill="both", expand=True)

            # Raster view
            self._frame_raster_container = tkk.Frame(self._tabview)
            self._tabview.add(self._frame_raster_container, text="Raster view")

            self._raster_root = tkk.Frame(self._frame_raster_container)
            self._raster_root.pack(fill="both", expand=True)

            self._raster_topbar = tkk.Frame(self._raster_root)
            self._raster_topbar.pack(fill="x", padx=4, pady=(2, 4))

            self._options_toggle_btn = tkk.Button(
                self._raster_topbar,
                text="⮞ Show options",
                command=self._toggle_options_panel,
                bootstyle="secondary"
            )
            self._options_toggle_btn.pack(side="right")

            self._raster_body = tkk.Frame(self._raster_root)
            self._raster_body.pack(fill="both", expand=True)
            self._raster_body.columnconfigure(0, weight=1)
            self._raster_body.rowconfigure(0, weight=1)

            self._plot_container = tkk.Frame(self._raster_body)
            self._plot_container.grid(row=0, column=0, sticky="nsew")

            self._options_panel = tkk.Frame(self._raster_body, padding=(10, 10, 10, 10), relief="ridge", borderwidth=1)
            self._build_options_panel(self._options_panel)
            self._apply_options_panel_visibility()

            # Calibration tab (empty for now)
            self._frame_calibration = tkk.Frame(self._tabview)
            self._tabview.add(self._frame_calibration, text="Calibration")

            # Settings tab (empty for now)
            self._frame_settings = tkk.Frame(self._tabview)
            self._tabview.add(self._frame_settings, text="Settings")

            # Settings content: connection options
            self._settings_serial_port = OptionDropdown(
                self._frame_settings,
                "Serial port",
                ["auto"] + [port.device for port in Serial.listPorts()],
                "auto",
                command=lambda port: self._sensor.setPort(port) if self._sensor else None,
                persistent=True,
            )
            self._settings_serial_port.add_to(self._frame_settings)

            self._settings_wafer_dia = OptionDropdown(
                self._frame_settings,
                "Wafer diameter (mm)",
                [str(v) for v in range(50, 151, 10)],
                "150",
                command=lambda _v: self._rebuild_raster_fig(),
                persistent=True,
            )
            self._settings_wafer_dia.add_to(self._frame_settings)

            self._settings_hide_outside_circle = OptionToggle(
                self._frame_settings,
                "Mask values outside wafer dia.",
                initial=False,
                command=lambda _: self._rebuild_raster_fig(),
                persistent=True,
            )
            self._settings_hide_outside_circle.add_to(self._frame_settings)

            self._color_schemes = getColorSchemes()
            scheme_names = list(self._color_schemes.keys())

            self._settings_color_scheme = OptionDropdown(
                self._frame_settings,
                "Color scheme",
                scheme_names,
                scheme_names[0] if scheme_names else "Grayscale",
                command=lambda _v: self._rebuild_raster_fig(),
                persistent=True,
            )
            self._settings_color_scheme.add_to(self._frame_settings)

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

            # Build plot last, after all UI elements and settings are in place.
            self._rebuild_raster_fig()

    def _rebuild_raster_fig(self) -> None:
        if not self._sensor or not self._sensor.ser or not self._sensor.ser.is_open:
            return
        
        if hasattr(self, '_raster_canvas') and self._raster_canvas is not None:
            self._raster_canvas.get_tk_widget().destroy()

        range_mode = self._range_mode_dropdown.value.get() if hasattr(self, '_range_mode_dropdown') else "manual"
        log_range = self._log_scale_toggle.value.get() if hasattr(self, '_log_scale_toggle') else True
        show_values = self._show_values_toggle.value.get() if hasattr(self, '_show_values_toggle') else False
        wafer_dia = float(self._settings_wafer_dia.value.get()) if hasattr(self, '_settings_wafer_dia') else 150.0
        hide_outside = self._settings_hide_outside_circle.value.get() if hasattr(self, '_settings_hide_outside_circle') else False
        selected_scheme = self._settings_color_scheme.value.get() if hasattr(self, '_settings_color_scheme') else "Grayscale"
        schemes = getattr(self, '_color_schemes', getColorSchemes())
        scheme = schemes.get(selected_scheme, {"colors": ["#000000", "#FFFFFF"], "under": "#000000", "over": "#FFFFFF"})
        color_scheme = scheme.get("colors", ["#000000", "#FFFFFF"])
        use_clipping_colors = self._settings_use_clipping_colors.value.get() if hasattr(self, '_settings_use_clipping_colors') else True
        show_orientation_hint = self._settings_show_orientation_hint.value.get() if hasattr(self, '_settings_show_orientation_hint') else True
        if use_clipping_colors:
            under_color = scheme.get("under", color_scheme[0])
            over_color = scheme.get("over", color_scheme[-1])
        else:
            under_color = color_scheme[0]
            over_color = color_scheme[-1]

        manual_lo_default = 1.0 if log_range else 0.0
        manual_lo = float(getCFGKey("manual_range_lo", manual_lo_default))
        manual_hi = float(getCFGKey("manual_range_hi", 65535.0))
        
        self._raster_fig = RasterFigure(
            np.full((9, 9), np.nan),
            rangeMode=range_mode,
            logRange=log_range,
            showValues=show_values,
            waferDiameterMm=wafer_dia,
            MaskWafer=hide_outside,
            colorScheme=color_scheme,
            underColor=under_color,
            overColor=over_color,
            showOrientationHint=show_orientation_hint,
            manualLo=manual_lo,
            manualHi=manual_hi,
            onManualRangeChange=self._store_manual_range,
        )
        self._raster_canvas = FigureCanvasTkAgg(self._raster_fig, master=self._plot_container)
        self._raster_canvas.draw()
        self._raster_canvas.get_tk_widget().pack(fill="both", expand=True)

        if hasattr(self, '_stream_toggle') and not self._stream_toggle.value.get():
            self._update_measurement()

    def _build_options_panel(self, parent) -> None:
        from ttkbootstrap.scrolled import ScrolledFrame
        self._options_container = ScrolledFrame(parent, autohide=True, bootstyle="round")
        self._options_container.pack(fill="both", expand=True)

        self._options: list[Option] = []

        measurement_section = OptionSection(self._options_container, "Measurement", persistent=True)
        self._add_option(measurement_section)

        self._stream_toggle = OptionToggle(measurement_section.content_frame, "Stream measurements", initial=True, persistent=True)
        measurement_section.add_option(self._stream_toggle)

        def set_freq(freq_str: str) -> None:
            self._measurement_rate = int(freq_str)
            
        measurement_section.add_option(
            OptionDropdown(
                measurement_section.content_frame,
                "Interval (ms)",
                ["50", "100", "200", "500", "1000", "2000"],
                "100",
                command=set_freq,
                visibility=lambda: self._stream_toggle.value.get(),
                persistent=True
            )
        )

        measurement_section.add_option(
            OptionButton(
                measurement_section.content_frame, 
                "Measure", 
                command=self._update_measurement,
                visibility=lambda: not self._stream_toggle.value.get()
            )
        )
        
        display_section = OptionSection(self._options_container, "Display", persistent=True)
        self._add_option(display_section)
        
        self._range_mode_dropdown = OptionDropdown(
            display_section.content_frame, 
            "Range",
            ["auto", "manual", "max"],
            "manual",
            command=lambda _v: self._rebuild_raster_fig(),
            persistent=True
        )
        display_section.add_option(self._range_mode_dropdown)
        
        self._log_scale_toggle = OptionToggle(
            display_section.content_frame, 
            "Log scale", 
            initial=True,
            command=lambda _: self._rebuild_raster_fig(),
            persistent=True
        )
        display_section.add_option(self._log_scale_toggle)

        self._show_values_toggle = OptionToggle(
            display_section.content_frame,
            "Show cell values",
            initial=False,
            command=lambda _: self._rebuild_raster_fig(),
            persistent=True
        )
        display_section.add_option(self._show_values_toggle)

        export_section = OptionSection(self._options_container, "Export", persistent=True)
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
            text="No USB storage detected",
            foreground="red",
            visibility=lambda: not is_usb_available()
        )
        export_section.add_option(lbl)

        calibrate_section = OptionSection(self._options_container, "Calibration", persistent=True)
        self._add_option(calibrate_section)

        self._raw_data_toggle = OptionToggle(
            calibrate_section.content_frame, 
            "Show raw data", 
            initial=True,
            command=lambda _: self._rebuild_raster_fig(),
            persistent=True
        )
        calibrate_section.add_option(self._raw_data_toggle)

    def _toggle_options_panel(self) -> None:
        self._options_panel_visible = not self._options_panel_visible
        self._apply_options_panel_visibility()

    def _apply_options_panel_visibility(self) -> None:
        if not hasattr(self, '_options_panel') or not hasattr(self, '_options_toggle_btn'):
            return

        if self._options_panel_visible:
            self._options_panel.grid(row=0, column=1, sticky="nsew")
            self._options_toggle_btn.configure(text="⮜ Hide options")
        else:
            self._options_panel.grid_forget()
            self._options_toggle_btn.configure(text="⮞ Show options")

        

    def _add_option(self, option: Option) -> None:
        self._options.append(option)
        option.add_to(self._options_container)