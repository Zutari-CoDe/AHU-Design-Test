"""
Weather data module.
Provides ASHRAE design-day conditions for common locations.
Future: EPW file parsing support.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class DesignConditions:
    """ASHRAE design weather conditions for a location."""
    location: str
    country: str
    latitude: float
    longitude: float
    altitude_m: float
    timezone: int

    # Summer design conditions
    cooling_db_n20: float       # 0.4% cooling DB [°C]  (N=20 in your sheet = near 1%)
    cooling_wb_n20: float       # 0.4% coincident WB [°C]
    cooling_db_04: float        # 0.4% cooling DB [°C]
    cooling_wb_04: float        # Coincident WB [°C]
    cooling_db_meanwb: float    # Mean coincident WB (for enthalpy)
    dehumid_db: float           # Dehumidification DB [°C]
    dehumid_wb: float           # Max WB / dehumidification WB [°C]

    # Winter design conditions
    heating_db_n20: float       # 99% heating DB [°C]
    heating_db_004: float       # 99.6% heating DB [°C]
    heating_db_meanwb: float    # mean coincident WB for heating (approx)


# ASHRAE Handbook of Fundamentals — selected locations
# Sources: ASHRAE 2021 HOF, Chapter 14
DESIGN_CONDITIONS: Dict[str, DesignConditions] = {

    "ABU DHABI": DesignConditions(
        location="Abu Dhabi", country="UAE",
        latitude=24.43, longitude=54.65, altitude_m=27, timezone=4,
        cooling_db_n20=47.0, cooling_wb_n20=29.5,
        cooling_db_04=45.2, cooling_wb_04=28.5,
        cooling_db_meanwb=35.2, dehumid_db=33.6, dehumid_wb=30.2,
        heating_db_n20=7.3, heating_db_004=9.5, heating_db_meanwb=14.7,
    ),

    "DUBAI": DesignConditions(
        location="Dubai", country="UAE",
        latitude=25.25, longitude=55.33, altitude_m=5, timezone=4,
        cooling_db_n20=46.2, cooling_wb_n20=30.8,
        cooling_db_04=44.9, cooling_wb_04=30.0,
        cooling_db_meanwb=35.8, dehumid_db=34.2, dehumid_wb=31.2,
        heating_db_n20=10.2, heating_db_004=12.0, heating_db_meanwb=16.0,
    ),

    "RIYADH": DesignConditions(
        location="Riyadh", country="Saudi Arabia",
        latitude=24.72, longitude=46.73, altitude_m=612, timezone=3,
        cooling_db_n20=44.7, cooling_wb_n20=23.2,
        cooling_db_04=43.0, cooling_wb_04=22.4,
        cooling_db_meanwb=32.0, dehumid_db=31.0, dehumid_wb=22.8,
        heating_db_n20=3.2, heating_db_004=5.0, heating_db_meanwb=9.5,
    ),

    "JOHANNESBURG": DesignConditions(
        location="Johannesburg", country="South Africa",
        latitude=-26.13, longitude=28.23, altitude_m=1694, timezone=2,
        cooling_db_n20=32.2, cooling_wb_n20=19.3,
        cooling_db_04=30.8, cooling_wb_04=18.8,
        cooling_db_meanwb=24.5, dehumid_db=23.0, dehumid_wb=19.0,
        heating_db_n20=1.4, heating_db_004=3.1, heating_db_meanwb=8.5,
    ),

    "CAPE TOWN": DesignConditions(
        location="Cape Town", country="South Africa",
        latitude=-33.97, longitude=18.60, altitude_m=42, timezone=2,
        cooling_db_n20=35.2, cooling_wb_n20=21.0,
        cooling_db_04=33.1, cooling_wb_04=20.4,
        cooling_db_meanwb=26.3, dehumid_db=24.8, dehumid_wb=20.5,
        heating_db_n20=4.8, heating_db_004=6.2, heating_db_meanwb=11.5,
    ),

    "LONDON": DesignConditions(
        location="London", country="UK",
        latitude=51.48, longitude=-0.45, altitude_m=25, timezone=0,
        cooling_db_n20=30.5, cooling_wb_n20=21.0,
        cooling_db_04=28.8, cooling_wb_04=20.2,
        cooling_db_meanwb=22.8, dehumid_db=21.0, dehumid_wb=19.7,
        heating_db_n20=-3.5, heating_db_004=-1.8, heating_db_meanwb=4.0,
    ),

    "FRANKFURT": DesignConditions(
        location="Frankfurt", country="Germany",
        latitude=50.03, longitude=8.55, altitude_m=113, timezone=1,
        cooling_db_n20=33.2, cooling_wb_n20=21.5,
        cooling_db_04=31.2, cooling_wb_04=21.0,
        cooling_db_meanwb=23.8, dehumid_db=22.5, dehumid_wb=20.5,
        heating_db_n20=-10.0, heating_db_004=-7.5, heating_db_meanwb=2.0,
    ),

    "SINGAPORE": DesignConditions(
        location="Singapore", country="Singapore",
        latitude=1.37, longitude=103.98, altitude_m=16, timezone=8,
        cooling_db_n20=34.0, cooling_wb_n20=28.3,
        cooling_db_04=33.1, cooling_wb_04=27.8,
        cooling_db_meanwb=30.1, dehumid_db=29.0, dehumid_wb=28.1,
        heating_db_n20=22.3, heating_db_004=22.8, heating_db_meanwb=25.0,
    ),

    "SYDNEY": DesignConditions(
        location="Sydney", country="Australia",
        latitude=-33.95, longitude=151.18, altitude_m=6, timezone=10,
        cooling_db_n20=37.8, cooling_wb_n20=24.5,
        cooling_db_04=35.9, cooling_wb_04=23.5,
        cooling_db_meanwb=28.0, dehumid_db=26.2, dehumid_wb=23.8,
        heating_db_n20=4.8, heating_db_004=6.3, heating_db_meanwb=11.0,
    ),

    "NEW YORK": DesignConditions(
        location="New York (JFK)", country="USA",
        latitude=40.63, longitude=-73.78, altitude_m=9, timezone=-5,
        cooling_db_n20=33.9, cooling_wb_n20=25.9,
        cooling_db_04=32.6, cooling_wb_04=25.2,
        cooling_db_meanwb=28.0, dehumid_db=26.8, dehumid_wb=25.4,
        heating_db_n20=-11.2, heating_db_004=-8.9, heating_db_meanwb=2.0,
    ),

    "CHICAGO": DesignConditions(
        location="Chicago O'Hare", country="USA",
        latitude=41.98, longitude=-87.90, altitude_m=204, timezone=-6,
        cooling_db_n20=34.4, cooling_wb_n20=25.7,
        cooling_db_04=32.6, cooling_wb_04=25.0,
        cooling_db_meanwb=28.1, dehumid_db=27.0, dehumid_wb=25.2,
        heating_db_n20=-22.8, heating_db_004=-19.2, heating_db_meanwb=-2.0,
    ),

    "HONG KONG": DesignConditions(
        location="Hong Kong", country="China",
        latitude=22.32, longitude=114.17, altitude_m=9, timezone=8,
        cooling_db_n20=34.5, cooling_wb_n20=28.5,
        cooling_db_04=33.3, cooling_wb_04=28.1,
        cooling_db_meanwb=30.0, dehumid_db=29.2, dehumid_wb=28.3,
        heating_db_n20=7.3, heating_db_004=8.8, heating_db_meanwb=14.5,
    ),

    "MUMBAI": DesignConditions(
        location="Mumbai", country="India",
        latitude=19.12, longitude=72.85, altitude_m=14, timezone=5,
        cooling_db_n20=37.0, cooling_wb_n20=29.8,
        cooling_db_04=35.2, cooling_wb_04=29.0,
        cooling_db_meanwb=31.5, dehumid_db=30.5, dehumid_wb=29.2,
        heating_db_n20=14.5, heating_db_004=16.0, heating_db_meanwb=20.0,
    ),

    "CUSTOM": DesignConditions(
        location="Custom Location", country="",
        latitude=0, longitude=0, altitude_m=0, timezone=0,
        cooling_db_n20=45.0, cooling_wb_n20=28.0,
        cooling_db_04=40.0, cooling_wb_04=26.0,
        cooling_db_meanwb=32.0, dehumid_db=30.0, dehumid_wb=26.0,
        heating_db_n20=5.0, heating_db_004=8.0, heating_db_meanwb=12.0,
    ),
}


def get_location_list():
    return sorted([k for k in DESIGN_CONDITIONS.keys() if k != "CUSTOM"]) + ["CUSTOM"]


def get_design_conditions(location_name: str) -> Optional[DesignConditions]:
    return DESIGN_CONDITIONS.get(location_name.upper())
