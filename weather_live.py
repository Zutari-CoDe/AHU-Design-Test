"""
weather_live.py — Live ASHRAE-equivalent design conditions from Open-Meteo ERA5
================================================================================
Pipeline:
  1. Geocode city string → lat, lon, elevation (Open-Meteo Geocoding API, free)
  2. Pull 10 years of hourly Tdb + Tdp ERA5 reanalysis (Open-Meteo Archive API, free)
  3. Compute WB from Tdp via psychrolib
  4. Derive ASHRAE-style percentiles:
       Summer: 99.6% Tdb  + coincident WB   (≈ ASHRAE N=20 / 0.4% cooling)
               99.0% Tdb  + coincident WB   (≈ ASHRAE 1%   / N=50)
               max WB     + coincident Tdb  (≈ ASHRAE dehumid)
       Winter: 0.4% Tdb                     (≈ ASHRAE 99.6% heating)
               1.0% Tdb                     (≈ ASHRAE 99%   heating)

No API key required. Free for non-commercial use. Data: ERA5 / ECMWF via Open-Meteo.
"""

import requests
import numpy as np
import psychrolib
import urllib3
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

# Suppress SSL warnings from corporate proxy certificate inspection
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

psychrolib.SetUnitSystem(psychrolib.SI)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL   = "https://archive-api.open-meteo.com/v1/archive"

# How many years of ERA5 data to pull for percentile calculation
HISTORY_YEARS = 10


@dataclass
class LiveDesignConditions:
    """Computed ASHRAE-equivalent design conditions from ERA5 data."""
    location_name: str
    country: str
    latitude: float
    longitude: float
    altitude_m: float

    # Summer cooling (high Tdb percentiles)
    cooling_db_996: float     # 99.6% Tdb (ASHRAE ~0.4% / N=20)
    cooling_wb_996: float     # Coincident WB at 99.6% Tdb
    cooling_db_990: float     # 99.0% Tdb (ASHRAE ~1%)
    cooling_wb_990: float     # Coincident WB at 99.0% Tdb

    # Summer dehumidification (high WB percentiles)
    dehumid_wb_996: float     # 99.6% WB
    dehumid_db_996: float     # Coincident Tdb at 99.6% WB

    # Winter heating (low Tdb percentiles)
    heating_db_004: float     # 0.4% Tdb (ASHRAE 99.6%)
    heating_db_010: float     # 1.0% Tdb (ASHRAE 99%)
    heating_wb_mean: float    # Mean WB at winter design condition

    # Data quality
    data_years: int
    source: str = "Open-Meteo ERA5 Reanalysis"


def _tdp_to_twb(tdb: float, tdp: float, pressure: float) -> float:
    """Convert dew point to wet bulb via psychrolib."""
    try:
        w = psychrolib.GetHumRatioFromTDewPoint(tdp, pressure)
        return psychrolib.GetTWetBulbFromHumRatio(tdb, w, pressure)
    except Exception:
        # Approximation fallback: Stull 2011
        return tdb * np.arctan(0.151977 * (tdp + 8.313659)**0.5) + \
               np.arctan(tdb + tdp) - np.arctan(tdp - 1.676331) + \
               0.00391838 * tdp**1.5 * np.arctan(0.023101 * tdp) - 4.686035


def geocode(city: str) -> Optional[dict]:
    """
    Geocode a city name using Open-Meteo geocoding API.
    Returns dict with: name, country, latitude, longitude, elevation
    """
    try:
        r = requests.get(GEOCODING_URL, params={
            "name": city,
            "count": 5,
            "language": "en",
            "format": "json"
        }, timeout=10, verify=False)
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            return None
        # Prefer results with a country match if city includes comma
        best = results[0]
        return {
            "name"      : best.get("name", city),
            "country"   : best.get("country", ""),
            "latitude"  : best["latitude"],
            "longitude" : best["longitude"],
            "elevation" : best.get("elevation", 0) or 0,
        }
    except Exception as e:
        raise RuntimeError(f"Geocoding failed for '{city}': {e}")


