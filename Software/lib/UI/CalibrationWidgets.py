"""Calibration UI widgets: _CalRaster for overview, _ProgressRaster for measurement progress."""

from __future__ import annotations

import tkinter as tk

import numpy as np
from lib.Sensor import positions as _SENSOR_POSITIONS


# Set of (row, col) grid indices that have a real sensor diode behind them.
_VALID_PIXELS: set[tuple[int, int]] = {
    (py + 4, px + 4)
    for px, py in (p for p in _SENSOR_POSITIONS if p is not None)
}


class CalRaster(tk.Canvas):
    """
    Square-cell 9x9 canvas raster for the calibration overview.
    Only cells present in _VALID_PIXELS are drawn.
    Each cell shows the high ADC value (top half) and low ADC value (bottom half).
    Clicking a valid cell invokes click_callback(row, col).
    """
    GRID = 9

    def __init__(self, parent, click_callback=None, **kw):
        kw.setdefault("highlightthickness", 0)
        super().__init__(parent, **kw)
        self._click_callback = click_callback
        self._data: np.ndarray = np.full((9, 9, 2), np.nan)
        self._baseline: np.ndarray | None = None
        self._cell_coords: list[tuple[int, int, int, int, int, int]] = []
        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<Button-1>", self._on_click)

    def update_data(self, data: np.ndarray, baseline: np.ndarray | None = None) -> None:
        self._data = data
        self._baseline = baseline
        self._redraw()

    @staticmethod
    def _format_prev_curr(curr: float, prev: float | None) -> tuple[str, str]:
        if np.isnan(curr):
            curr_text = "-"
        else:
            curr_text = str(int(curr))

        if prev is None:
            return curr_text, "same"

        if np.isnan(prev):
            prev_text = "-"
        else:
            prev_text = str(int(prev))

        if prev_text == curr_text:
            return curr_text, "same"
        return f"{prev_text}→{curr_text}", "changed"

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

                high = self._data[r, c, 0]
                low  = self._data[r, c, 1]
                prev_high = None
                prev_low = None
                if self._baseline is not None and self._baseline.shape == self._data.shape:
                    prev_high = self._baseline[r, c, 0]
                    prev_low = self._baseline[r, c, 1]

                b_text, b_state = self._format_prev_curr(high, prev_high)
                b_color = "#ffcc66" if b_state == "changed" else ("#44cc88" if not np.isnan(high) else "#555555")
                self.create_text((x0 + x1) // 2, (y0 + mid_y) // 2,
                                 text=b_text, fill=b_color, font=font)

                d_text, d_state = self._format_prev_curr(low, prev_low)
                d_color = "#ffcc66" if d_state == "changed" else ("#aa88ff" if not np.isnan(low) else "#555555")
                self.create_text((x0 + x1) // 2, (mid_y + y1) // 2,
                                 text=d_text, fill=d_color, font=font)

    def _on_click(self, event) -> None:
        if not self._click_callback:
            return
        for r, c, x0, y0, x1, y1 in self._cell_coords:
            if x0 <= event.x < x1 and y0 <= event.y < y1:
                self._click_callback(r, c)
                return


class ProgressRaster(tk.Canvas):
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
