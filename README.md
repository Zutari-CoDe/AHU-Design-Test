# AHU Psychrometric Chart — Streamlit App

A professional psychrometric chart tool for AHU design, built for data centre HVAC engineering.

## Features
- Interactive psychrometric chart (Plotly) with saturation curve, RH lines, enthalpy lines, WB lines
- ASHRAE A1 data centre zone overlay
- Process arrows showing AHU air handling sequence
- ASHRAE design conditions auto-fill for 13+ global cities
- Altitude-corrected atmospheric pressure
- Full psychrometric state table with CSV export
- All inputs match the red-cell inputs from the Excel sheet

## Project Structure

```
ahu_psychro_app/
├── app.py              ← Main Streamlit UI + chart
├── psychro.py          ← Psychrometric engine (wraps psychrolib)
├── weather.py          ← ASHRAE design-day data for global locations
├── requirements.txt
├── data/
│   └── AHU_Design.xlsx ← Your original Excel (reference)
└── README.md
```

## Setup & Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the app
```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`

## How to Use

1. **Select location** — pick from the dropdown or use "CUSTOM"
2. **Click "Auto-Fill ASHRAE Design Conditions"** — populates outdoor temps for that city
3. **Edit any inputs** in the sidebar expanders (CRAH, Outdoor, AHU Off-Coil, Return Air)
4. **Toggle chart overlays** — RH/Enthalpy/WB lines, ASHRAE zone, process arrows
5. **Download CSV** — exports all psychrometric states

## Weather Data Source

Design-day values (DB, WB at 0.4%, 1%, 99%, 99.6% exceedance) are from:
- **ASHRAE Handbook of Fundamentals 2021, Chapter 14**

For full hourly climate data (EPW files) — useful for annual simulation:
- https://climate.onebuilding.org (free global EPW files)
- Parse with `pvlib` or `ladybug-core`

## Adding More Cities

Edit `weather.py` and add a new entry to `DESIGN_CONDITIONS` dict following the same pattern.

## Flask Version

A Flask version can be created later using the same `psychro.py` and `weather.py` modules.
The chart would be exported as a Plotly HTML div or PNG from the backend.
