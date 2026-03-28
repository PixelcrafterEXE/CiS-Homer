from __future__ import annotations

import threading

import ttkbootstrap as tkk

from lib.Sensor import Sensor
from lib.UI.Calibration import CalibrationMixin
from lib.UI.Options import Option
from lib.UI.Settings import SettingsMixin
from lib.UI.Visualizer import VisualizerMixin


class UI(tkk.Tk, VisualizerMixin, CalibrationMixin, SettingsMixin):
    def __init__(self) -> None:
        super().__init__()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._sensor: Sensor | None = None
        self._raster_fig = None
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
        """Helper to check if sensor connection is active and open."""
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
                    try:
                        self._sensor.ser.close()
                    except Exception:
                        pass
                    self._sensor.ser = None
                self.after(0, self._build_main_panel)
            finally:
                self._fetching_data = False

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

    def buildUI(self) -> None:
        self.title("CiS HomeRPI")
        # self.attributes("-fullscreen", True)
        self.geometry("800x1280")

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

        self._build_visualizer_tab(sensor_active)
        self._build_calibration_tab()
        self._build_settings_tab()

        # Now that Settings tab has been built (and its dropdowns/toggles
        # exist), build the raster figure with the correct color scheme etc.
        if sensor_active:
            self._rebuild_raster_fig()
        else:
            tkk.Label(self._plot_container, text="No sensor detected", foreground="red").pack(expand=True)

        self._ui_sensor_state = sensor_active
