from __future__ import annotations

import numpy as np


NTCPoint = tuple[float, float]  # (temperature_c, resistance_ohm)

NTC_CURVE_POINTS: list[NTCPoint] = [
	(0.0, 28000.0),
	(100.0, 891.0),
]

def fit_ntc_polynomial(
	curve_points: list[NTCPoint] = NTC_CURVE_POINTS,
	degree: int | None = None,
) -> np.poly1d:
	"""Fit and return a polynomial mapping resistance (Ohm) -> temperature (°C)."""
	if len(curve_points) < 2:
		raise ValueError("At least 2 curve points are required.")

	temperatures = np.asarray([p[0] for p in curve_points], dtype=float)
	resistances = np.asarray([p[1] for p in curve_points], dtype=float)

	if np.any(resistances <= 0):
		raise ValueError("All resistances must be > 0.")

	max_degree = len(curve_points) - 1
	degree = max_degree if degree is None else int(degree)
	if degree < 1 or degree > max_degree:
		raise ValueError(f"degree must be in range 1..{max_degree}")

	coeffs = np.polyfit(resistances, temperatures, degree)
	return np.poly1d(coeffs)

def resistance_from_reading(reading: float) -> float:
	"""Convert ADC reading (0..65535) to NTC resistance in Ohms."""
	raise NotImplementedError("ADC-to-resistance conversion not implemented yet.")

def temperature_from_resistance(resistance_ohm: float, poly: np.poly1d) -> float:
	"""Calculate temperature in °C from resistance in Ohms."""
	if resistance_ohm <= 0:
		raise ValueError("resistance_ohm must be > 0")
	return float(poly(float(resistance_ohm)))


def temperature_from_reading(reading: int, poly: np.poly1d) -> float:
	"""Calculate temperature in °C directly from ADC reading (0..65535)."""
	if not 0 <= reading <= 65535:
		raise ValueError("reading must be in range 0..65535")
	resistance = resistance_from_reading(float(reading))
	return temperature_from_resistance(resistance, poly)

