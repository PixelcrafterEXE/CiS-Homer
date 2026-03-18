import numpy as np
from matplotlib.figure import Figure
import matplotlib.colors as mcolors
from matplotlib.collections import LineCollection
import tkinter as tk
import ttkbootstrap as tkk

class RasterFigure(Figure):
    def __init__(self, data: np.ndarray, autoRange: bool = False, logRange: bool = True, *args, **kwargs):
        kwargs.setdefault('figsize', (8, 6))
        super().__init__(*args, **kwargs)
        
        self.subplots_adjust(left=0.01, right=0.95, top=0.98, bottom=0.02, wspace=0.05)
        
        ax, cax = self.subplots(1, 2, gridspec_kw={'width_ratios': [15, 1]})
        
        data = data.astype(float)
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
                'raster', [(0.0, 'black'), (lo_n, 'black'), (hi_n, 'white'), (1.0, 'white')], N=65536
            )
            cmap.set_bad('none')
            return cmap

        norm = mcolors.LogNorm(vmin=1, vmax=65535, clip=True) if logRange else mcolors.Normalize(vmin=0, vmax=65535, clip=True)

        self.im = ax.imshow(data, cmap=make_cmap(lo, hi), norm=norm, interpolation='nearest', aspect='equal')
        ax.set_xticks([])
        ax.set_yticks([])

        def ok(i, j):
            return 0 <= i < rows and 0 <= j < cols and not nan_mask[i, j]

        segs = (
            [[(j-.5, i-.5), (j+.5, i-.5)] for i in range(rows+1) for j in range(cols) if ok(i-1,j) or ok(i,j)] +
            [[(j-.5, i-.5), (j-.5, i+.5)] for j in range(cols+1) for i in range(rows) if ok(i,j-1) or ok(i,j)]
        )
        if segs:
            ax.add_collection(LineCollection(segs, colors='black', lw=0.5))

        self.colorbar(self.im, cax=cax)

        if not autoRange:
            self.state = {'drag': None, 'lo': lo, 'hi': hi}
            self.lo_line = cax.axhline(lo, color='cyan', lw=1.5)
            self.hi_line = cax.axhline(hi, color='cyan', lw=1.5)
            self.vmin_cb = 1 if logRange else 0

            def on_press(event):
                if event.inaxes != cax or event.ydata is None: return
                y = event.ydata
                self.state['drag'] = 'lo' if abs(y - self.state['lo']) <= abs(y - self.state['hi']) else 'hi'

            def on_motion(event):
                if not self.state['drag'] or event.inaxes != cax or event.ydata is None: return
                y = float(np.clip(event.ydata, self.vmin_cb, 65535))
                if self.state['drag'] == 'lo':
                    self.state['lo'] = min(y, self.state['hi'] * 0.999 if logRange else self.state['hi'] - 1)
                    self.lo_line.set_ydata([self.state['lo']] * 2)
                else:
                    self.state['hi'] = max(y, self.state['lo'] * 1.001 if logRange else self.state['lo'] + 1)
                    self.hi_line.set_ydata([self.state['hi']] * 2)
                self.im.set_cmap(make_cmap(self.state['lo'], self.state['hi']))
                self.canvas.draw_idle()

            def on_release(event): 
                self.state['drag'] = None

            # We must assign these later or when the figure is added to a canvas.
            self._on_press = on_press
            self._on_motion = on_motion
            self._on_release = on_release

            # For safety: hook up events when figure gets a canvas
            def connect_events(fig):
                if fig.canvas:
                    if not hasattr(fig.canvas, 'figure'):
                        fig.canvas.figure = fig
                    fig.canvas.mpl_connect('button_press_event', fig._on_press)
                    fig.canvas.mpl_connect('motion_notify_event', fig._on_motion)
                    fig.canvas.mpl_connect('button_release_event', fig._on_release)
            
            # Store connect function temporarily.
            self._connect_events = connect_events

    def set_canvas(self, canvas):
        super().set_canvas(canvas)
        if hasattr(self, '_connect_events'):
            self._connect_events(self)

    def update_data(self, data: np.ndarray) -> None:
        self.im.set_data(data.astype(float))
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.draw_idle()


class BarFigure(Figure):
    def __init__(self, data: np.ndarray, *args, **kwargs):
        kwargs.setdefault('figsize', (10, 8))
        super().__init__(*args, **kwargs)
        
        self.subplots_adjust(left=0.05, right=0.98, top=0.95, bottom=0.08, hspace=0.3)
        self.ax1 = self.add_subplot(211)
        self.ax2 = self.add_subplot(212)
        
        indices = np.arange(1, 65)
        
        # Top subplot: Channels 1-32
        self.bars1 = self.ax1.bar(indices[:32], data[:32])
        self.ax1.set_xlabel("Channel Index")
        self.ax1.set_ylabel("Value")
        self.ax1.set_title("Channels 1-32")
        self.ax1.set_xlim(0, 33)
        self.ax1.set_xticks(indices[:32])
        
        # Bottom subplot: Channels 33-64
        self.bars2 = self.ax2.bar(indices[32:], data[32:])
        self.ax2.set_xlabel("Channel Index")
        self.ax2.set_ylabel("Value")
        self.ax2.set_title("Channels 33-64")
        self.ax2.set_xlim(32, 65)
        self.ax2.set_xticks(indices[32:])

    def update_data(self, data: np.ndarray) -> None:
        for bar, val in zip(self.bars1, data[:32]):
            bar.set_height(val)
        for bar, val in zip(self.bars2, data[32:]):
            bar.set_height(val)

        # Update y-limits if necessary to avoid static cutoffs dynamically
        max_val1 = np.max(data[:32]) if len(data[:32]) else 1.0
        max_val2 = np.max(data[32:]) if len(data[32:]) else 1.0
        
        self.ax1.set_ylim(0, max_val1 * 1.1)
        self.ax2.set_ylim(0, max_val2 * 1.1)
        
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.draw_idle()

class TableFrame(tkk.Frame):
    def __init__(self, parent, data: np.ndarray, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.configure(padding=10)
        self._table_vars = []
        for i in range(9):
            row_vars = []
            for j in range(9):
                var = tk.StringVar(value="")
                val = data[i, j]
                if not np.isnan(val):
                    var.set(str(int(val)))
                lbl = tkk.Label(self, textvariable=var, anchor="center", borderwidth=1, relief="solid")
                lbl.grid(row=i, column=j, sticky="nsew", padx=1, pady=1)
                self.rowconfigure(i, weight=1)
                self.columnconfigure(j, weight=1)
                row_vars.append(var)
            self._table_vars.append(row_vars)

    def update_data(self, data: np.ndarray) -> None:
        for i in range(9):
            for j in range(9):
                val = data[i, j]
                if np.isnan(val):
                    self._table_vars[i][j].set("")
                else:
                    self._table_vars[i][j].set(str(int(val)))
