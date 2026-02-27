# AHU Psychrometric Design — Streamlit App

Interactive psychrometric chart and AHU design tool for data centre HVAC systems.

## Deploy to Streamlit Community Cloud (free)

1. Push this folder to a GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Sign in with GitHub
4. Click **New app** → select your repo
5. Set **Main file path** to `app.py`
6. Click **Deploy**

Your app will be live at `https://your-app-name.streamlit.app`

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Features

- 🌍 **Live weather fetch** — ERA5 reanalysis data for any city worldwide
- 📊 **Interactive Plotly chart** — hover, zoom, toggle layers
- ❄️ **CRAH setpoint inputs** — off-coil, on-coil, return air
- ⚡ **Auto-derive off-coil conditions** from CRAH dew point
- 🌡️ **Moist air states table** — all psychrometric properties
- 💧 **System flows** — CRAH/AHU mass flows, fan loads
- ⚙️ **Process loads** — sensible, latent, total heat for each process
- 📥 **Excel export** — full report with embedded chart

## Project structure

```
├── app.py              # Streamlit app (main entry point)
├── psychro.py          # AirState class, psychrometric curves
├── psychro_engine.py   # Derive off-coil, system flows, process loads
├── weather_live.py     # ERA5 weather fetch via Open-Meteo
├── excel_export.py     # Excel report generator
├── chart_png.py        # Matplotlib chart (used for Excel embedding)
├── requirements.txt
└── .streamlit/
    └── config.toml     # Dark theme configuration
```
