import numpy as np
from matplotlib.figure import Figure
import matplotlib.colors as mcolors
from matplotlib.collections import LineCollection
from matplotlib.patches import Circle
from matplotlib.offsetbox import OffsetImage, AnnotationBbox, TextArea, VPacker
import matplotlib.image as mpimg
import os

class RasterFigure(Figure):
    def __init__(
        self,
        data: np.ndarray,
        autoRange: bool = False,
        rangeMode: str | None = None,
        logRange: bool = True,
        showValues: bool = False,
        waferDiameterMm: float = 150.0,
        gridDiameterMm: float = 150.0,
        MaskWafer: bool = False,
        colorScheme: list[str] | tuple[str, ...] | None = None,
        underColor: str = 'black',
        overColor: str = 'white',
        showOrientationHint: bool = True,
        manualLo: float | None = None,
        manualHi: float | None = None,
        onManualRangeChange=None,
        *args,
        **kwargs,
    ):
        kwargs.setdefault('figsize', (8, 6))
        super().__init__(*args, **kwargs)
        
        self.rangeMode = (rangeMode or ("auto" if autoRange else "manual")).lower()
        if self.rangeMode not in ("auto", "manual", "max"):
            self.rangeMode = "manual"
        self.autoRange = self.rangeMode == "auto"
        self.logRange = logRange
        self.showValues = showValues
        self.waferDiameterMm = waferDiameterMm
        self.gridDiameterMm = gridDiameterMm if gridDiameterMm > 0 else 150.0
        self.hideOutsideCircle = MaskWafer
        self.colorScheme = list(colorScheme) if colorScheme else ['black', 'white']
        if len(self.colorScheme) == 1:
            self.colorScheme = [self.colorScheme[0], self.colorScheme[0]]
        self.underColor = underColor
        self.overColor = overColor
        self.showOrientationHint = showOrientationHint
        self._on_manual_range_change = onManualRangeChange
        self._value_texts = []
        self._outline_circle = None
        self._stats_text = None
        self.subplots_adjust(left=0.01, right=0.95, top=0.98, bottom=0.02, wspace=0.05)
        
        ax, cax = self.subplots(1, 2, gridspec_kw={'width_ratios': [15, 1]})
        
        data = data.astype(float)
        data = self._mask_outside_circle(data)
        rows, cols = data.shape
        nan_mask = np.isnan(data)
        valid_vals = data[~nan_mask]

        base_lo = 1.0 if logRange else 0.0
        base_hi = 65535.0
        eps = 1e-6

        if self.rangeMode == "auto":
            lo = float(valid_vals.min()) if len(valid_vals) else base_lo
            hi = float(valid_vals.max()) if len(valid_vals) else base_hi
        elif self.rangeMode == "max":
            lo, hi = base_lo, base_hi
        else:
            lo = float(manualLo) if manualLo is not None else base_lo
            hi = float(manualHi) if manualHi is not None else base_hi
            lo = float(np.clip(lo, base_lo, base_hi - eps))
            hi = float(np.clip(hi, lo + eps, base_hi))

        def make_cmap(lo, hi):
            if self.logRange:
                log_rng = np.log10(65535) - np.log10(1)
                lo_n = (np.log10(max(lo, 1)) - np.log10(1)) / log_rng
                hi_n = (np.log10(max(hi, 1)) - np.log10(1)) / log_rng
            else:
                lo_n, hi_n = lo / 65535.0, hi / 65535.0
            lo_n = float(np.clip(lo_n, 0.0, 1.0 - eps))
            hi_n = float(np.clip(hi_n, lo_n + eps, 1.0))

            stops: list[tuple[float, str]] = [
                (0.0, self.underColor),
                (lo_n, self.underColor),
            ]

            scheme_count = len(self.colorScheme)
            for idx, color in enumerate(self.colorScheme):
                t = idx / (scheme_count - 1)
                pos = lo_n + t * (hi_n - lo_n)
                stops.append((float(pos), color))

            stops.extend([
                (hi_n, self.overColor),
                (1.0, self.overColor),
            ])

            # Matplotlib requires strictly increasing x positions.
            clean_stops: list[tuple[float, str]] = []
            last_x = -1.0
            for x, color in stops:
                x = float(np.clip(x, 0.0, 1.0))
                if x <= last_x:
                    if last_x >= 1.0 - eps:
                        continue
                    x = last_x + eps
                clean_stops.append((x, color))
                last_x = x

            cmap = mcolors.LinearSegmentedColormap.from_list(
                'raster', clean_stops, N=65536
            )
            cmap.set_under(self.underColor)
            cmap.set_over(self.overColor)
            cmap.set_bad('none')
            return cmap
        
        self.make_cmap = make_cmap

        norm = mcolors.LogNorm(vmin=1, vmax=65535, clip=True) if logRange else mcolors.Normalize(vmin=0, vmax=65535, clip=True)

        self.im = ax.imshow(data, cmap=make_cmap(lo, hi), norm=norm, interpolation='nearest', aspect='equal')
        self._ax = ax
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_frame_on(False)
        for spine in ax.spines.values():
            spine.set_visible(False)

        def ok(i, j):
            return 0 <= i < rows and 0 <= j < cols and not nan_mask[i, j]

        segs = (
            [[(j-.5, i-.5), (j+.5, i-.5)] for i in range(rows+1) for j in range(cols) if ok(i-1,j) or ok(i,j)] +
            [[(j-.5, i-.5), (j-.5, i+.5)] for j in range(cols+1) for i in range(rows) if ok(i,j-1) or ok(i,j)]
        )
        if segs:
            ax.add_collection(LineCollection(segs, colors='black', lw=0.5))

        self._draw_outline_circle(rows, cols)
        if self.showOrientationHint:
            self._draw_orientation_hint()
        self._create_stats_text(data)

        self.colorbar(self.im, cax=cax)

        if self.showValues:
            self._create_value_texts(data)

        if self.rangeMode == "manual":
            self.state = {'drag': None, 'lo': lo, 'hi': hi}
            y_trans = cax.get_yaxis_transform()
            # Draw lines with circular markers extending to the left (x=0) 
            self.lo_line, = cax.plot([-0.2, 1], [lo, lo], color='#007bff', lw=2, marker='o', markersize=15, markevery=[0], clip_on=False, transform=y_trans)
            self.hi_line, = cax.plot([-0.2, 1], [hi, hi], color='#007bff', lw=2, marker='o', markersize=15, markevery=[0], clip_on=False, transform=y_trans)
            self.vmin_cb = 1 if logRange else 0

            def on_press(event):
                if event.y is None or event.x is None: return
                
                # Check horizontal coordinate in cax axes space
                x_axes, _ = cax.transAxes.inverted().transform((event.x, event.y))
                if x_axes < -2.0 or x_axes > 2.0: return
                
                # Get vertical coordinate in cax data space
                _, y_data = cax.transData.inverted().transform((event.x, event.y))
                
                self.state['drag'] = 'lo' if abs(y_data - self.state['lo']) <= abs(y_data - self.state['hi']) else 'hi'

            def on_motion(event):
                if not self.state['drag'] or event.y is None: return
                
                _, y_data = cax.transData.inverted().transform((event.x, event.y))
                y = float(np.clip(y_data, self.vmin_cb, 65535))
                
                if self.state['drag'] == 'lo':
                    self.state['lo'] = min(y, self.state['hi'] * 0.999 if logRange else self.state['hi'] - 1)
                    self.lo_line.set_ydata([self.state['lo']] * 2)
                else:
                    self.state['hi'] = max(y, self.state['lo'] * 1.001 if logRange else self.state['lo'] + 1)
                    self.hi_line.set_ydata([self.state['hi']] * 2)

                if self._on_manual_range_change:
                    try:
                        self._on_manual_range_change(self.state['lo'], self.state['hi'])
                    except Exception:
                        pass

                self.im.set_cmap(make_cmap(self.state['lo'], self.state['hi']))
                if self.showValues:
                    self._update_value_texts(np.asarray(self.im.get_array(), dtype=float))
                self.canvas.draw_idle()

            def on_release(event): 
                self.state['drag'] = None

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

    def _draw_outline_circle(self, rows: int, cols: int) -> None:
        center_x, center_y, radius = self._circle_geometry(rows, cols)

        if self._outline_circle is None:
            self._outline_circle = Circle(
                (center_x, center_y),
                radius,
                fill=False,
                edgecolor='black',
                linewidth=1.5,
                zorder=3,
            )
            self._ax.add_patch(self._outline_circle)
        else:
            self._outline_circle.center = (center_x, center_y)
            self._outline_circle.set_radius(radius)

    def _draw_orientation_hint(self) -> None:
        hint_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "res", "OrientHint.png")
        )
        if not os.path.exists(hint_path):
            return

        try:
            hint_img = mpimg.imread(hint_path)
            image_box = OffsetImage(hint_img, zoom=0.14)
            label_box = TextArea("Orientation:", textprops={"fontsize": 9})
            packed_box = VPacker(children=[label_box, image_box], align="center", pad=0, sep=2)
            hint_artist = AnnotationBbox(
                packed_box,
                (0.02, 0.02),
                xycoords='figure fraction',
                frameon=False,
                box_alignment=(0, 0),
                zorder=5,
            )
            self.add_artist(hint_artist)
        except Exception:
            # Non-critical visual element; ignore load/render issues.
            pass

    def _create_stats_text(self, data: np.ndarray, unmapped: dict[int, int] | None = None) -> None:
        self._stats_text = self.text(
            0.02,
            0.98,
            "",
            transform=self.transFigure,
            ha='left',
            va='top',
            fontsize=9,
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.75, "edgecolor": "none"},
            zorder=6,
        )
        self._update_stats_text(data, unmapped)

    def _update_stats_text(self, data: np.ndarray, unmapped: dict[int, int] | None = None) -> None:
        if self._stats_text is None:
            return

        unmapped = unmapped or {}

        def format_unmapped_lines(values: dict[int, int]) -> str:
            ch8 = values.get(8)
            ch33 = values.get(33)
            ch52 = values.get(52)
            return (
                f"NTC1 (CH8): {'-' if ch8 is None else ch8}\n"
                f"NTC2 (CH33): {'-' if ch33 is None else ch33}\n"
                f"Reference Diode (CH52): {'-' if ch52 is None else ch52}"
            )

        valid = data[~np.isnan(data)]
        if valid.size == 0:
            base_text = "Median: -\nMean: -\nHomogenität: -"
            self._stats_text.set_text(f"{base_text}\n{format_unmapped_lines(unmapped)}")
            return

        median = float(np.median(valid))
        mean = float(np.mean(valid))
        vmin = float(np.min(valid))
        vmax = float(np.max(valid))
        denom = vmax + vmin
        homo = ((vmax - vmin) / denom) if denom != 0 else float('nan')

        homo_text = "-" if np.isnan(homo) else f"{homo:.4f}"
        stats_text = (
            f"Median: {median:.1f}\n"
            f"Mean: {mean:.1f}\n"
            f"Homogeneity: {homo_text}"
        )
        stats_text += f"\n{format_unmapped_lines(unmapped)}"
        self._stats_text.set_text(stats_text)

    def _circle_geometry(self, rows: int, cols: int) -> tuple[float, float, float]:
        center_x = (cols - 1) / 2.0
        center_y = (rows - 1) / 2.0
        base_radius = min(rows, cols) / 2.0
        radius = base_radius * (self.waferDiameterMm / self.gridDiameterMm)
        return center_x, center_y, radius

    def _mask_outside_circle(self, data: np.ndarray) -> np.ndarray:
        if not self.hideOutsideCircle:
            return data

        rows, cols = data.shape
        center_x, center_y, radius = self._circle_geometry(rows, cols)
        yy, xx = np.indices((rows, cols), dtype=float)
        outside = (xx - center_x) ** 2 + (yy - center_y) ** 2 > radius ** 2

        masked = data.copy()
        masked[outside] = np.nan
        return masked

    def set_canvas(self, canvas):
        super().set_canvas(canvas)
        if hasattr(self, '_connect_events'):
            self._connect_events(self)

    def _create_value_texts(self, data: np.ndarray) -> None:
        rows, cols = data.shape
        self._value_texts = []
        for i in range(rows):
            row = []
            for j in range(cols):
                txt = self._ax.text(j, i, "", ha='center', va='center', fontsize=7)
                row.append(txt)
            self._value_texts.append(row)
        self._update_value_texts(data)

    def _update_value_texts(self, data: np.ndarray) -> None:
        if not self.showValues or not self._value_texts:
            return

        rows, cols = data.shape
        for i in range(rows):
            for j in range(cols):
                value = data[i, j]
                txt = self._value_texts[i][j]
                if np.isnan(value):
                    txt.set_text("")
                    continue

                txt.set_text(f"{int(value)}")
                try:
                    r, g, b, _ = self.im.cmap(self.im.norm(value))
                    # Perceived luminance for contrast-aware text color.
                    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
                except Exception:
                    luminance = 0.0
                txt.set_color('white' if luminance < 0.5 else 'black')

    def update_data(self, data: np.ndarray, unmapped: dict[int, int] | None = None) -> None:
        data_float = data.astype(float)
        data_float = self._mask_outside_circle(data_float)
        self.im.set_data(data_float)
        self._draw_outline_circle(*data_float.shape)
        
        if self.autoRange:
            nan_mask = np.isnan(data_float)
            valid_vals = data_float[~nan_mask]
            lo = float(valid_vals.min()) if len(valid_vals) else (1.0 if self.logRange else 0.0)
            hi = float(valid_vals.max()) if len(valid_vals) else 65535.0
            self.im.set_cmap(self.make_cmap(lo, hi))

        self._update_stats_text(data_float, unmapped)
        self._update_value_texts(data_float)
            
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.draw_idle()