def fetch_era5_hourly(lat: float, lon: float, years: int = HISTORY_YEARS) -> dict:
    """
    Fetch hourly Tdb (temperature_2m) and Tdp (dew_point_2m) from Open-Meteo ERA5.
    Returns dict with arrays: tdb, tdp, times.
    Pulls the most recent `years` years up to yesterday.
    """
    end_date   = datetime.utcnow().date() - timedelta(days=2)  # ERA5 has ~5 day lag
    start_date = end_date.replace(year=end_date.year - years)

    try:
        r = requests.get(ARCHIVE_URL, params={
            "latitude"        : round(lat, 4),
            "longitude"       : round(lon, 4),
            "start_date"      : start_date.isoformat(),
            "end_date"        : end_date.isoformat(),
            "hourly"          : "temperature_2m,dew_point_2m",
            "timezone"        : "UTC",
            "wind_speed_unit" : "ms",
        }, timeout=60, verify=False)
        r.raise_for_status()
        data = r.json()

        hourly = data.get("hourly", {})
        tdb = np.array(hourly.get("temperature_2m", []), dtype=float)
        tdp = np.array(hourly.get("dew_point_2m",   []), dtype=float)

        # Remove NaN rows
        valid = ~(np.isnan(tdb) | np.isnan(tdp))
        tdb = tdb[valid]
        tdp = tdp[valid]

        if len(tdb) < 1000:
            raise RuntimeError("Insufficient data returned from ERA5")

        actual_years = (end_date - start_date).days / 365.25
        return {"tdb": tdb, "tdp": tdp, "years": actual_years,
                "start": start_date.isoformat(), "end": end_date.isoformat()}

    except requests.exceptions.Timeout:
        raise RuntimeError("ERA5 request timed out — try again")
    except Exception as e:
        raise RuntimeError(f"ERA5 fetch failed: {e}")


def compute_design_conditions(lat: float, lon: float, altitude_m: float,
                               location_name: str, country: str,
                               years: int = HISTORY_YEARS) -> LiveDesignConditions:
    """
    Full pipeline: fetch ERA5 data → compute ASHRAE-style design conditions.
    """
    from psychro import altitude_to_pressure
    P = altitude_to_pressure(altitude_m)

    # ── Fetch ERA5 data ───────────────────────────────────────────────────
    era5 = fetch_era5_hourly(lat, lon, years)
    tdb  = era5["tdb"]
    tdp  = era5["tdp"]
    n    = len(tdb)

    # ── Compute WB for all hours ──────────────────────────────────────────
    twb = np.array([_tdp_to_twb(t, d, P) for t, d in zip(tdb, tdp)])

    # ── Percentile thresholds ─────────────────────────────────────────────
    # ASHRAE uses annual hours: 8760h/yr
    # 0.4% exceedance = 99.6th percentile of annual distribution
    # We compute over all hours in the dataset

    # --- Summer cooling: high Tdb percentiles ---
    p_cool_996 = np.percentile(tdb, 99.6)   # 0.4% cooling DB
    p_cool_990 = np.percentile(tdb, 99.0)   # 1.0% cooling DB

    # Coincident WB: mean WB when Tdb is within 0.5°C of the design DB
    def coincident_wb(db_threshold: float, tdb_arr, twb_arr, window=1.0) -> float:
        mask = tdb_arr >= (db_threshold - window)
        if mask.sum() == 0:
            return db_threshold - 5
        return float(np.mean(twb_arr[mask]))

    wb_996 = coincident_wb(p_cool_996, tdb, twb)
    wb_990 = coincident_wb(p_cool_990, tdb, twb)

    # --- Summer dehumidification: high WB percentiles ---
    p_dehum_996 = np.percentile(twb, 99.6)
    mask_wb     = twb >= (p_dehum_996 - 0.5)
    db_at_wb996 = float(np.mean(tdb[mask_wb])) if mask_wb.sum() > 0 else p_dehum_996 + 3

    # --- Winter heating: low Tdb percentiles ---
    p_heat_004 = np.percentile(tdb, 0.4)    # 99.6% heating DB
    p_heat_010 = np.percentile(tdb, 1.0)    # 99.0% heating DB

    # Mean coincident WB in cold conditions
    mask_cold  = tdb <= (p_heat_004 + 1.0)
    wb_winter  = float(np.mean(twb[mask_cold])) if mask_cold.sum() > 0 else p_heat_004 - 2

    return LiveDesignConditions(
        location_name  = location_name,
        country        = country,
        latitude       = lat,
        longitude      = lon,
        altitude_m     = altitude_m,
        cooling_db_996 = round(float(p_cool_996), 1),
        cooling_wb_996 = round(float(wb_996), 1),
        cooling_db_990 = round(float(p_cool_990), 1),
        cooling_wb_990 = round(float(wb_990), 1),
        dehumid_wb_996 = round(float(p_dehum_996), 1),
        dehumid_db_996 = round(float(db_at_wb996), 1),
        heating_db_004 = round(float(p_heat_004), 1),
        heating_db_010 = round(float(p_heat_010), 1),
        heating_wb_mean= round(float(wb_winter), 1),
        data_years     = int(round(era5["years"])),
    )


