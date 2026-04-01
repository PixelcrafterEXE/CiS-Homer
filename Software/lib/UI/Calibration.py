from __future__ import annotations

import threading
import tkinter as tk

import numpy as np
import ttkbootstrap as tkk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from lib.Sensor import positions as _SENSOR_POSITIONS, valid_channel_indices as _VALID_CHANNEL_INDICES
from lib.UI.Options import OptionButton, OptionEntry, OptionToggle

# ── Module-level helpers ──────────────────────────────────────────────────────

# Set of (row, col) grid indices that have a real sensor diode behind them.
_VALID_PIXELS: set[tuple[int, int]] = {
    (py + 4, px + 4)
    for px, py in (p for p in _SENSOR_POSITIONS if p is not None)
}


def _parse_float(s: str) -> float:
    try:
        return float(s.strip())
    except ValueError:
        return np.nan


# ─────────────────────────────────────────────────────────────────────────────
#  Canvas raster widgets
# ─────────────────────────────────────────────────────────────────────────────

class _CalRaster(tk.Canvas):
    """
    Square-cell 9x9 canvas raster for the calibration overview.
    Only cells present in _VALID_PIXELS are drawn.
    Each cell shows the bright ADC value (top half) and dark ADC value (bottom half).
    Clicking a valid cell invokes click_callback(row, col).
    """
    GRID = 9

    def __init__(self, parent, click_callback=None, **kw):
        kw.setdefault("highlightthickness", 0)
        super().__init__(parent, **kw)
        self._click_callback = click_callback
        self._data: np.ndarray = np.full((9, 9, 2), np.nan)
        self._cell_coords: list[tuple[int, int, int, int, int, int]] = []
        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<Button-1>", self._on_click)

    def update_data(self, data: np.ndarray) -> None:
        self._data = data
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")
        self._cell_coords = []
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10 or h < 10:
            return
        cell = min(w // self.GRID, h // self.GRID)
        ox = (w - cell * self.GRID) // 2
        oy = (h - cell * self.GRID) // 2
        fsz = max(6, cell // 6)
        font = ("TkFixedFont", fsz)

        for r in range(self.GRID):
            for c in range(self.GRID):
                if (r, c) not in _VALID_PIXELS:
                    continue
                x0, y0 = ox + c * cell, oy + r * cell
                x1, y1 = x0 + cell, y0 + cell
                self._cell_coords.append((r, c, x0, y0, x1, y1))

                self.create_rectangle(x0, y0, x1, y1,
                                      outline="#666666", fill="#2e2e2e", width=1)

                mid_y = (y0 + y1) // 2
                self.create_line(x0, mid_y, x1, mid_y, fill="#555555", width=1)

                bright = self._data[r, c, 0]
                dark   = self._data[r, c, 1]

                b_text  = str(int(bright)) if not np.isnan(bright) else "-"
                b_color = "#44cc88"        if not np.isnan(bright) else "#555555"
                self.create_text((x0 + x1) // 2, (y0 + mid_y) // 2,
                                 text=b_text, fill=b_color, font=font)

                d_text  = str(int(dark)) if not np.isnan(dark) else "-"
                d_color = "#aa88ff"      if not np.isnan(dark) else "#555555"
                self.create_text((x0 + x1) // 2, (mid_y + y1) // 2,
                                 text=d_text, fill=d_color, font=font)

    def _on_click(self, event) -> None:
        if not self._click_callback:
            return
        for r, c, x0, y0, x1, y1 in self._cell_coords:
            if x0 <= event.x < x1 and y0 <= event.y < y1:
                self._click_callback(r, c)
                return


class _ProgressRaster(tk.Canvas):
    """
    Square-cell 9x9 canvas for wizard calibration progress.
    Captured cells are shown filled with the raw ADC value; uncaptured cells are dim.
    The currently active diode is highlighted in yellow.
    """
    GRID = 9

    def __init__(self, parent, **kw):
        kw.setdefault("highlightthickness", 0)
        super().__init__(parent, **kw)
        self._data: np.ndarray = np.full((9, 9), np.nan)
        self._active_diode: int | None = None
        self.bind("<Configure>", lambda _e: self._redraw())

    def update_data(self, data: np.ndarray, active_diode: int | None = None) -> None:
        self._data = data
        self._active_diode = active_diode
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10 or h < 10:
            return
        cell = min(w // self.GRID, h // self.GRID)
        ox = (w - cell * self.GRID) // 2
        oy = (h - cell * self.GRID) // 2
        fsz = max(5, cell // 6)
        font = ("TkFixedFont", fsz)

        # Determine active pixel position
        active_row, active_col = None, None
        if self._active_diode is not None and self._active_diode < len(_SENSOR_POSITIONS):
            pos = _SENSOR_POSITIONS[self._active_diode]
            if pos is not None:
                px, py = pos
                active_row, active_col = py + 4, px + 4

        for r in range(self.GRID):
            for c in range(self.GRID):
                if (r, c) not in _VALID_PIXELS:
                    continue
                x0, y0 = ox + c * cell, oy + r * cell
                x1, y1 = x0 + cell, y0 + cell
                val  = self._data[r, c]
                done = not np.isnan(val)
                
                # Highlight active pixel in yellow
                is_active = (r == active_row and c == active_col)
                if is_active:
                    fill = "#665500"
                    text_color = "#ffff00"
                    outline_color = "#ffff00"
                    outline_width = 2
                elif done:
                    fill = "#2a5e3a"
                    text_color = "#88ffaa"
                    outline_color = "#666666"
                    outline_width = 1
                else:
                    fill = "#2e2e2e"
                    text_color = "#555555"
                    outline_color = "#666666"
                    outline_width = 1
                
                text = str(int(val)) if done else "."
                self.create_rectangle(x0, y0, x1, y1,
                                      outline=outline_color, fill=fill, width=outline_width)
                self.create_text((x0 + x1) // 2, (y0 + y1) // 2,
                                 text=text, fill=text_color, font=font)


# ─────────────────────────────────────────────────────────────────────────────
#  CalibrationMixin
# ─────────────────────────────────────────────────────────────────────────────

class CalibrationMixin:
    def _build_calibration_tab(self, sensor_active_fn) -> None:
        """Build the calibration tab. sensor_active_fn is a callable that returns True if sensor is connected."""
        self._frame_calibration = tkk.Frame(self._tabview)
        self._tabview.add(self._frame_calibration, text="Calibration")
        self._setup_calibration_tab(sensor_active_fn)

    def _setup_calibration_tab(self, sensor_active_fn) -> None:
        # shape (9, 9, 2): axis-2 is [bright_adc, dark_adc]
        if not hasattr(self, "_cal_data"):
            self._cal_data = np.full((9, 9, 2), np.nan)
        self._cal_streaming = False
        self._cal_fetching  = False
        
        # Disable calibration tab if no sensor is connected
        sensor_active = sensor_active_fn() if callable(sensor_active_fn) else sensor_active_fn
        if not sensor_active:
            for w in self._frame_calibration.winfo_children():
                w.destroy()
            tkk.Label(
                self._frame_calibration,
                text="No sensor detected",
                foreground="red"
            ).pack(expand=True)
            return
        
        self._show_calibration_main()
        self._load_calibration_from_sensor()

        # Reload whenever the user switches to the Calibration tab
        def _on_tab_changed(_event: object) -> None:
            try:
                if self._tabview.index("current") == self._tabview.index(self._frame_calibration):
                    # Only reload if we're on the main calibration page (not inside a wizard)
                    if getattr(self, "_cal_wizard_page", None) is None:
                        self._load_calibration_from_sensor()
            except Exception:
                pass

        self._tabview.bind("<<NotebookTabChanged>>", _on_tab_changed)

    # ─────────────────────────────────────────────────────────────────────────
    #  MAIN PAGE
    # ─────────────────────────────────────────────────────────────────────────

    def _show_calibration_main(self) -> None:
        self._cal_streaming = False
        self._cal_wizard_page = None
        self._cal_prog_lf_widget = None
        for w in self._frame_calibration.winfo_children():
            w.destroy()
        root = self._frame_calibration

        _INFO = (
            "Calibration maps each pixel's raw ADC count to a known irradiance using two reference "
            "points: a bright measurement and a dark measurement.  "
            "Click any cell to edit its values manually, or use the Calibration Wizard."
        )
        tkk.Label(root, text=_INFO, wraplength=720, justify="left").pack(
            fill="x", padx=12, pady=(10, 2)
        )

        # ── Setpoints ─────────────────────────────────────────────────────────
        sp_lf = tkk.LabelFrame(root, text=" Calibration Reference Points ")
        sp_lf.pack(fill="x", padx=12, pady=(0, 4))
        sp_inner = tkk.Frame(sp_lf)
        sp_inner.pack(fill="x", padx=8, pady=6)

        tkk.Label(sp_inner, text="Setpoint 1 (top, bright):").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self._cal_sp1_label = tkk.Label(
            sp_inner,
            text=str(getattr(self, "_cal_setpoint_1", "—")),
            foreground="#44cc88", font=("TkDefaultFont", 10, "bold"),
        )
        self._cal_sp1_label.grid(row=0, column=1, sticky="w")
        tkk.Label(sp_inner, text="µW/mm²").grid(row=0, column=2, sticky="w", padx=(3, 24))

        tkk.Label(sp_inner, text="Setpoint 2 (bottom, dark):").grid(row=0, column=3, sticky="w", padx=(0, 6))
        self._cal_sp2_label = tkk.Label(
            sp_inner,
            text=str(getattr(self, "_cal_setpoint_2", "—")),
            foreground="#aa88ff", font=("TkDefaultFont", 10, "bold"),
        )
        self._cal_sp2_label.grid(row=0, column=4, sticky="w")
        tkk.Label(sp_inner, text="µW/mm²").grid(row=0, column=5, sticky="w", padx=(3, 0))

        self._cal_load_status = tkk.Label(sp_inner, text="", foreground="gray",
                                          font=("TkDefaultFont", 8))
        self._cal_load_status.grid(row=1, column=0, columnspan=6, sticky="w", pady=(2, 0))

        self._cal_raster = _CalRaster(root, click_callback=self._show_edit_page)
        self._cal_raster.pack(fill="both", expand=True, padx=12, pady=4)
        self._cal_raster.update_data(self._cal_data)

        btn_bar = tkk.Frame(root)
        btn_bar.pack(fill="x", padx=12, pady=(4, 12))
        btn_bar.columnconfigure(0, weight=1)
        btn_bar.columnconfigure(1, weight=1)
        btn_bar.columnconfigure(2, weight=1)
        btn_bar.columnconfigure(3, weight=1)
        tk.Button(btn_bar, text="Load from Sensor",
                  command=self._load_calibration_from_sensor).grid(row=0, column=0, padx=4, sticky="ew")
        tk.Button(btn_bar, text="Save to Sensor",
                  command=self._save_calibration).grid(row=0, column=1, padx=4, sticky="ew")
        tk.Button(btn_bar, text="Reset Calibration",
                  command=self._reset_calibration).grid(row=0, column=2, padx=4, sticky="ew")
        tk.Button(btn_bar, text="Start Calibration Wizard",
                  command=self._start_calibration_wizard).grid(row=0, column=3, padx=4, sticky="ew")

    def _refresh_cal_raster(self) -> None:
        if hasattr(self, "_cal_raster"):
            self._cal_raster.update_data(self._cal_data)

    # ─────────────────────────────────────────────────────────────────────────
    #  EDIT PIXEL PAGE
    # ─────────────────────────────────────────────────────────────────────────

    def _show_edit_page(self, row: int, col: int) -> None:
        self._cal_streaming = False
        self._cal_wizard_page = "edit"
        self._cal_prog_lf_widget = None
        self._cal_edit_row = row
        self._cal_edit_col = col
        for w in self._frame_calibration.winfo_children():
            w.destroy()
        root = self._frame_calibration

        tkk.Label(
            root,
            text=f"Pixel  row {row + 1},  column {col + 1}",
            font=("TkDefaultFont", 12, "bold"),
        ).pack(padx=12, pady=(12, 6))

        # ── Manual entry ───────────────────────────────────────────────────
        t_bright_opt = getattr(self, "_cal_opt_target_bright", None)
        t_dark_opt   = getattr(self, "_cal_opt_target_dark",   None)
        tb_str = t_bright_opt.value.get() if t_bright_opt else "?"
        td_str = t_dark_opt.value.get()   if t_dark_opt   else "?"

        manual_lf = tkk.LabelFrame(root, text=" Manual Entry ")
        manual_lf.pack(fill="x", padx=12, pady=4)

        b_init = "" if np.isnan(self._cal_data[row, col, 0]) else str(int(self._cal_data[row, col, 0]))
        d_init = "" if np.isnan(self._cal_data[row, col, 1]) else str(int(self._cal_data[row, col, 1]))

        self._edit_bright_opt = OptionEntry(
            manual_lf, f"Bright reference  (setpoint: {tb_str} µW/mm²):",
            initial=b_init, numeric=True)
        self._edit_bright_opt.add_to(manual_lf)

        self._edit_dark_opt = OptionEntry(
            manual_lf, f"Dark reference  (setpoint: {td_str} µW/mm²):",
            initial=d_init, numeric=True)
        self._edit_dark_opt.add_to(manual_lf)

        # ── Live measurement ───────────────────────────────────────────────
        live_lf = tkk.LabelFrame(root, text=" Live Measurement ")
        live_lf.pack(fill="both", expand=True, padx=12, pady=4)

        self._cal_graph_canvas = None
        self._cal_sensor_history = []
        self._build_cal_live_graph(live_lf)

        cap_bar = tkk.Frame(live_lf)
        cap_bar.pack(fill="x", pady=(4, 4))
        OptionButton(cap_bar, text="Capture as Bright",
                     command=lambda: self._cal_capture_edit("bright")).add_to(cap_bar)
        OptionButton(cap_bar, text="Capture as Dark",
                     command=lambda: self._cal_capture_edit("dark")).add_to(cap_bar)

        # ── Navigation ─────────────────────────────────────────────────────
        def _apply() -> None:
            self._cal_data[row, col, 0] = _parse_float(self._edit_bright_opt.value.get())
            self._cal_data[row, col, 1] = _parse_float(self._edit_dark_opt.value.get())
            self._cal_streaming = False
            self._show_calibration_main()

        def _clear() -> None:
            self._cal_data[row, col, :] = np.nan
            self._cal_streaming = False
            self._show_calibration_main()

        def _back() -> None:
            self._cal_streaming = False
            self._show_calibration_main()

        nav = tkk.Frame(root)
        nav.pack(fill="x", padx=12, pady=(4, 12))
        tk.Button(nav, text="Apply",  command=_apply).pack(side="left", padx=4)
        tk.Button(nav, text="Clear",  command=_clear).pack(side="left", padx=4)
        tk.Button(nav, text="Back",   command=_back ).pack(side="left", padx=4)

        self._cal_streaming = True
        self._cal_live_stream_loop()

    def _cal_capture_edit(self, dataset: str) -> None:
        h = self._cal_sensor_history
        if not h:
            return
        val = h[-1]
        if np.isnan(val):
            return
        row, col = self._cal_edit_row, self._cal_edit_col
        idx = 0 if dataset == "bright" else 1
        self._cal_data[row, col, idx] = val
        opt = self._edit_bright_opt if dataset == "bright" else self._edit_dark_opt
        opt.value.set(str(int(val)))

    # ─────────────────────────────────────────────────────────────────────────
    #  MAIN PAGE ACTIONS
    # ─────────────────────────────────────────────────────────────────────────

    def _save_calibration(self) -> None:
        if not self._sensor_active():
            self._show_error("Save failed: sensor not connected.")
            return

        channel_values = np.zeros((61, 2), dtype=np.uint16)
        for ch_idx, sensor_idx in enumerate(_VALID_CHANNEL_INDICES):
            pos = _SENSOR_POSITIONS[sensor_idx]
            if pos is None:
                continue
            px, py = pos
            row, col = py + 4, px + 4
            v0 = self._cal_data[row, col, 0]
            v1 = self._cal_data[row, col, 1]
            channel_values[ch_idx, 0] = 0 if np.isnan(v0) else int(np.clip(v0, 0, 65535))
            channel_values[ch_idx, 1] = 0 if np.isnan(v1) else int(np.clip(v1, 0, 65535))

        sp1 = getattr(self, "_cal_setpoint_1", 1000)
        sp2 = getattr(self, "_cal_setpoint_2", 1200)

        if hasattr(self, "_cal_load_status"):
            self._cal_load_status.configure(text="Saving to sensor…", foreground="gray")

        def _write() -> None:
            try:
                self._sensor.writeCalibration(
                    channel_values=channel_values,
                    setpoint_1=int(sp1),
                    setpoint_2=int(sp2),
                )
                self.after(0, lambda: (
                    self._cal_load_status.configure(text="Saved.", foreground="#44cc88")
                    if hasattr(self, "_cal_load_status") else None
                ))
            except Exception as e:
                self.after(0, lambda msg=str(e): (
                    self._show_error(f"Save failed: {msg}"),
                    self._cal_load_status.configure(text=f"Save failed: {msg}", foreground="red")
                    if hasattr(self, "_cal_load_status") else None,
                ))

        threading.Thread(target=_write, daemon=True).start()

    def _load_calibration_from_sensor(self) -> None:
        """Read calibration EEPROM and populate _cal_data + setpoint labels."""
        if not self._sensor_active():
            return
        if hasattr(self, "_cal_load_status"):
            self._cal_load_status.configure(text="Loading from sensor…", foreground="gray")

        def _fetch() -> None:
            try:
                cal = self._sensor.readCalibration()
                new_data = np.full((9, 9, 2), np.nan)
                for ch_idx, sensor_idx in enumerate(_VALID_CHANNEL_INDICES):
                    pos = _SENSOR_POSITIONS[sensor_idx]
                    if pos is None:
                        continue
                    px, py = pos
                    row, col = py + 4, px + 4
                    new_data[row, col, 0] = float(cal["channel_values"][ch_idx, 0])
                    new_data[row, col, 1] = float(cal["channel_values"][ch_idx, 1])
                self.after(0, lambda d=new_data, s1=cal["setpoint_1"], s2=cal["setpoint_2"]:
                           self._apply_loaded_calibration(d, s1, s2))
            except Exception as e:
                self.after(0, lambda msg=str(e): self._on_cal_load_error(msg))

        threading.Thread(target=_fetch, daemon=True).start()

    def _apply_loaded_calibration(self, data: np.ndarray, sp1: int, sp2: int) -> None:
        self._cal_data = data
        self._cal_setpoint_1 = sp1
        self._cal_setpoint_2 = sp2
        if hasattr(self, "_cal_raster"):
            self._cal_raster.update_data(data)
        if hasattr(self, "_cal_sp1_label"):
            self._cal_sp1_label.configure(text=str(sp1))
        if hasattr(self, "_cal_sp2_label"):
            self._cal_sp2_label.configure(text=str(sp2))
        if hasattr(self, "_cal_load_status"):
            self._cal_load_status.configure(text="Loaded from sensor.", foreground="#44cc88")

    def _on_cal_load_error(self, msg: str) -> None:
        if hasattr(self, "_cal_load_status"):
            self._cal_load_status.configure(text=f"Load failed: {msg}", foreground="red")
        self._show_error(f"Calibration load failed: {msg}")

    def _reset_calibration(self) -> None:
        # Reset channel data: dark=0, bright=500
        for r in range(9):
            for c in range(9):
                if (r, c) in _VALID_PIXELS:
                    self._cal_data[r, c, 0] = 500  # bright
                    self._cal_data[r, c, 1] = 0    # dark
        # Reset setpoints to firmware defaults
        self._cal_setpoint_1 = 1000
        self._cal_setpoint_2 = 1200
        if hasattr(self, "_cal_sp1_label"):
            self._cal_sp1_label.configure(text="1000")
        if hasattr(self, "_cal_sp2_label"):
            self._cal_sp2_label.configure(text="1200")
        if hasattr(self, "_cal_load_status"):
            self._cal_load_status.configure(text="Reset to defaults.", foreground="gray")
        self._refresh_cal_raster()

    # ─────────────────────────────────────────────────────────────────────────
    #  WIZARD SCAFFOLDING
    # ─────────────────────────────────────────────────────────────────────────

    def _start_calibration_wizard(self) -> None:
        self._cal_auto_measure_val  = False
        self._cal_dark_cover_val    = False
        self._cal_target_dark_str   = str(getattr(self, "_cal_setpoint_2", 1200))
        self._cal_target_bright_str = str(getattr(self, "_cal_setpoint_1", 1000))
        self._cal_opt_target_bright = None
        self._cal_opt_target_dark   = None
        self._cal_opt_auto_measure  = None
        self._cal_opt_dark_cover    = None
        self._cal_bright_data    = np.full((9, 9), np.nan)
        self._cal_dark_data      = np.full((9, 9), np.nan)
        self._cal_sensor_history = []
        self._cal_active_diode   = 0
        self._cal_streaming      = False
        self._cal_fetching       = False
        self._cal_prog_lf_widget = None
        self._show_wizard_page(1)

    def _show_wizard_page(self, page: int) -> None:
        self._cal_streaming      = False
        self._cal_wizard_page    = page
        self._cal_prog_lf_widget = None
        for w in self._frame_calibration.winfo_children():
            w.destroy()
        {
            1: self._build_wizard_page1,
            2: self._build_wizard_page2,
            3: self._build_wizard_page3,
            4: self._build_wizard_page4,
        }.get(page, self._wizard_finish)()

    def _wizard_nav(self, parent, back_cmd=None, next_cmd=None,
                    back_label="Back", next_label="Next") -> None:
        bar = tkk.Frame(parent)
        bar.pack(fill="x", padx=10, pady=(4, 10), side="bottom")
        if back_cmd:
            tk.Button(bar, text=back_label, command=back_cmd).pack(side="left", padx=4)
        tk.Button(bar, text="Cancel", command=self._show_calibration_main).pack(side="left", padx=4)
        if next_cmd:
            tk.Button(bar, text=next_label, command=next_cmd).pack(side="right", padx=4)

    # ─────────────────────────────────────────────────────────────────────────
    #  PAGE 1 — Dark target + cover shortcut
    # ─────────────────────────────────────────────────────────────────────────

    def _build_wizard_page1(self) -> None:
        root = self._frame_calibration

        tkk.Label(root, text="Step 1 of 4  -  Dark Reference",
                  font=("TkDefaultFont", 13, "bold")).pack(padx=12, pady=(14, 2))
        tkk.Label(
            root,
            text=(
                "Set the reference value for the dark calibration point.  "
                "Enable auto-measure to capture the brightest pixel automatically when its "
                "reading stabilises.  Alternatively, cover the entire sensor and use the "
                "shortcut below to capture all pixels at once and skip page 2."
            ),
            wraplength=700, justify="left",
        ).pack(padx=12, pady=(0, 8))

        form = tkk.LabelFrame(root, text=" Settings ")
        form.pack(fill="x", padx=12, pady=4)

        self._cal_opt_target_dark = OptionEntry(
            form, "Target dark value  (µW/mm²):",
            initial=self._cal_target_dark_str, numeric=True,
            command=lambda v: (
                setattr(self, "_cal_target_dark_str", v),
                setattr(self, "_cal_setpoint_2", int(v) if v.strip().isdigit() else getattr(self, "_cal_setpoint_2", 1200)),
            ),
        )
        self._cal_opt_target_dark.add_to(form)

        self._cal_opt_auto_measure = OptionToggle(
            form, "Auto-measure  (capture brightest pixel when stable)",
            initial=self._cal_auto_measure_val,
            command=lambda v: setattr(self, "_cal_auto_measure_val", v),
        )
        self._cal_opt_auto_measure.add_to(form)

        cover_lf = tkk.LabelFrame(root, text=" Cover-sensor shortcut ")
        cover_lf.pack(fill="x", padx=12, pady=4)
        tkk.Label(
            cover_lf,
            text=(
                "Cover the entire sensor so that every diode receives zero irradiance, "
                "then enable the toggle below.  Page 2 will be skipped: a single frame "
                "is captured for all pixels simultaneously."
            ),
            wraplength=660, justify="left",
        ).pack(fill="x", padx=8, pady=(4, 2))

        self._cal_opt_dark_cover = OptionToggle(
            cover_lf, "Calibrate via full cover  (skip page 2):",
            initial=self._cal_dark_cover_val,
            command=lambda v: self._on_dark_cover_toggle(v),
        )
        self._cal_opt_dark_cover.add_to(cover_lf)

        def _next() -> None:
            if self._cal_dark_cover_val:
                self._cal_dark_all_pixels()
                self._show_wizard_page(3)
            else:
                self._show_wizard_page(2)

        next_label = "Calibrate Dark" if self._cal_dark_cover_val else "Next"
        
        # Create navigation bar and store reference to next button
        bar = tkk.Frame(root)
        bar.pack(fill="x", padx=10, pady=(4, 10), side="bottom")
        tk.Button(bar, text="Back", command=self._show_calibration_main).pack(side="left", padx=4)
        tk.Button(bar, text="Cancel", command=self._show_calibration_main).pack(side="left", padx=4)
        self._cal_page1_next_btn = tk.Button(bar, text=next_label, command=_next)
        self._cal_page1_next_btn.pack(side="right", padx=4)

    def _on_dark_cover_toggle(self, enabled: bool) -> None:
        """Update the next button text when cover shortcut toggle changes."""
        setattr(self, "_cal_dark_cover_val", enabled)
        if hasattr(self, '_cal_page1_next_btn'):
            new_label = "Calibrate Dark" if enabled else "Next"
            self._cal_page1_next_btn.configure(text=new_label)

    # ─────────────────────────────────────────────────────────────────────────
    #  PAGE 2 — Dark measurement
    # ─────────────────────────────────────────────────────────────────────────

    def _build_wizard_page2(self) -> None:
        root = self._frame_calibration

        tkk.Label(root, text="Step 2 of 4  -  Dark Measurement",
                  font=("TkDefaultFont", 13, "bold")).pack(padx=12, pady=(14, 2))
        tkk.Label(
            root,
            text=(
                "Live ADC reading of the currently brightest diode is plotted below.  "
                "Position your dark source or attenuated light over each pixel in turn and capture it."
            ),
            wraplength=700, justify="left",
        ).pack(padx=12, pady=(0, 4))

        graph_lf = tkk.LabelFrame(root, text=" Active diode - live ADC reading ")
        graph_lf.pack(fill="both", expand=True, padx=12, pady=4)
        self._cal_graph_canvas = None
        self._build_cal_live_graph(graph_lf)

        prog_lf = tkk.LabelFrame(root, text=" Calibrated pixels  (green = captured, yellow = active) ")
        prog_lf.pack(fill="x", padx=12, pady=4)
        self._cal_prog_lf_widget = _ProgressRaster(prog_lf, height=120)
        self._cal_prog_lf_widget.pack(fill="x")
        self._cal_prog_lf_widget.update_data(self._cal_dark_data, active_diode=getattr(self, '_cal_active_diode', None))

        if not self._cal_auto_measure_val:
            OptionButton(root, text="Calibrate Pixel",
                         command=lambda: self._cal_capture_pixel("dark")).add_to(root)

        self._wizard_nav(root,
                         back_cmd=lambda: self._show_wizard_page(1),
                         next_cmd=lambda: self._show_wizard_page(3))

        self._cal_streaming = True
        self._cal_sensor_history = []
        self._cal_live_stream_loop()

    # ─────────────────────────────────────────────────────────────────────────
    #  PAGE 3 — Bright target
    # ─────────────────────────────────────────────────────────────────────────

    def _build_wizard_page3(self) -> None:
        root = self._frame_calibration

        tkk.Label(root, text="Step 3 of 4  -  Bright Reference",
                  font=("TkDefaultFont", 13, "bold")).pack(padx=12, pady=(14, 2))
        tkk.Label(
            root,
            text=(
                "Set the reference irradiance for the bright calibration point and position your "
                "light source over the sensor.  Enable auto-measure to capture the brightest "
                "pixel automatically when its reading stabilises."
            ),
            wraplength=700, justify="left",
        ).pack(padx=12, pady=(0, 8))

        form = tkk.LabelFrame(root, text=" Settings ")
        form.pack(fill="x", padx=12, pady=4)

        self._cal_opt_target_bright = OptionEntry(
            form, "Target brightness  (µW/mm²):",
            initial=self._cal_target_bright_str, numeric=True,
            command=lambda v: (
                setattr(self, "_cal_target_bright_str", v),
                setattr(self, "_cal_setpoint_1", int(v) if v.strip().isdigit() else getattr(self, "_cal_setpoint_1", 1000)),
            ),
        )
        self._cal_opt_target_bright.add_to(form)

        self._cal_opt_auto_measure = OptionToggle(
            form, "Auto-measure  (capture brightest pixel when stable)",
            initial=self._cal_auto_measure_val,
            command=lambda v: setattr(self, "_cal_auto_measure_val", v),
        )
        self._cal_opt_auto_measure.add_to(form)

        def _back() -> None:
            # skip page 2 if cover shortcut was used
            if self._cal_dark_cover_val:
                self._show_wizard_page(1)
            else:
                self._show_wizard_page(2)

        self._wizard_nav(root, back_cmd=_back,
                         next_cmd=lambda: self._show_wizard_page(4))

    # ─────────────────────────────────────────────────────────────────────────
    #  PAGE 4 — Bright measurement
    # ─────────────────────────────────────────────────────────────────────────

    def _build_wizard_page4(self) -> None:
        root = self._frame_calibration

        tkk.Label(root, text="Step 4 of 4  -  Bright Measurement",
                  font=("TkDefaultFont", 13, "bold")).pack(padx=12, pady=(14, 2))
        tkk.Label(
            root,
            text=(
                "Live ADC reading of the currently brightest diode is plotted below.  "
                "Move the light source over each pixel in turn and capture it."
            ),
            wraplength=700, justify="left",
        ).pack(padx=12, pady=(0, 4))

        graph_lf = tkk.LabelFrame(root, text=" Active diode - live ADC reading ")
        graph_lf.pack(fill="both", expand=True, padx=12, pady=4)
        self._cal_graph_canvas = None
        self._build_cal_live_graph(graph_lf)

        prog_lf = tkk.LabelFrame(root, text=" Calibrated pixels  (green = captured, yellow = active) ")
        prog_lf.pack(fill="x", padx=12, pady=4)
        self._cal_prog_lf_widget = _ProgressRaster(prog_lf, height=120)
        self._cal_prog_lf_widget.pack(fill="x")
        self._cal_prog_lf_widget.update_data(self._cal_bright_data, active_diode=getattr(self, '_cal_active_diode', None))

        if not self._cal_auto_measure_val:
            OptionButton(root, text="Calibrate Pixel",
                         command=lambda: self._cal_capture_pixel("bright")).add_to(root)

        self._wizard_nav(root,
                         back_cmd=lambda: self._show_wizard_page(3),
                         next_cmd=self._wizard_finish, next_label="Finish")

        self._cal_streaming = True
        self._cal_sensor_history = []
        self._cal_live_stream_loop()

    # ─────────────────────────────────────────────────────────────────────────
    #  LIVE GRAPH
    # ─────────────────────────────────────────────────────────────────────────

    def _build_cal_live_graph(self, parent) -> None:
        fig = Figure(figsize=(6, 1.8), tight_layout=True)
        self._cal_live_fig = fig
        ax = fig.add_subplot(111)
        self._cal_live_ax = ax
        ax.set_xlabel("Sample", fontsize=8)
        ax.set_ylabel("ADC counts (log)", fontsize=8)
        ax.set_yscale("log")
        ax.set_ylim(1, 65535)  # Start from 1 for log scale
        ax.tick_params(labelsize=7)
        (self._cal_live_line,) = ax.plot([], [], color="#4ea6dc", lw=1.5, label="active diode")
        self._cal_live_peak_line = ax.axhline(
            y=float("nan"), color="#ff8844", lw=1.0, linestyle="--", label="peak since last change"
        )
        # Store all diode change lines
        self._cal_diode_change_lines = []
        ax.legend(fontsize=7, loc="upper left")
        
        # Add reset button below the graph
        btn_frame = tkk.Frame(parent)
        btn_frame.pack(fill="x", pady=(2, 0))
        tkk.Button(btn_frame, text="Reset History", command=self._reset_cal_history,
                   bootstyle="secondary-outline").pack(side="right", padx=4)
        
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self._cal_graph_canvas = canvas
        self._cal_last_active_diode = None
        self._cal_diode_change_indices = []  # Track all diode change positions
        self._cal_last_diode_change_idx = 0  # Index of last diode change for peak calculation

    def _reset_cal_history(self) -> None:
        """Reset the calibration history and clear diode change markers."""
        self._cal_sensor_history = []
        self._cal_diode_change_indices = []
        self._cal_last_diode_change_idx = 0
        # Clear all diode change lines from the plot
        if hasattr(self, '_cal_diode_change_lines'):
            for line in self._cal_diode_change_lines:
                line.remove()
            self._cal_diode_change_lines = []
        self._update_cal_live_graph()

    def _cal_live_stream_loop(self) -> None:
        if not self._cal_streaming:
            return
        if self._cal_fetching:
            self.after(80, self._cal_live_stream_loop)
            return
        self._cal_fetching = True

        def _fetch() -> None:
            try:
                if not self._sensor_active():
                    val = float("nan")
                    self._cal_active_diode = 0
                else:
                    raw = self._sensor.getRaw()
                    valid_idx = [i for i, p in enumerate(_SENSOR_POSITIONS) if p is not None]
                    
                    # In edit mode, only read from the specific pixel being edited
                    page = getattr(self, "_cal_wizard_page", None)
                    if page == "edit" and hasattr(self, '_cal_edit_row') and hasattr(self, '_cal_edit_col'):
                        # Read only the pixel being edited
                        row, col = self._cal_edit_row, self._cal_edit_col
                        # Find the diode index for this row/col
                        px, py = col - 4, row - 4
                        try:
                            idx = _SENSOR_POSITIONS.index((px, py))
                            val = float(raw[idx])
                            self._cal_active_diode = idx
                        except (ValueError, IndexError):
                            val = float("nan")
                            self._cal_active_diode = 0
                    else:
                        # In wizard mode, track the brightest diode
                        active = int(valid_idx[int(np.argmax([raw[i] for i in valid_idx]))])
                        val = float(raw[active])
                        self._cal_active_diode = active
            except Exception:
                val = float("nan")
            finally:
                self._cal_fetching = False

            self._cal_sensor_history.append(val)
            if len(self._cal_sensor_history) > 200:
                self._cal_sensor_history = self._cal_sensor_history[-200:]

            page = getattr(self, "_cal_wizard_page", None)
            if (
                getattr(self, "_cal_auto_measure_val", False)
                and page in (2, 4)
                and len(self._cal_sensor_history) >= 6
                and not np.isnan(val)
            ):
                recent = self._cal_sensor_history[-6:]
                if np.std(recent) < 800 and np.mean(recent) > 300:
                    ds = "dark" if page == 2 else "bright"
                    self.after(0, lambda d=ds: self._cal_capture_pixel(d))

            self.after(0, self._update_cal_live_graph)

        threading.Thread(target=_fetch, daemon=True).start()
        self.after(150, self._cal_live_stream_loop)

    def _update_cal_live_graph(self) -> None:
        if not self._cal_streaming:
            return
        if not hasattr(self, "_cal_live_ax") or self._cal_graph_canvas is None:
            return
        h = self._cal_sensor_history
        if not h:
            return
        
        # Track diode changes and mark ALL of them on graph
        if hasattr(self, '_cal_active_diode') and hasattr(self, '_cal_last_active_diode'):
            if self._cal_last_active_diode is not None and self._cal_active_diode != self._cal_last_active_diode:
                # Diode changed - record this position
                change_idx = len(h) - 1
                if not hasattr(self, '_cal_diode_change_indices'):
                    self._cal_diode_change_indices = []
                self._cal_diode_change_indices.append(change_idx)
                self._cal_last_diode_change_idx = change_idx
                
                # Add a new vertical line for this diode change
                if not hasattr(self, '_cal_diode_change_lines'):
                    self._cal_diode_change_lines = []
                line = self._cal_live_ax.axvline(
                    x=change_idx, color="#ff4444", lw=1.0, linestyle=":", alpha=0.7
                )
                self._cal_diode_change_lines.append(line)
            self._cal_last_active_diode = self._cal_active_diode
        
        self._cal_live_line.set_data(list(range(len(h))), h)
        self._cal_live_ax.set_xlim(0, max(len(h) - 1, 1))
        
        # Calculate peak since last diode change (not overall peak)
        if not hasattr(self, '_cal_last_diode_change_idx'):
            self._cal_last_diode_change_idx = 0
        recent_data = h[self._cal_last_diode_change_idx:]
        valid = [v for v in recent_data if not np.isnan(v) and v > 0]  # Exclude 0 for log scale
        if valid:
            self._cal_live_peak_line.set_ydata([max(valid), max(valid)])
        
        # Update the progress raster with the current active diode highlighted
        if hasattr(self, '_cal_prog_lf_widget') and self._cal_prog_lf_widget is not None:
            page = getattr(self, "_cal_wizard_page", None)
            if page == 2:
                self._cal_prog_lf_widget.update_data(self._cal_dark_data, active_diode=getattr(self, '_cal_active_diode', None))
            elif page == 4:
                self._cal_prog_lf_widget.update_data(self._cal_bright_data, active_diode=getattr(self, '_cal_active_diode', None))
        
        try:
            self._cal_graph_canvas.draw_idle()
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    #  CAPTURE HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _cal_capture_pixel(self, dataset: str) -> None:
        """Record the active diode's latest reading into the wizard dataset."""
        h = self._cal_sensor_history
        if not h:
            return
        val = h[-1]
        if np.isnan(val):
            return
        idx = self._cal_active_diode
        if idx < len(_SENSOR_POSITIONS) and _SENSOR_POSITIONS[idx] is not None:
            px, py = _SENSOR_POSITIONS[idx]
            row, col = py + 4, px + 4
            if 0 <= row < 9 and 0 <= col < 9:
                if dataset == "dark":
                    self._cal_dark_data[row, col] = val
                else:
                    self._cal_bright_data[row, col] = val
                w = self._cal_prog_lf_widget
                if w is not None:
                    data = self._cal_dark_data if dataset == "dark" else self._cal_bright_data
                    w.update_data(data, active_diode=self._cal_active_diode)

    def _cal_dark_all_pixels(self) -> None:
        """Capture a single raw frame and store every channel as its dark reference."""
        if not self._sensor_active():
            return
        try:
            raw = self._sensor.getRaw()
            for idx, pos in enumerate(_SENSOR_POSITIONS):
                if pos is None or idx >= len(raw):
                    continue
                px, py = pos
                r, c = py + 4, px + 4
                if 0 <= r < 9 and 0 <= c < 9:
                    self._cal_dark_data[r, c] = float(raw[idx])
        except Exception as e:
            print(f"[CalibrationMixin] Dark-cover capture error: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    #  FINISH
    # ─────────────────────────────────────────────────────────────────────────

    def _wizard_finish(self) -> None:
        self._cal_streaming = False
        for r in range(9):
            for c in range(9):
                b = self._cal_bright_data[r, c]
                d = self._cal_dark_data[r, c]
                if not np.isnan(b):
                    self._cal_data[r, c, 0] = b
                if not np.isnan(d):
                    self._cal_data[r, c, 1] = d
        self._show_calibration_main()




