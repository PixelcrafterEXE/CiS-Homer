from __future__ import annotations
import tkinter as tk
from typing import Callable, Sequence

import ttkbootstrap as tkk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

import lib.Sensor as Serial
from lib.Sensor import Sensor
from lib.Plotting import RasterFigure, BarFigure, TableFrame
from lib.Config import getCFGKey, setCFGKey


class Option(tkk.Frame):
    def __init__(self, parent, label: str | None = None, visibility: Callable[[], bool] | None = None) -> None:
        super().__init__(parent, padding=10)
        self.columnconfigure(0, weight=1)
        self._label = label
        self._visibility = visibility
        self._parent_container = None
        self._is_visible = False

    def add_to(self, parent) -> None:
        self._parent_container = parent
        self._is_visible = self._visibility() if self._visibility else True
        if self._is_visible:
            self.pack(in_=parent, fill="x", padx=8, pady=5)

    def check_visibility_change(self) -> bool:
        if not self._visibility:
            return False
        new_visible = self._visibility()
        if new_visible != self._is_visible:
            self._is_visible = new_visible
            return True
        return False

#todo: implement persistency


class OptionButton(Option):
    def __init__(self, parent, text: str, command: Callable | None = None, visibility: Callable[[], bool] | None = None) -> None:
        super().__init__(parent, visibility=visibility)
        button = tkk.Button(self, text=text, command=command, bootstyle="primary")
        button.grid(row=0, column=0, sticky="ew")

class OptionLabel(Option):
    def __init__(self, parent, text: str, foreground: str = "red", visibility: Callable[[], bool] | None = None) -> None:
        super().__init__(parent, visibility=visibility)
        label = tkk.Label(self, text=text, foreground=foreground)
        label.grid(row=0, column=0, sticky="w")


class OptionToggle(Option):
    def __init__(
        self,
        parent,
        label: str,
        initial: bool = False,
        command: Callable[[bool], None] | None = None,
        visibility: Callable[[], bool] | None = None,
        persistent: bool = False,
    ) -> None:
        super().__init__(parent, label, visibility=visibility)
        self.persistent = persistent
        self.config_key = f"toggle_{label.replace(' ', '_')}"
        if self.persistent:
            initial = getCFGKey(self.config_key, initial)
        self.value = tk.BooleanVar(value=initial)

        text = tkk.Label(self, text=label)
        text.grid(row=0, column=0, sticky="w")

        def _on_toggle() -> None:
            if self.persistent:
                setCFGKey(self.config_key, self.value.get())
            if command:
                command(self.value.get())

        toggle = tkk.Checkbutton(self, variable=self.value, command=_on_toggle, bootstyle="round-toggle")
        toggle.grid(row=0, column=1, sticky="e")


class OptionDropdown(Option):
    def __init__(
        self,
        parent,
        label: str,
        values: Sequence[str],
        initial: str | None = None,
        command: Callable[[str], None] | None = None,
        visibility: Callable[[], bool] | None = None,
        persistent: bool = False,
    ) -> None:
        super().__init__(parent, label, visibility=visibility)
        self.persistent = persistent
        self.config_key = f"dropdown_{label.replace(' ', '_')}"

        text = tkk.Label(self, text=label)
        text.grid(row=0, column=0, sticky="w", padx=(0, 10))

        selected = initial if initial is not None else (values[0] if values else "")
        if self.persistent:
            selected = getCFGKey(self.config_key, selected)
            
        self.value = tk.StringVar(value=selected)

        dropdown = tkk.Combobox(self, textvariable=self.value, values=list(values), state="readonly")
        dropdown.grid(row=0, column=1, sticky="ew")

        def _on_select(_event=None) -> None:
            if self.persistent:
                setCFGKey(self.config_key, self.value.get())
            if command:
                command(self.value.get())

        dropdown.bind("<<ComboboxSelected>>", _on_select)
        self.columnconfigure(1, weight=1)


