from __future__ import annotations

import ttkbootstrap as tkk

import lib.Sensor as Serial
from lib.Config import getColorSchemes
from lib.UI.Options import OptionDropdown, OptionToggle


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
        self._wafer_diameter_dropdown = OptionDropdown(
            self._frame_settings, "Wafer diameter (mm)",
            [str(v) for v in range(50, 151, 10)], "150",
            command=lambda _v: self._rebuild_raster_fig(),
            persistent=True,
        )
        self._wafer_diameter_dropdown.add_to(self._frame_settings)

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
