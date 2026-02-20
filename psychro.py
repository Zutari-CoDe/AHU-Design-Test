"""
Psychrometric calculation engine using psychrolib.
All calculations at standard or site-specific pressure.
"""

import psychrolib
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

# Set SI units globally
psychrolib.SetUnitSystem(psychrolib.SI)


@dataclass
class AirState:
    """Represents a fully-defined moist air state."""
    name: str
    tdb: float          # Dry bulb temp [°C]
    twb: float          # Wet bulb temp [°C]
    pressure: float     # Atmospheric pressure [Pa]

    # Derived (computed on init)
    rh: float = field(init=False)
    w: float = field(init=False)       # Humidity ratio [kg/kg]
    h: float = field(init=False)       # Enthalpy [kJ/kg]
    tdp: float = field(init=False)     # Dew point [°C]
    density: float = field(init=False) # [kg/m³]

    def __post_init__(self):
        p = self.pressure
        try:
            self.w = psychrolib.GetHumRatioFromTWetBulb(self.tdb, self.twb, p)
            self.rh = psychrolib.GetRelHumFromHumRatio(self.tdb, self.w, p)
            self.h = psychrolib.GetMoistAirEnthalpy(self.tdb, self.w) / 1000  # J/kg → kJ/kg
            self.tdp = psychrolib.GetTDewPointFromHumRatio(self.tdb, self.w, p)
            v = psychrolib.GetMoistAirVolume(self.tdb, self.w, p)
            self.density = 1.0 / v
        except Exception as e:
            self.w = 0.0
            self.rh = 0.0
            self.h = self.tdb * 1.006
            self.tdp = self.tdb - 2
            self.density = 1.2

    @property
    def w_gkg(self):
        """Humidity ratio in g/kg (for chart display)."""
        return self.w * 1000


def altitude_to_pressure(altitude_m: float) -> float:
    """Convert altitude [m] to atmospheric pressure [Pa] using standard atmosphere."""
    return 101325 * (1 - 2.25577e-5 * altitude_m) ** 5.25588


def saturation_curve(pressure: float, tdb_min=-10, tdb_max=55, n=300):
    """Generate saturation curve (RH=100%) data for psychrometric chart."""
    temps = np.linspace(tdb_min, tdb_max, n)
    w_sat = []
    for t in temps:
        try:
            w = psychrolib.GetSatHumRatio(t, pressure)
            w_sat.append(w * 1000)  # g/kg
        except Exception:
            w_sat.append(None)
    return temps, w_sat


def rh_curve(rh: float, pressure: float, tdb_min=-10, tdb_max=55, n=200):
    """Generate constant RH line data."""
    temps = np.linspace(tdb_min, tdb_max, n)
    w_rh = []
    for t in temps:
        try:
            w = psychrolib.GetHumRatioFromRelHum(t, rh, pressure)
            w_rh.append(w * 1000)
        except Exception:
            w_rh.append(None)
    return temps, w_rh


def enthalpy_line(h_kj: float, pressure: float, tdb_min=-10, tdb_max=55, n=100):
    """Generate constant enthalpy line: W = (h - 1.006*T) / (2501 + 1.86*T) in g/kg."""
    temps = np.linspace(tdb_min, tdb_max, n)
    w_h = []
    for t in temps:
        try:
            w = (h_kj - 1.006 * t) / (2501 + 1.86 * t)
            if 0 <= w <= 0.040:
                w_h.append(w * 1000)
            else:
                w_h.append(None)
        except Exception:
            w_h.append(None)
    return temps, w_h


def wb_line(twb: float, pressure: float, tdb_min: float = None, tdb_max=55, n=100):
    """Generate constant wet bulb line."""
    if tdb_min is None:
        tdb_min = twb
    temps = np.linspace(tdb_min, tdb_max, n)
    w_wb = []
    for t in temps:
        try:
            w = psychrolib.GetHumRatioFromTWetBulb(t, twb, pressure)
            if w >= 0:
                w_wb.append(w * 1000)
            else:
                w_wb.append(None)
        except Exception:
            w_wb.append(None)
    return temps, w_wb
