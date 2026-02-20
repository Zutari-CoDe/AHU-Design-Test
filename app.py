"""
AHU Psychrometric Chart — Streamlit App
Zutari Infrastructure Engineering
"""

import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import psychrolib
from psychro import (
    AirState, altitude_to_pressure,
    saturation_curve, rh_curve, enthalpy_line, wb_line
)
from weather import get_location_list, get_design_conditions

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AHU Psychrometric Chart",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

psychrolib.SetUnitSystem(psychrolib.SI)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stSidebar"] {background-color: #0f1117;}
    [data-testid="stSidebar"] * {color: #e0e0e0 !important;}
    .main {background-color: #0f1117;}
    h1, h2, h3, h4 {color: #00c3ff !important;}
    .stTabs [data-baseweb="tab"] {color: #aaa;}
    .stTabs [aria-selected="true"] {color: #00c3ff !important; border-bottom: 2px solid #00c3ff;}
    .metric-card {
        background: #1a1d2e;
        border: 1px solid #2a2d3e;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 4px 0;
    }
    .metric-card .label {font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 0.08em;}
    .metric-card .value {font-size: 20px; font-weight: 600; color: #00c3ff; margin-top: 2px;}
    .metric-card .unit  {font-size: 12px; color: #666;}
    .section-header {
        font-size: 12px; font-weight: 600; letter-spacing: 0.1em;
        color: #00c3ff !important; text-transform: uppercase;
        border-bottom: 1px solid #1e3a5f; padding-bottom: 4px; margin: 16px 0 8px 0;
    }
    div[data-testid="stNumberInput"] label {font-size: 12px !important;}
    div[data-testid="stSelectbox"] label {font-size: 12px !important;}
    .stAlert {border-radius: 8px;}
</style>
""", unsafe_allow_html=True)


# ── Helper: metric card ───────────────────────────────────────────────────────
def metric_card(label, value, unit=""):
    st.markdown(f"""
    <div class="metric-card">
        <div class="label">{label}</div>
        <div class="value">{value} <span class="unit">{unit}</span></div>
    </div>
    """, unsafe_allow_html=True)


# ── Session state defaults ────────────────────────────────────────────────────
def init_defaults():
    defaults = {
        "location": "ABU DHABI",
        "altitude": 22.0,
        "it_load": 1500.0,
        # ASHRAE zone
        "ash_tdb_low": 18.0, "ash_twb_low": 6.4,
        "ash_tdb_high": 18.0, "ash_twb_high": 14.4,
        "ash_tdb_27_low": 27.0, "ash_twb_27_low": 10.27,
        "ash_tdb_27_high": 27.0, "ash_twb_27_high": 13.2,
        # CRAH
        "crah_off_tdb": 25.0, "crah_off_twb": 16.5,
        "crah_on_tdb": 36.0, "crah_on_twb": 19.8,
        # Outdoor
        "oat_n20_tdb": 49.2, "oat_n20_twb": 32.9,
        "oat_04e_tdb": 35.2, "oat_04e_twb": 30.75,
        "oat_04h_tdb": 33.6, "oat_04h_twb": 30.2,
        "oat_min_n20_tdb": 7.3, "oat_min_n20_twb": 3.6,
        "oat_min_04h_tdb": 31.1, "oat_min_04h_twb": 14.7,
        # AHU off-coil
        "oc_cool_tdb": 12.9, "oc_cool_twb": 12.9,
        "oc_enth_tdb": 14.55, "oc_enth_twb": 14.55,
        "oc_dehum_tdb": 15.0, "oc_dehum_twb": 15.0,
        "oc_heat_tdb": 36.0, "oc_heat_twb": 15.82,
        "oc_humid_tdb": 15.0, "oc_humid_twb": 15.0,
        # Return air
        "ra_tdb": 35.0, "ra_twb": 25.0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_defaults()


# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌡️ AHU Psychro")
    st.markdown("---")

    # Location
    st.markdown('<div class="section-header">📍 Location</div>', unsafe_allow_html=True)
    locations = get_location_list()
    loc_idx = locations.index(st.session_state.location) if st.session_state.location in locations else 0
    location = st.selectbox("Location", locations, index=loc_idx, key="location")

    dc = get_design_conditions(location)
    altitude = st.number_input("Altitude (m)", value=float(dc.altitude_m) if dc else 0.0,
                                min_value=0.0, max_value=5000.0, step=1.0, key="altitude")

    if dc and location != "CUSTOM":
        if st.button("📥 Auto-Fill ASHRAE Design Conditions", use_container_width=True):
            st.session_state.oat_n20_tdb   = dc.cooling_db_n20
            st.session_state.oat_n20_twb   = dc.cooling_wb_n20
            st.session_state.oat_04e_tdb   = dc.cooling_db_04
            st.session_state.oat_04e_twb   = dc.cooling_wb_04
            st.session_state.oat_04h_tdb   = dc.dehumid_db
            st.session_state.oat_04h_twb   = dc.dehumid_wb
            st.session_state.oat_min_n20_tdb = dc.heating_db_n20
            st.session_state.oat_min_n20_twb = dc.heating_db_meanwb
            st.session_state.oat_min_04h_tdb = dc.heating_db_004
            st.session_state.oat_min_04h_twb = dc.heating_db_meanwb + 2
            st.rerun()

    st.markdown(f"""
    <div style="background:#1a1d2e;border-radius:6px;padding:8px 12px;margin:6px 0;font-size:11px;color:#888;">
        📌 {dc.location + ', ' + dc.country if dc else '—'} &nbsp;|&nbsp; Alt: {altitude:.0f} m
    </div>
    """, unsafe_allow_html=True)

    pressure = altitude_to_pressure(altitude)

    # Global
    st.markdown('<div class="section-header">⚡ System Loads</div>', unsafe_allow_html=True)
    it_load = st.number_input("IT Load (kW)", value=st.session_state.it_load,
                               min_value=0.0, step=10.0, key="it_load")

    # Tabs for input groups
    st.markdown('<div class="section-header">🌿 Air States (Tdb / Twb)</div>', unsafe_allow_html=True)

    with st.expander("ASHRAE Zone Limits", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.number_input("18°C Low WB [Twb]", key="ash_twb_low", step=0.1, format="%.1f")
            st.number_input("18°C High WB [Twb]", key="ash_twb_high", step=0.1, format="%.1f")
            st.number_input("27°C Low WB [Twb]", key="ash_twb_27_low", step=0.1, format="%.1f")
            st.number_input("27°C High WB [Twb]", key="ash_twb_27_high", step=0.1, format="%.1f")

    with st.expander("CRAH Conditions", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.number_input("Off-Coil Tdb", key="crah_off_tdb", step=0.1, format="%.1f")
            st.number_input("On-Coil Tdb", key="crah_on_tdb", step=0.1, format="%.1f")
        with c2:
            st.number_input("Off-Coil Twb", key="crah_off_twb", step=0.1, format="%.1f")
            st.number_input("On-Coil Twb", key="crah_on_twb", step=0.1, format="%.1f")

    with st.expander("Outdoor Design", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.number_input("Max N=20 Tdb", key="oat_n20_tdb", step=0.1, format="%.1f")
            st.number_input("Max 0.4%E Tdb", key="oat_04e_tdb", step=0.1, format="%.1f")
            st.number_input("Max 0.4%H Tdb", key="oat_04h_tdb", step=0.1, format="%.1f")
            st.number_input("Min N=20 Tdb", key="oat_min_n20_tdb", step=0.1, format="%.1f")
            st.number_input("Min 0.4%H Tdb", key="oat_min_04h_tdb", step=0.1, format="%.1f")
        with c2:
            st.number_input("Max N=20 Twb", key="oat_n20_twb", step=0.1, format="%.1f")
            st.number_input("Max 0.4%E Twb", key="oat_04e_twb", step=0.1, format="%.1f")
            st.number_input("Max 0.4%H Twb", key="oat_04h_twb", step=0.1, format="%.1f")
            st.number_input("Min N=20 Twb", key="oat_min_n20_twb", step=0.1, format="%.1f")
            st.number_input("Min 0.4%H Twb", key="oat_min_04h_twb", step=0.1, format="%.1f")

    with st.expander("AHU Off-Coil", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.number_input("Cool Tdb", key="oc_cool_tdb", step=0.1, format="%.1f")
            st.number_input("Enthalpy Tdb", key="oc_enth_tdb", step=0.1, format="%.1f")
            st.number_input("Dehum Tdb", key="oc_dehum_tdb", step=0.1, format="%.1f")
            st.number_input("Heat Tdb", key="oc_heat_tdb", step=0.1, format="%.1f")
        with c2:
            st.number_input("Cool Twb", key="oc_cool_twb", step=0.1, format="%.1f")
            st.number_input("Enthalpy Twb", key="oc_enth_twb", step=0.1, format="%.1f")
            st.number_input("Dehum Twb", key="oc_dehum_twb", step=0.1, format="%.1f")
            st.number_input("Heat Twb", key="oc_heat_twb", step=0.1, format="%.1f")

    with st.expander("Return Air", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.number_input("RA Tdb", key="ra_tdb", step=0.1, format="%.1f")
        with c2:
            st.number_input("RA Twb", key="ra_twb", step=0.1, format="%.1f")

    # Chart options
    st.markdown('<div class="section-header">🎨 Chart Display</div>', unsafe_allow_html=True)
    show_rh_lines  = st.checkbox("RH Lines", value=True)
    show_enth_lines = st.checkbox("Enthalpy Lines", value=True)
    show_wb_lines  = st.checkbox("WB Lines", value=False)
    show_ashrae    = st.checkbox("ASHRAE A1 Zone", value=True)
    show_processes = st.checkbox("Process Lines", value=True)
    show_table     = st.checkbox("Data Table", value=True)


# ── COMPUTE AIR STATES ────────────────────────────────────────────────────────
s = st.session_state
P = pressure

states = {
    "ASHRAE 18 Low"  : AirState("ASHRAE 18 Low",  s.ash_tdb_low,  s.ash_twb_low,  P),
    "ASHRAE 18 High" : AirState("ASHRAE 18 High", s.ash_tdb_high, s.ash_twb_high, P),
    "ASHRAE 27 Low"  : AirState("ASHRAE 27 Low",  s.ash_tdb_27_low, s.ash_twb_27_low, P),
    "ASHRAE 27 High" : AirState("ASHRAE 27 High", s.ash_tdb_27_high, s.ash_twb_27_high, P),
    "CRAH Off-Coil"  : AirState("CRAH Off-Coil",  s.crah_off_tdb, s.crah_off_twb, P),
    "CRAH On-Coil"   : AirState("CRAH On-Coil",   s.crah_on_tdb,  s.crah_on_twb,  P),
    "OAT Max N=20"   : AirState("OAT Max N=20",   s.oat_n20_tdb,  s.oat_n20_twb,  P),
    "OAT Max 0.4%E"  : AirState("OAT Max 0.4%E",  s.oat_04e_tdb,  s.oat_04e_twb,  P),
    "OAT Max 0.4%H"  : AirState("OAT Max 0.4%H",  s.oat_04h_tdb,  s.oat_04h_twb,  P),
    "OAT Min N=20"   : AirState("OAT Min N=20",   s.oat_min_n20_tdb, s.oat_min_n20_twb, P),
    "OAT Min 0.4%H"  : AirState("OAT Min 0.4%H",  s.oat_min_04h_tdb, s.oat_min_04h_twb, P),
    "OC Max Cool"    : AirState("OC Max Cool",     s.oc_cool_tdb,  s.oc_cool_twb,  P),
    "OC Enthalpy"    : AirState("OC Enthalpy",     s.oc_enth_tdb,  s.oc_enth_twb,  P),
    "OC Dehum"       : AirState("OC Dehum",        s.oc_dehum_tdb, s.oc_dehum_twb, P),
    "OC Heat"        : AirState("OC Heat",         s.oc_heat_tdb,  s.oc_heat_twb,  P),
    "Return Air"     : AirState("Return Air",      s.ra_tdb,       s.ra_twb,       P),
}


# ── CHART COLORS ──────────────────────────────────────────────────────────────
COLORS = {
    "ASHRAE"    : "#2ecc71",
    "CRAH"      : "#e74c3c",
    "OUTDOOR"   : "#f39c12",
    "OFF_COIL"  : "#00c3ff",
    "RETURN"    : "#9b59b6",
    "SAT_CURVE" : "#ffffff",
    "RH_LINE"   : "rgba(150,150,150,0.35)",
    "ENTH_LINE" : "rgba(100,180,255,0.20)",
    "WB_LINE"   : "rgba(200,200,100,0.20)",
    "ASHRAE_ZONE": "rgba(46,204,113,0.10)",
}

POINT_GROUPS = {
    "ASHRAE 18 Low" : ("ASHRAE A1 Zone", COLORS["ASHRAE"], "diamond"),
    "ASHRAE 18 High": ("ASHRAE A1 Zone", COLORS["ASHRAE"], "diamond"),
    "ASHRAE 27 Low" : ("ASHRAE A1 Zone", COLORS["ASHRAE"], "diamond"),
    "ASHRAE 27 High": ("ASHRAE A1 Zone", COLORS["ASHRAE"], "diamond"),
    "CRAH Off-Coil" : ("CRAH",          COLORS["CRAH"],    "circle"),
    "CRAH On-Coil"  : ("CRAH",          COLORS["CRAH"],    "circle"),
    "OAT Max N=20"  : ("Outdoor",       COLORS["OUTDOOR"], "square"),
    "OAT Max 0.4%E" : ("Outdoor",       COLORS["OUTDOOR"], "square"),
    "OAT Max 0.4%H" : ("Outdoor",       COLORS["OUTDOOR"], "square"),
    "OAT Min N=20"  : ("Outdoor",       COLORS["OUTDOOR"], "square-open"),
    "OAT Min 0.4%H" : ("Outdoor",       COLORS["OUTDOOR"], "square-open"),
    "OC Max Cool"   : ("AHU Off-Coil",  COLORS["OFF_COIL"], "star"),
    "OC Enthalpy"   : ("AHU Off-Coil",  COLORS["OFF_COIL"], "star"),
    "OC Dehum"      : ("AHU Off-Coil",  COLORS["OFF_COIL"], "star"),
    "OC Heat"       : ("AHU Off-Coil",  COLORS["OFF_COIL"], "star"),
    "Return Air"    : ("Return Air",    COLORS["RETURN"],   "triangle-up"),
}


# ── BUILD CHART ───────────────────────────────────────────────────────────────
def build_chart():
    fig = go.Figure()

    tdb_min, tdb_max = -10, 55
    w_max = 32  # g/kg

    # --- Saturation curve ---
    t_sat, w_sat = saturation_curve(P, tdb_min, tdb_max)
    fig.add_trace(go.Scatter(
        x=t_sat, y=w_sat, mode="lines",
        line=dict(color=COLORS["SAT_CURVE"], width=2.5),
        name="Saturation (100%RH)",
        hovertemplate="Tdb: %{x:.1f}°C<br>W: %{y:.2f} g/kg<extra>Saturation</extra>"
    ))

    # --- RH lines ---
    if show_rh_lines:
        for rh_val in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
            t_rh, w_rh = rh_curve(rh_val, P, tdb_min, tdb_max)
            valid = [(t, w) for t, w in zip(t_rh, w_rh) if w is not None and w <= w_max]
            if valid:
                tv, wv = zip(*valid)
                show_legend = (rh_val == 0.1)
                fig.add_trace(go.Scatter(
                    x=tv, y=wv, mode="lines",
                    line=dict(color=COLORS["RH_LINE"], width=0.8, dash="dot"),
                    name="RH Lines" if show_legend else None,
                    legendgroup="rh_lines",
                    showlegend=show_legend,
                    hovertemplate=f"RH={rh_val*100:.0f}%<br>Tdb: %{{x:.1f}}°C<br>W: %{{y:.2f}} g/kg<extra></extra>",
                ))
                # Label
                mid = len(tv) // 2
                fig.add_annotation(
                    x=tv[mid], y=wv[mid],
                    text=f"{rh_val*100:.0f}%",
                    font=dict(size=9, color="#666"),
                    showarrow=False,
                    xanchor="left", yanchor="bottom"
                )

    # --- Enthalpy lines ---
    if show_enth_lines:
        for h_val in range(0, 120, 10):
            t_h, w_h = enthalpy_line(h_val, P, tdb_min, tdb_max)
            valid = [(t, w) for t, w in zip(t_h, w_h) if w is not None and 0 <= w <= w_max]
            if valid:
                tv, wv = zip(*valid)
                show_legend = (h_val == 0)
                fig.add_trace(go.Scatter(
                    x=tv, y=wv, mode="lines",
                    line=dict(color=COLORS["ENTH_LINE"], width=0.6),
                    name="Enthalpy Lines" if show_legend else None,
                    legendgroup="enth_lines",
                    showlegend=show_legend,
                    hovertemplate=f"h={h_val} kJ/kg<br>Tdb: %{{x:.1f}}°C<br>W: %{{y:.2f}} g/kg<extra></extra>",
                ))
                if tv and wv and wv[-1] <= w_max:
                    fig.add_annotation(
                        x=tv[-1], y=wv[-1],
                        text=f"{h_val}",
                        font=dict(size=8, color="#336699"),
                        showarrow=False, xanchor="left"
                    )

    # --- WB lines ---
    if show_wb_lines:
        for wb_val in range(5, 35, 5):
            t_wb, w_wb = wb_line(wb_val, P, wb_val, tdb_max)
            valid = [(t, w) for t, w in zip(t_wb, w_wb) if w is not None and w <= w_max]
            if valid:
                tv, wv = zip(*valid)
                show_legend = (wb_val == 5)
                fig.add_trace(go.Scatter(
                    x=tv, y=wv, mode="lines",
                    line=dict(color=COLORS["WB_LINE"], width=0.7, dash="longdash"),
                    name="WB Lines" if show_legend else None,
                    legendgroup="wb_lines",
                    showlegend=show_legend,
                ))

    # --- ASHRAE A1 zone polygon ---
    if show_ashrae:
        a18l = states["ASHRAE 18 Low"]
        a18h = states["ASHRAE 18 High"]
        a27h = states["ASHRAE 27 High"]
        a27l = states["ASHRAE 27 Low"]
        zone_x = [a18l.tdb, a18h.tdb, a27h.tdb, a27l.tdb, a18l.tdb]
        zone_y = [a18l.w_gkg, a18h.w_gkg, a27h.w_gkg, a27l.w_gkg, a18l.w_gkg]
        fig.add_trace(go.Scatter(
            x=zone_x, y=zone_y, fill="toself",
            fillcolor=COLORS["ASHRAE_ZONE"],
            line=dict(color=COLORS["ASHRAE"], width=1.5, dash="dash"),
            name="ASHRAE A1 Zone",
            legendgroup="ashrae_zone",
            hoverinfo="skip"
        ))

    # --- Process lines ---
    if show_processes:
        process_pairs = [
            ("OAT Max N=20", "OC Max Cool",   COLORS["OUTDOOR"], "Summer Max Cooling"),
            ("OAT Max 0.4%E","OC Enthalpy",   COLORS["OUTDOOR"], "Summer Enthalpy"),
            ("OAT Max 0.4%H","OC Dehum",      COLORS["OUTDOOR"], "Summer Dehum"),
            ("OAT Min N=20", "OC Heat",       COLORS["OFF_COIL"], "Winter Heating"),
            ("OC Max Cool",  "CRAH Off-Coil", COLORS["CRAH"],    "DOAS→CRAH"),
            ("CRAH On-Coil", "CRAH Off-Coil", COLORS["CRAH"],    "CRAH Process"),
            ("Return Air",   "CRAH On-Coil",  COLORS["RETURN"],  "Return→CRAH"),
        ]
        first = True
        for p1_name, p2_name, color, label in process_pairs:
            if p1_name in states and p2_name in states:
                p1 = states[p1_name]
                p2 = states[p2_name]
                fig.add_trace(go.Scatter(
                    x=[p1.tdb, p2.tdb], y=[p1.w_gkg, p2.w_gkg],
                    mode="lines+markers",
                    line=dict(color=color, width=1.2, dash="dot"),
                    marker=dict(symbol="arrow", size=10, color=color,
                                angleref="previous"),
                    name=label,
                    legendgroup="processes",
                    showlegend=first,
                    hovertemplate=f"{label}<br>%{{x:.1f}}°C / %{{y:.2f}} g/kg<extra></extra>",
                ))
                first = False

    # --- Data points ---
    added_groups = set()
    for name, state in states.items():
        group_name, color, symbol = POINT_GROUPS.get(name, ("Other", "#fff", "circle"))
        show_leg = group_name not in added_groups
        added_groups.add(group_name)

        hover = (
            f"<b>{name}</b><br>"
            f"Tdb: {state.tdb:.1f} °C<br>"
            f"Twb: {state.twb:.1f} °C<br>"
            f"RH: {state.rh*100:.1f} %<br>"
            f"W: {state.w_gkg:.2f} g/kg<br>"
            f"h: {state.h:.2f} kJ/kg<br>"
            f"Tdp: {state.tdp:.1f} °C<br>"
            f"ρ: {state.density:.3f} kg/m³"
        )

        fig.add_trace(go.Scatter(
            x=[state.tdb], y=[state.w_gkg],
            mode="markers+text",
            marker=dict(symbol=symbol, size=12, color=color,
                        line=dict(width=1.5, color="#fff")),
            text=[name.replace(" ", "<br>")],
            textposition="top center",
            textfont=dict(size=9, color=color),
            name=group_name,
            legendgroup=group_name,
            showlegend=show_leg,
            hovertemplate=hover + "<extra></extra>",
            customdata=[[name]],
        ))

    # --- Layout ---
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0f1117",
        plot_bgcolor="#0f1117",
        font=dict(family="Inter, Arial", size=11, color="#cccccc"),
        title=dict(
            text=f"<b>Psychrometric Chart</b> — {location} | Alt: {altitude:.0f} m | P: {P/1000:.2f} kPa | IT Load: {it_load:.0f} kW",
            font=dict(size=14, color="#00c3ff"),
            x=0.0, xanchor="left"
        ),
        xaxis=dict(
            title="Dry Bulb Temperature [°C]",
            range=[tdb_min, tdb_max],
            showgrid=True, gridcolor="#1e2230", gridwidth=0.5,
            zeroline=True, zerolinecolor="#333",
            ticksuffix="°C",
            dtick=5,
        ),
        yaxis=dict(
            title="Humidity Ratio [g/kg dry air]",
            range=[0, w_max],
            showgrid=True, gridcolor="#1e2230", gridwidth=0.5,
            ticksuffix=" g/kg",
            dtick=2,
        ),
        legend=dict(
            bgcolor="rgba(15,17,23,0.85)",
            bordercolor="#2a2d3e", borderwidth=1,
            font=dict(size=10),
            itemsizing="constant",
            x=1.01, y=1.0, xanchor="left",
        ),
        margin=dict(l=60, r=220, t=60, b=60),
        height=680,
        hovermode="closest",
    )

    return fig


# ── MAIN LAYOUT ───────────────────────────────────────────────────────────────
st.markdown("# 🌡️ AHU Psychrometric Design Tool")
st.markdown(f"**Location:** {location} &nbsp;|&nbsp; **Pressure:** {pressure/1000:.2f} kPa &nbsp;|&nbsp; **IT Load:** {it_load:.0f} kW")
st.markdown("---")

# Chart
fig = build_chart()
st.plotly_chart(fig, use_container_width=True, config={
    "displayModeBar": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "toImageButtonOptions": {"format": "png", "width": 1600, "height": 900, "scale": 2},
})

# ── METRICS ROW ───────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Air State Summary")

cols = st.columns(4)
key_states = ["OAT Max N=20", "OC Max Cool", "CRAH Off-Coil", "Return Air"]
for col, name in zip(cols, key_states):
    st_obj = states[name]
    with col:
        st.markdown(f"**{name}**")
        metric_card("Dry Bulb",   f"{st_obj.tdb:.1f}", "°C")
        metric_card("Humidity W", f"{st_obj.w_gkg:.2f}", "g/kg")
        metric_card("Enthalpy h", f"{st_obj.h:.1f}", "kJ/kg")
        metric_card("RH",         f"{st_obj.rh*100:.1f}", "%")
        metric_card("Dew Point",  f"{st_obj.tdp:.1f}", "°C")
        metric_card("Density",    f"{st_obj.density:.3f}", "kg/m³")

# ── DATA TABLE ───────────────────────────────────────────────────────────────
if show_table:
    st.markdown("---")
    st.markdown("### Full Psychrometric State Table")

    rows = []
    for name, st_obj in states.items():
        rows.append({
            "State": name,
            "Tdb [°C]": round(st_obj.tdb, 2),
            "Twb [°C]": round(st_obj.twb, 2),
            "RH [%]": round(st_obj.rh * 100, 1),
            "W [g/kg]": round(st_obj.w_gkg, 3),
            "h [kJ/kg]": round(st_obj.h, 2),
            "Tdp [°C]": round(st_obj.tdp, 2),
            "ρ [kg/m³]": round(st_obj.density, 4),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True,
                 column_config={
                     "Tdb [°C]":  st.column_config.NumberColumn(format="%.1f °C"),
                     "Twb [°C]":  st.column_config.NumberColumn(format="%.1f °C"),
                     "RH [%]":    st.column_config.NumberColumn(format="%.1f %%"),
                     "W [g/kg]":  st.column_config.NumberColumn(format="%.3f g/kg"),
                     "h [kJ/kg]": st.column_config.NumberColumn(format="%.2f kJ/kg"),
                     "Tdp [°C]":  st.column_config.NumberColumn(format="%.1f °C"),
                     "ρ [kg/m³]": st.column_config.NumberColumn(format="%.4f kg/m³"),
                 })

    # Download button
    csv = df.to_csv(index=False)
    st.download_button(
        label="⬇️ Download CSV",
        data=csv,
        file_name=f"psychro_{location.replace(' ','_')}.csv",
        mime="text/csv",
    )

# ── FOOTER ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#444;font-size:11px;'>"
    "Psychrometric calculations: ASHRAE Fundamentals · psychrolib SI · Plotly Interactive"
    "</div>",
    unsafe_allow_html=True
)
