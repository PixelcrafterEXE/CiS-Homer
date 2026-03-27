from __future__ import annotations

import ttkbootstrap as tkk


class CalibrationMixin:
    def _build_calibration_tab(self) -> None:
        self._frame_calibration = tkk.Frame(self._tabview)
        self._tabview.add(self._frame_calibration, text="Calibration")
        self._setup_calibration_tab()

    def _setup_calibration_tab(self) -> None:
        pass