def get_design_conditions_for_city(city: str) -> LiveDesignConditions:
    """
    Main entry point: city name string → full design conditions.
    Raises RuntimeError with user-friendly message on failure.
    """
    geo = geocode(city)
    if not geo:
        raise RuntimeError(f"City '{city}' not found. Try a different name or check spelling.")

    return compute_design_conditions(
        lat           = geo["latitude"],
        lon           = geo["longitude"],
        altitude_m    = geo["elevation"],
        location_name = geo["name"],
        country       = geo["country"],
    )


def design_conditions_to_dict(dc: LiveDesignConditions) -> dict:
    """
    Convert to the format expected by Flask /api/design-conditions endpoint.
    Maps computed ERA5 percentiles → app input field names.
    """
    return {
        # Outdoor inputs (mapped to app field IDs)
        "oat_n20_tdb"      : dc.cooling_db_996,  # 0.4% / N=20 cooling DB
        "oat_n20_twb"      : dc.cooling_wb_996,  # Coincident WB
        "oat_04e_tdb"      : dc.cooling_db_990,  # 1% cooling DB (enthalpy)
        "oat_04e_twb"      : dc.cooling_wb_990,
        "oat_04h_tdb"      : dc.dehumid_db_996,  # Dehum coincident DB
        "oat_04h_twb"      : dc.dehumid_wb_996,  # Max WB (dehum)
        "oat_min_n20_tdb"  : dc.heating_db_004,  # 99.6% heating DB
        "oat_min_n20_twb"  : dc.heating_wb_mean,
        "oat_min_04h_tdb"  : dc.heating_db_010,  # 99.0% heating DB
        "oat_min_04h_twb"  : dc.heating_wb_mean + 1.0,
        # Location metadata
        "altitude"         : dc.altitude_m,
        "label"            : f"{dc.location_name}, {dc.country}",
        "latitude"         : dc.latitude,
        "longitude"        : dc.longitude,
        "data_years"       : dc.data_years,
        "source"           : dc.source,
        # Raw stats (for display)
        "cooling_db_996"   : dc.cooling_db_996,
        "cooling_wb_996"   : dc.cooling_wb_996,
        "cooling_db_990"   : dc.cooling_db_990,
        "cooling_wb_990"   : dc.cooling_wb_990,
        "dehumid_wb_996"   : dc.dehumid_wb_996,
        "dehumid_db_996"   : dc.dehumid_db_996,
        "heating_db_004"   : dc.heating_db_004,
        "heating_db_010"   : dc.heating_db_010,
    }
