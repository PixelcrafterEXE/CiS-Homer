from __future__ import annotations

import datetime
import threading

import ttkbootstrap as tkk

import lib.Sensor as Serial
from lib.Config import getColorSchemes
from lib.UI.Options import OptionButton, OptionDropdown, OptionLabel, OptionSlider, OptionToggle


class SettingsMixin:
    def _build_settings_tab(self) -> None:
        self._frame_settings = tkk.Frame(self._tabview)
        self._tabview.add(self._frame_settings, text="Settings")
        self._setup_settings_tab()

    def _setup_settings_tab(self) -> None:
        # Serial Port
        OptionDropdown(
            self._frame_settings, "Serial port",
            ["auto"] + [port.device for port in Serial.listPorts()],
            "auto",
            command=lambda port: self._sensor.setPort(port) if self._sensor else None,
            persistent=True,
        ).add_to(self._frame_settings)

        # Wafer Config
        self._wafer_diameter_slider = OptionSlider(
            self._frame_settings, "Wafer diameter (mm)",
            min_val=50, max_val=150, initial=150,
            custom_steps=[25, 5],
            show_minmax=True,
            command=lambda _v: self._rebuild_raster_fig(),
            persistent=True,
        )
        self._wafer_diameter_slider.add_to(self._frame_settings)

        self._mask_wafer_toggle = OptionToggle(
            self._frame_settings, "Mask values outside wafer dia.",
            initial=False,
            command=lambda _: self._rebuild_raster_fig(),
            persistent=True,
        )
        self._mask_wafer_toggle.add_to(self._frame_settings)

        # Visuals
        self._color_schemes = getColorSchemes()
        scheme_names = list(self._color_schemes.keys())
        self._color_scheme_dropdown = OptionDropdown(
            self._frame_settings, "Color scheme",
            scheme_names, scheme_names[0] if scheme_names else "Grayscale",
            command=lambda _v: self._rebuild_raster_fig(),
            persistent=True,
        )
        self._color_scheme_dropdown.add_to(self._frame_settings)

        self._settings_use_clipping_colors = OptionToggle(
            self._frame_settings, "Use clipping colors",
            initial=True,
            command=lambda _: self._rebuild_raster_fig(),
            persistent=True,
        )
        self._settings_use_clipping_colors.add_to(self._frame_settings)

        self._settings_show_orientation_hint = OptionToggle(
            self._frame_settings, "Show orientation hint",
            initial=True,
            command=lambda _: self._rebuild_raster_fig(),
            persistent=True,
        )
        self._settings_show_orientation_hint.add_to(self._frame_settings)

        # ── System Time ─────────────────────────────────────────────────────
        self._sys_time_option = OptionLabel(
            self._frame_settings,
            text="--:--:--    --.--. ----",
            foreground="",
        )
        self._sys_time_option.add_to(self._frame_settings)
        self._update_sys_time_label()

        OptionButton(
            self._frame_settings,
            text="Sync time from Sensor",
            command=self._sync_time_from_sensor,
        ).add_to(self._frame_settings)

        OptionButton(
            self._frame_settings,
            text="Write current time to Sensor EEPROM",
            command=self._write_sensor_time,
        ).add_to(self._frame_settings)

    # ── Time helpers ──────────────────────────────────────────────────────

    def _update_sys_time_label(self) -> None:
        """Refresh the system-time label and reschedule itself every second."""
        if hasattr(self, "_sys_time_option"):
            now = datetime.datetime.now()
            self._sys_time_option.set_text(now.strftime("%H:%M:%S    %d.%m.%Y"))
            self.after(1000, self._update_sys_time_label)

    def _sync_time_from_sensor(self) -> None:
        """Read time from sensor EEPROM and apply it to the OS clock."""
        if not self._sensor_active():
            self._show_error("Sync time failed: sensor not connected.")
            return

        def _fetch():
            try:
                self._sensor.getTime()
            except Exception as e:
                self.after(0, lambda msg=str(e): self._show_error(f"Sync time failed: {msg}"))

        threading.Thread(target=_fetch, daemon=True).start()

    def _write_sensor_time(self) -> None:
        """Write the current system time to the sensor EEPROM."""
        if not self._sensor_active():
            self._show_error("Write time failed: sensor not connected.")
            return
        now = datetime.datetime.now()
        day, month, year = now.day, now.month, now.year % 100
        hour, minute, second = now.hour, now.minute, now.second

        def _write():
            try:
                self._sensor.setTime(day, month, year, hour, minute, second)
            except Exception as e:
                self.after(0, lambda msg=str(e): self._show_error(f"Write time failed: {msg}"))

        threading.Thread(target=_write, daemon=True).start()