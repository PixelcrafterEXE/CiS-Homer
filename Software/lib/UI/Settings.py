from __future__ import annotations

import datetime
import threading

import ttkbootstrap as tkk

import lib.Sensor as Serial
from lib.Config import getColorSchemes
from lib.UI.Options import OptionButton, OptionDropdown, OptionEntry, OptionLabel, OptionSlider, OptionToggle


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

        # ── Time ────────────────────────────────────────────────────────────
        # System clock (always visible, ticks every second)
        self._sys_time_option = OptionLabel(
            self._frame_settings,
            text="System:  --:--:--    --.--. ----",
        )
        self._add_option(self._sys_time_option, self._frame_settings)

        # Sensor EEPROM time (only when sensor connected, read from cache)
        self._sensor_time_option = OptionLabel(
            self._frame_settings,
            text="Sensor:  —",
            visibility=self._sensor_active,
        )
        self._add_option(self._sensor_time_option, self._frame_settings)

        # Sync sensor EEPROM time → OS clock
        self._add_option(OptionButton(
            self._frame_settings,
            text="Sync time to OS from Sensor",
            command=self._sync_time_from_sensor,
            visibility=self._sensor_active,
        ), self._frame_settings)

        # Manual time entry to write to sensor EEPROM
        self._manual_time_entry_opt = OptionEntry(
            self._frame_settings,
            label="Write to Sensor  (DD.MM.YYYY HH:MM:SS):",
            initial=datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            visibility=self._sensor_active,
        )
        self._add_option(self._manual_time_entry_opt, self._frame_settings)

        self._add_option(OptionButton(
            self._frame_settings,
            text="Write time to Sensor EEPROM",
            command=self._write_manual_sensor_time,
            visibility=self._sensor_active,
        ), self._frame_settings)

        self._update_sys_time_label()

    # ── Time helpers ──────────────────────────────────────────────────────

    def _update_sys_time_label(self) -> None:
        """Refresh the system-time label and reschedule itself every second."""
        if hasattr(self, "_sys_time_option"):
            now = datetime.datetime.now()
            self._sys_time_option.set_text("System:  " + now.strftime("%H:%M:%S    %d.%m.%Y"))
        if hasattr(self, "_sensor_time_option"):
            self._update_sensor_time_from_cache()
        self.after(1000, self._update_sys_time_label)

    def _update_sensor_time_from_cache(self) -> None:
        """Update the sensor EEPROM time label from the in-memory calibration cache."""
        if not self._sensor_active() or not self._sensor or not self._sensor._calibration_cache:
            self._sensor_time_option.set_text("Sensor:  —")
            return
        cal = self._sensor._calibration_cache
        try:
            year = int(cal["year"])
            if year < 100:
                year += 2000
            t = datetime.datetime(year, int(cal["month"]), int(cal["day"]),
                                  int(cal["hour"]), int(cal["minute"]), int(cal["second"]))
            self._sensor_time_option.set_text("Sensor:  " + t.strftime("%H:%M:%S    %d.%m.%Y"))
        except Exception:
            self._sensor_time_option.set_text("Sensor:  —")

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

    def _write_manual_sensor_time(self) -> None:
        """Parse the manual time entry and write it to the sensor EEPROM."""
        if not self._sensor_active():
            self._show_error("Write time failed: sensor not connected.")
            return
        if not hasattr(self, "_manual_time_entry_opt"):
            return
        raw = self._manual_time_entry_opt.value.get().strip()
        dt = None
        for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            self._show_error("Invalid time format. Use: DD.MM.YYYY HH:MM:SS")
            return
        day, month, year = dt.day, dt.month, dt.year % 100
        hour, minute, second = dt.hour, dt.minute, dt.second

        def _write():
            try:
                self._sensor.setTime(day, month, year, hour, minute, second)
            except Exception as e:
                self.after(0, lambda msg=str(e): self._show_error(f"Write time failed: {msg}"))

        threading.Thread(target=_write, daemon=True).start()