from __future__ import annotations

import numpy as np
import ttkbootstrap as tkk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from lib.Config import getColorSchemes, setCFGKey
from lib.Plotting import RasterFigure
from lib.UI.Options import Option, OptionButton, OptionDropdown, OptionEntry, OptionLabel, OptionSlider, OptionToggle


class VisualizerMixin:
    def _build_visualizer_tab(self, sensor_active: bool) -> None:
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
            text="⮝ Show options ⮝",
            command=self._toggle_options_panel,
            bootstyle="secondary",
        )
        self._options_toggle_btn.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        self._options_panel = tkk.Frame(self._raster_body, padding=10, relief="ridge", borderwidth=1)
        self._build_options_panel(self._options_panel)
        self._apply_options_panel_visibility()

        if sensor_active:
            self._rebuild_raster_fig()
        else:
            self._raster_canvas = None
            tkk.Label(self._plot_container, text="No sensor detected", foreground="red").pack(expand=True)

    def _build_options_panel(self, parent) -> None:
        self._options = []

        cols_container = tkk.Frame(parent)
        cols_container.pack(fill="both", expand=True)

        cols_container.columnconfigure(0, weight=1, uniform="group1")
        cols_container.columnconfigure(1, weight=1, uniform="group1")
        cols_container.columnconfigure(2, weight=1, uniform="group1")
        cols_container.rowconfigure(0, weight=1)

        # --- COLUMN 1: MEASUREMENT ---
        col_meas = tkk.LabelFrame(cols_container, text=" Measurement ")
        col_meas.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self._stream_toggle = OptionToggle(col_meas, "Stream measurements", initial=True, persistent=True)
        self._add_option(self._stream_toggle, col_meas)

        self._add_option(OptionDropdown(
            col_meas, "Interval (ms)", ["50", "100", "200", "500", "1000"], "100",
            command=lambda f: setattr(self, '_measurement_rate', int(f)),
            visibility=lambda: self._stream_toggle.value.get(), persistent=True,
        ), col_meas)

        self._add_option(OptionButton(
            col_meas, "Manual Measure", command=self._update_measurement,
            visibility=lambda: not self._stream_toggle.value.get(),
        ), col_meas)

        self._data_source_dropdown = OptionDropdown(
            col_meas, "Data source", ["raw", "calibrated", "mW/mm²"], "raw",
            command=lambda _v: self._update_measurement(), persistent=True,
        )
        self._add_option(self._data_source_dropdown, col_meas)

        # --- COLUMN 2: DISPLAY ---
        col_disp = tkk.LabelFrame(cols_container, text=" Display ")
        col_disp.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        self._range_mode_dropdown = OptionDropdown(
            col_disp, "Range", ["auto", "manual", "max"], "manual",
            command=lambda _v: self._rebuild_raster_fig(), persistent=True,
        )
        self._add_option(self._range_mode_dropdown, col_disp)

        self._log_scale_toggle = OptionToggle(
            col_disp, "Log scale", initial=True,
            command=lambda _: self._rebuild_raster_fig(), persistent=True,
        )
        self._add_option(self._log_scale_toggle, col_disp)

        self._label_measurements_toggle = OptionToggle(
            col_disp, "Label Measurements", initial=False,
            command=lambda _: self._rebuild_raster_fig(), persistent=True,
        )
        self._add_option(self._label_measurements_toggle, col_disp)

        # --- COLUMN 3: EXPORT ---
        col_exp = tkk.LabelFrame(cols_container, text=" Export ")
        col_exp.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)

        from lib.Export import export_data, is_usb_available

        self._add_option(OptionButton(
            col_exp, "Export CSV to USB", command=lambda: export_data(self._sensor),
            visibility=is_usb_available,
        ), col_exp)

        self._add_option(OptionLabel(
            col_exp, text="No USB storage detected", foreground="red",
            visibility=lambda: not is_usb_available(),
        ), col_exp)

        # ── Keyboard test fields ──────────────────────────────────────────────
        self._add_option(OptionEntry(
            col_exp, "Text", placeholder="type here…",
        ), col_exp)

        self._add_option(OptionEntry(
            col_exp, "Number", placeholder="0", numeric=True,
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
            self._options_toggle_btn.configure(text="⮟ Hide options ⮟")
        else:
            self._options_panel.grid_forget()
            self._options_toggle_btn.configure(text="⮝ Show options ⮝")

    def _store_manual_range(self, lo: float, hi: float) -> None:
        setCFGKey("manual_range_lo", float(lo))
        setCFGKey("manual_range_hi", float(hi))

    def _rebuild_raster_fig(self) -> None:
        if not self._sensor_active():
            return
        if hasattr(self, '_raster_canvas') and self._raster_canvas:
            self._raster_canvas.get_tk_widget().destroy()

        range_mode = self._range_mode_dropdown.value.get() if hasattr(self, '_range_mode_dropdown') else "manual"
        log_range = self._log_scale_toggle.value.get() if hasattr(self, '_log_scale_toggle') else True
        show_values = self._label_measurements_toggle.value.get() if hasattr(self, '_label_measurements_toggle') else False

        # Settings-panel values
        wafer_mm = float(self._wafer_diameter_dropdown.value.get()) if hasattr(self, '_wafer_diameter_dropdown') else 150.0
        mask_wafer = self._mask_wafer_toggle.value.get() if hasattr(self, '_mask_wafer_toggle') else False
        show_hint = self._settings_show_orientation_hint.value.get() if hasattr(self, '_settings_show_orientation_hint') else True
        use_clip = self._settings_use_clipping_colors.value.get() if hasattr(self, '_settings_use_clipping_colors') else True

        color_schemes = getattr(self, '_color_schemes', {})
        scheme_name = self._color_scheme_dropdown.value.get() if hasattr(self, '_color_scheme_dropdown') else ""
        scheme = color_schemes.get(scheme_name, {})
        color_list = scheme.get("colors") or ['black', 'white']
        under_color = scheme.get("under", 'black') if use_clip else color_list[0]
        over_color = scheme.get("over", 'white') if use_clip else color_list[-1]

        self._raster_fig = RasterFigure(
            np.full((9, 9), np.nan),
            rangeMode=range_mode,
            logRange=log_range,
            showValues=show_values,
            waferDiameterMm=wafer_mm,
            MaskWafer=mask_wafer,
            colorScheme=color_list,
            underColor=under_color,
            overColor=over_color,
            showOrientationHint=show_hint,
        )
        self._raster_canvas = FigureCanvasTkAgg(self._raster_fig, master=self._plot_container)
        self._raster_canvas.draw()
        self._raster_canvas.get_tk_widget().pack(fill="both", expand=True)