class OptionSection(Option):
    def __init__(self, parent, label: str, visibility: Callable[[], bool] | None = None) -> None:
        super().__init__(parent, label, visibility=visibility)
        self.configure(padding=0)
        self._children: list[Option] = []
        self._is_expanded = True
        
        self._header_btn = tkk.Button(
            self, 
            text=f"▼  {self._label}", 
            command=self._toggle, 
            bootstyle="link",
        )
        self._header_btn.grid(row=0, column=0, sticky="w")
        
        self.content_frame = tkk.Frame(self)
        self.content_frame.grid(row=1, column=0, sticky="nsew", pady=(5, 0), padx=(10, 0))
        self.content_frame.columnconfigure(0, weight=1)

    def _toggle(self) -> None:
        self._is_expanded = not self._is_expanded
        if self._is_expanded:
            self._header_btn.configure(text=f"▼  {self._label}")
            self.content_frame.grid(row=1, column=0, sticky="nsew", pady=(5, 0), padx=(10, 0))
        else:
            self._header_btn.configure(text=f"▶  {self._label}")
            self.content_frame.grid_forget()

    def add_option(self, option: Option) -> None:
        self._children.append(option)
        option.add_to(self.content_frame)

    def check_visibility_change(self) -> bool:
        changed = super().check_visibility_change()
        
        children_changed = False
        for child in self._children:
            if child.check_visibility_change():
                children_changed = True
                
        if children_changed:
            for child in self._children:
                child.pack_forget()
            for child in self._children:
                if child._is_visible:
                    child.pack(in_=child._parent_container, fill="x", padx=8, pady=5)
        
        return changed


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
                if current_tab == 0 and getattr(self, '_raster_fig', None):
                    data = self._sensor.getMap()
                    self.after(0, lambda: self._raster_fig.update_data(data))
                elif current_tab == 1 and getattr(self, '_bar_fig', None):
                    data = self._sensor.getRaw()
                    self.after(0, lambda: self._bar_fig.update_data(data))
                elif current_tab == 2 and getattr(self, '_table_frame', None):
                    data = self._sensor.getMap()
                    self.after(0, lambda: self._table_frame.update_data(data))
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
        #todo: disable alt+tab, alt+f4, ctrl+alt+del, etc. to prevent user from exiting the app or switching to another app

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
            self._table_frame = TableFrame(self._tabview, np.full((9, 9), np.nan))
            self._tabview.add(self._table_frame, text="Tabellenansicht")

    def _rebuild_raster_fig(self) -> None:
        if not self._sensor or not self._sensor.ser or not self._sensor.ser.is_open:
            return
        
        if hasattr(self, '_raster_canvas') and self._raster_canvas is not None:
            self._raster_canvas.get_tk_widget().destroy()

        auto_range = self._auto_range_toggle.value.get() if hasattr(self, '_auto_range_toggle') else False
        log_range = self._log_scale_toggle.value.get() if hasattr(self, '_log_scale_toggle') else True
        
        self._raster_fig = RasterFigure(np.full((9, 9), np.nan), autoRange=auto_range, logRange=log_range)
        self._raster_canvas = FigureCanvasTkAgg(self._raster_fig, master=self._frame_raster_container)
        self._raster_canvas.draw()
        self._raster_canvas.get_tk_widget().pack(fill="both", expand=True)

    def _build_right_panel(self) -> None:
        self._right_panel = tkk.Frame(self._main, padding=(0, 10, 10, 10))
        self._right_panel.grid(row=0, column=1, sticky="nsew")
        self._right_panel.rowconfigure(0, weight=1)
        self._right_panel.columnconfigure(0, weight=1)

        from ttkbootstrap.scrolled import ScrolledFrame
        self._options_container = ScrolledFrame(self._right_panel, autohide=True, bootstyle="round")
        self._options_container.grid(row=0, column=0, sticky="nsew")

        self._options: list[Option] = []

        serial_section = OptionSection(self._options_container, "Verbindung")
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
        serial_section.add_option(
            OptionDropdown(
                serial_section.content_frame,
                "Baud-Rate", 
                ["9600", "19200", "38400", "57600", "115200"],
                "115200",
                command=lambda baud: self._sensor.setBaud(int(baud)) if self._sensor else None,
                persistent=True
            )
        )

        messung_section = OptionSection(self._options_container, "Messung")
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
        
        display_section = OptionSection(self._options_container, "Anzeige")
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

        export_section = OptionSection(self._options_container, "Exportieren")
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


    def _add_option(self, option: Option) -> None:
        self._options.append(option)
        option.add_to(self._options_container)