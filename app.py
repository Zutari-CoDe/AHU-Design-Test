"""
AHU Psychrometric Design Tool — Streamlit App
Zutari Infrastructure Engineering
"""
import io
import matplotlib
matplotlib.use("Agg")

import streamlit as st
import plotly.graph_objects as go
import psychrolib
import numpy as np

from psychro import AirState, altitude_to_pressure, saturation_curve, rh_curve, enthalpy_line, wb_line
from psychro_engine import derive_off_coil, compute_system_flows, compute_processes, process_to_dict, ASHRAE_A1
from weather_live import get_design_conditions_for_city, design_conditions_to_dict
from excel_export import build_excel

psychrolib.SetUnitSystem(psychrolib.SI)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AHU Psychrometric Design",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    .stMetric { background: #1e2230; border-radius: 8px; padding: 8px; }
    h1 { color: #00c3ff; }
    h2, h3 { color: #cccccc; }
    .section-header {
        background: #1e2230; border-left: 3px solid #00c3ff;
        padding: 6px 12px; border-radius: 4px; margin: 12px 0 8px 0;
        font-weight: 600; color: #cccccc;
    }
</style>
""", unsafe_allow_html=True)

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULTS = {
    "city": "Abu Dhabi", "altitude": 22.0, "it_load": 1500.0, "ahu_vol_flow": 1.605,
    **ASHRAE_A1,
    "crah_off_tdb": 25.0,  "crah_off_twb": 16.5,
    "crah_on_tdb":  36.0,  "crah_on_twb":  19.8,
    "oat_n20_tdb":  49.2,  "oat_n20_twb":  32.9,
    "oat_04e_tdb":  35.2,  "oat_04e_twb":  30.75,
    "oat_04h_tdb":  33.6,  "oat_04h_twb":  30.2,
    "oat_min_n20_tdb": 7.3,   "oat_min_n20_twb": 3.6,
    "oat_min_04h_tdb": 31.1,  "oat_min_04h_twb": 14.7,
    "oc_cool_tdb":  12.9,  "oc_cool_twb":  12.9,
    "oc_enth_tdb":  14.55, "oc_enth_twb":  14.55,
    "oc_dehum_tdb": 15.0,  "oc_dehum_twb": 15.0,
    "oc_heat_tdb":  36.0,  "oc_heat_twb":  15.82,
    "ra_tdb": 35.0, "ra_twb": 25.0,
    "oc_cool_margin": 2.0, "oc_dehum_margin": 4.0, "oc_enth_target": 44.0,
    "show_rh_lines": True, "show_enth_lines": True, "show_wb_lines": False,
    "show_ashrae": True, "show_processes": True,
}

# Initialise session state from defaults
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Colours ───────────────────────────────────────────────────────────────────
C = {
    "ASHRAE": "#2ecc71", "CRAH": "#e74c3c", "OUTDOOR": "#f39c12",
    "OFF_COIL": "#00c3ff", "RETURN": "#9b59b6", "SAT_CURVE": "#ffffff",
    "RH_LINE": "rgba(150,150,150,0.35)", "ENTH_LINE": "rgba(100,180,255,0.20)",
    "WB_LINE": "rgba(200,200,100,0.20)", "ASHRAE_ZONE": "rgba(46,204,113,0.10)",
}
POINT_GROUPS = {
    "ASHRAE 18 Low":  ("ASHRAE A1 Zone", C["ASHRAE"],   "diamond"),
    "ASHRAE 18 High": ("ASHRAE A1 Zone", C["ASHRAE"],   "diamond"),
    "ASHRAE 27 Low":  ("ASHRAE A1 Zone", C["ASHRAE"],   "diamond"),
    "ASHRAE 27 High": ("ASHRAE A1 Zone", C["ASHRAE"],   "diamond"),
    "CRAH Off-Coil":  ("CRAH",           C["CRAH"],     "circle"),
    "CRAH On-Coil":   ("CRAH",           C["CRAH"],     "circle"),
    "OAT Max N=20":   ("Outdoor",        C["OUTDOOR"],  "square"),
    "OAT Max 0.4%E":  ("Outdoor",        C["OUTDOOR"],  "square"),
    "OAT Max 0.4%H":  ("Outdoor",        C["OUTDOOR"],  "square"),
    "OAT Min N=20":   ("Outdoor",        C["OUTDOOR"],  "square-open"),
    "OAT Min 0.4%H":  ("Outdoor",        C["OUTDOOR"],  "square-open"),
    "OC Max Cool":    ("AHU Off-Coil",   C["OFF_COIL"], "star"),
    "OC Enthalpy":    ("AHU Off-Coil",   C["OFF_COIL"], "star"),
    "OC Dehum":       ("AHU Off-Coil",   C["OFF_COIL"], "star"),
    "OC Heat":        ("AHU Off-Coil",   C["OFF_COIL"], "star"),
    "Return Air":     ("Return Air",     C["RETURN"],   "triangle-up"),
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_inp():
    return {k: st.session_state[k] for k in DEFAULTS}

def compute_states(inp):
    P = altitude_to_pressure(inp["altitude"])
    return P, {
        "ASHRAE 18 Low":  AirState("ASHRAE 18 Low",  18.0, inp["ash_twb_low"],      P),
        "ASHRAE 18 High": AirState("ASHRAE 18 High", 18.0, inp["ash_twb_high"],     P),
        "ASHRAE 27 Low":  AirState("ASHRAE 27 Low",  27.0, inp["ash_twb_27_low"],   P),
        "ASHRAE 27 High": AirState("ASHRAE 27 High", 27.0, inp["ash_twb_27_high"],  P),
        "CRAH Off-Coil":  AirState("CRAH Off-Coil",  inp["crah_off_tdb"], inp["crah_off_twb"], P),
        "CRAH On-Coil":   AirState("CRAH On-Coil",   inp["crah_on_tdb"],  inp["crah_on_twb"],  P),
        "OAT Max N=20":   AirState("OAT Max N=20",   inp["oat_n20_tdb"],  inp["oat_n20_twb"],  P),
        "OAT Max 0.4%E":  AirState("OAT Max 0.4%E",  inp["oat_04e_tdb"],  inp["oat_04e_twb"],  P),
        "OAT Max 0.4%H":  AirState("OAT Max 0.4%H",  inp["oat_04h_tdb"],  inp["oat_04h_twb"],  P),
        "OAT Min N=20":   AirState("OAT Min N=20",   inp["oat_min_n20_tdb"], inp["oat_min_n20_twb"], P),
        "OAT Min 0.4%H":  AirState("OAT Min 0.4%H",  inp["oat_min_04h_tdb"], inp["oat_min_04h_twb"], P),
        "OC Max Cool":    AirState("OC Max Cool",    inp["oc_cool_tdb"],  inp["oc_cool_twb"],  P),
        "OC Enthalpy":    AirState("OC Enthalpy",    inp["oc_enth_tdb"],  inp["oc_enth_twb"],  P),
        "OC Dehum":       AirState("OC Dehum",       inp["oc_dehum_tdb"], inp["oc_dehum_twb"], P),
        "OC Heat":        AirState("OC Heat",        inp["oc_heat_tdb"],  inp["oc_heat_twb"],  P),
        "Return Air":     AirState("Return Air",     inp["ra_tdb"],       inp["ra_twb"],       P),
    }

def build_chart(inp, states, P):
    fig = go.Figure()
    tdb_min, tdb_max, w_max = -10, 55, 32

    t_sat, w_sat = saturation_curve(P, tdb_min, tdb_max)
    fig.add_trace(go.Scatter(x=t_sat, y=w_sat, mode="lines",
        line=dict(color=C["SAT_CURVE"], width=2.5), name="Saturation (100% RH)",
        hovertemplate="Tdb: %{x:.1f}°C | W: %{y:.2f} g/kg<extra>Saturation</extra>"))

    if inp.get("show_rh_lines"):
        for i, rh in enumerate([.1,.2,.3,.4,.5,.6,.7,.8,.9]):
            tv, wv = rh_curve(rh, P, tdb_min, tdb_max)
            v = [(t,w) for t,w in zip(tv,wv) if w is not None and w <= w_max]
            if not v: continue
            tx, wx = zip(*v)
            fig.add_trace(go.Scatter(x=tx, y=wx, mode="lines",
                line=dict(color=C["RH_LINE"], width=0.8, dash="dot"),
                name="RH Lines" if i==0 else None, legendgroup="rh", showlegend=(i==0),
                hovertemplate=f"RH={rh*100:.0f}%<br>%{{x:.1f}}°C / %{{y:.2f}} g/kg<extra></extra>"))
            mid = len(tx)//2
            fig.add_annotation(x=tx[mid], y=wx[mid], text=f"{rh*100:.0f}%",
                font=dict(size=9, color="#666"), showarrow=False, xanchor="left", yanchor="bottom")

    if inp.get("show_enth_lines"):
        for i, h in enumerate(range(0, 120, 10)):
            tv, wv = enthalpy_line(h, P, tdb_min, tdb_max)
            v = [(t,w) for t,w in zip(tv,wv) if w is not None and 0 <= w <= w_max]
            if not v: continue
            tx, wx = zip(*v)
            fig.add_trace(go.Scatter(x=tx, y=wx, mode="lines",
                line=dict(color=C["ENTH_LINE"], width=0.6),
                name="Enthalpy Lines" if i==0 else None, legendgroup="enth", showlegend=(i==0),
                hovertemplate=f"h={h} kJ/kg<br>%{{x:.1f}}°C / %{{y:.2f}} g/kg<extra></extra>"))
            if wx[-1] <= w_max:
                fig.add_annotation(x=tx[-1], y=wx[-1], text=f"{h}",
                    font=dict(size=8, color="#336699"), showarrow=False, xanchor="left")

    if inp.get("show_wb_lines"):
        for i, wb in enumerate(range(5, 35, 5)):
            tv, wv = wb_line(wb, P, wb, tdb_max)
            v = [(t,w) for t,w in zip(tv,wv) if w is not None and w <= w_max]
            if not v: continue
            tx, wx = zip(*v)
            fig.add_trace(go.Scatter(x=tx, y=wx, mode="lines",
                line=dict(color=C["WB_LINE"], width=0.7, dash="longdash"),
                name="WB Lines" if i==0 else None, legendgroup="wb", showlegend=(i==0)))

    if inp.get("show_ashrae"):
        import psychrolib as _psl
        _psl.SetUnitSystem(_psl.SI)
        s18L = states["ASHRAE 18 Low"]
        s18H = states["ASHRAE 18 High"]
        rh_low  = _psl.GetRelHumFromHumRatio(s18L.tdb, s18L.w_gkg/1000, P)
        rh_high = _psl.GetRelHumFromHumRatio(s18H.tdb, s18H.w_gkg/1000, P)
        _tdbs = np.linspace(18, 27, 60)
        bot_x = list(_tdbs)
        bot_y = [_psl.GetHumRatioFromRelHum(t, rh_low,  P)*1000 for t in _tdbs]
        right_x = [27.0, 27.0]
        right_y = [_psl.GetHumRatioFromRelHum(27.0, rh_low,  P)*1000,
                   _psl.GetHumRatioFromRelHum(27.0, rh_high, P)*1000]
        top_x = list(reversed(_tdbs))
        top_y = [_psl.GetHumRatioFromRelHum(t, rh_high, P)*1000 for t in reversed(_tdbs)]
        zx = bot_x + right_x + top_x + [18.0]
        zy = bot_y + right_y + top_y + [s18L.w_gkg]
        fig.add_trace(go.Scatter(x=zx, y=zy, fill="toself", fillcolor=C["ASHRAE_ZONE"],
            line=dict(color=C["ASHRAE"], width=1.5, dash="dash"),
            name="ASHRAE A1 Zone", hoverinfo="skip"))

    if inp.get("show_processes"):
        pairs = [
            ("OAT Max N=20",  "OC Max Cool",  C["OUTDOOR"],  "Summer Max Cooling"),
            ("OAT Max 0.4%E", "OC Enthalpy",  C["OUTDOOR"],  "Summer Enthalpy"),
            ("OAT Max 0.4%H", "OC Dehum",     C["OUTDOOR"],  "Summer Dehum"),
            ("OAT Min N=20",  "OC Heat",      C["OFF_COIL"], "Winter Heating"),
            ("OC Max Cool",   "CRAH Off-Coil",C["CRAH"],     "DOAS→CRAH"),
            ("CRAH On-Coil",  "CRAH Off-Coil",C["CRAH"],     "CRAH Process"),
            ("Return Air",    "CRAH On-Coil", C["RETURN"],   "Return→CRAH"),
        ]
        for i, (a, b, col, lbl) in enumerate(pairs):
            p1, p2 = states[a], states[b]
            fig.add_trace(go.Scatter(x=[p1.tdb, p2.tdb], y=[p1.w_gkg, p2.w_gkg],
                mode="lines+markers", line=dict(color=col, width=1.2, dash="dot"),
                marker=dict(symbol="arrow", size=10, color=col, angleref="previous"),
                name="Processes" if i==0 else None, legendgroup="proc", showlegend=(i==0),
                hovertemplate=f"{lbl}<br>%{{x:.1f}}°C / %{{y:.2f}} g/kg<extra></extra>"))

    added = set()
    for name, st_obj in states.items():
        grp, col, sym = POINT_GROUPS.get(name, ("Other", "#fff", "circle"))
        sl = grp not in added
        added.add(grp)
        hover = (f"<b>{name}</b><br>Tdb:{st_obj.tdb:.1f}°C Twb:{st_obj.twb:.1f}°C<br>"
                 f"RH:{st_obj.rh*100:.1f}% W:{st_obj.w_gkg:.2f}g/kg<br>"
                 f"h:{st_obj.h:.2f}kJ/kg Tdp:{st_obj.tdp:.1f}°C ρ:{st_obj.density:.3f}kg/m³")
        fig.add_trace(go.Scatter(x=[st_obj.tdb], y=[st_obj.w_gkg], mode="markers+text",
            marker=dict(symbol=sym, size=12, color=col, line=dict(width=1.5, color="#fff")),
            text=[name], textposition="top center", textfont=dict(size=9, color=col),
            name=grp, legendgroup=grp, showlegend=sl,
            hovertemplate=hover+"<extra></extra>"))

    fig.update_layout(
        template="plotly_dark", paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
        font=dict(family="Inter,Arial", size=11, color="#cccccc"),
        title=dict(
            text=(f"<b>Psychrometric Chart</b> — {inp.get('city','')} | "
                  f"Alt:{float(inp.get('altitude',0)):.0f}m | "
                  f"P:{P/1000:.2f}kPa | IT:{float(inp.get('it_load',0)):.0f}kW"),
            font=dict(size=14, color="#00c3ff"), x=0.0, xanchor="left"),
        xaxis=dict(title="Dry Bulb Temperature [°C]", range=[tdb_min, tdb_max],
                   showgrid=True, gridcolor="#1e2230", dtick=5, ticksuffix="°C"),
        yaxis=dict(title="Humidity Ratio [g/kg dry air]", range=[0, w_max],
                   showgrid=True, gridcolor="#1e2230", dtick=2, ticksuffix=" g/kg", side="right"),
        legend=dict(bgcolor="rgba(15,17,23,0.85)", bordercolor="#2a2d3e", borderwidth=1,
                    font=dict(size=10), x=0.01, y=0.99, xanchor="left", yanchor="top"),
        margin=dict(l=60, r=120, t=60, b=60), height=700, hovermode="closest")
    return fig

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🌡️ AHU Design")
    st.caption("Psychrometric Design Tool — Zutari")
    st.divider()

    # ── Project ───────────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📋 Project & Location</div>', unsafe_allow_html=True)
    st.session_state["city"]         = st.text_input("City / Location", value=st.session_state["city"])
    st.session_state["altitude"]     = st.number_input("Altitude (m)", value=float(st.session_state["altitude"]), min_value=0.0, max_value=3000.0, step=1.0)
    st.session_state["it_load"]      = st.number_input("IT Load (kW)", value=float(st.session_state["it_load"]), min_value=100.0, max_value=20000.0, step=50.0)
    st.session_state["ahu_vol_flow"] = st.number_input("AHU Volume Flow (m³/s)", value=float(st.session_state["ahu_vol_flow"]), min_value=0.1, max_value=20.0, step=0.005, format="%.3f")

    # Weather fetch
    if st.button("🌍 Fetch Weather Data", use_container_width=True):
        with st.spinner(f"Fetching ERA5 data for {st.session_state['city']}..."):
            try:
                dc = design_conditions_to_dict(get_design_conditions_for_city(st.session_state["city"]))
                for k, v in dc.items():
                    if k in st.session_state:
                        st.session_state[k] = v
                st.success(f"✅ Weather data loaded for {st.session_state['city']}")
                st.rerun()
            except Exception as e:
                st.error(f"❌ {e}")

    st.divider()

    # ── Outdoor Design ────────────────────────────────────────────────────────
    with st.expander("☀️ Outdoor Design Conditions", expanded=False):
        st.caption("Summer Cooling")
        c1, c2 = st.columns(2)
        with c1:
            st.session_state["oat_n20_tdb"]  = st.number_input("N=20 Tdb (°C)",  value=float(st.session_state["oat_n20_tdb"]),  step=0.1, key="oat_n20_tdb_in")
            st.session_state["oat_04e_tdb"]  = st.number_input("0.4%E Tdb (°C)", value=float(st.session_state["oat_04e_tdb"]),  step=0.1, key="oat_04e_tdb_in")
            st.session_state["oat_04h_tdb"]  = st.number_input("0.4%H Tdb (°C)", value=float(st.session_state["oat_04h_tdb"]),  step=0.1, key="oat_04h_tdb_in")
        with c2:
            st.session_state["oat_n20_twb"]  = st.number_input("N=20 Twb (°C)",  value=float(st.session_state["oat_n20_twb"]),  step=0.1, key="oat_n20_twb_in")
            st.session_state["oat_04e_twb"]  = st.number_input("0.4%E Twb (°C)", value=float(st.session_state["oat_04e_twb"]),  step=0.1, key="oat_04e_twb_in")
            st.session_state["oat_04h_twb"]  = st.number_input("0.4%H Twb (°C)", value=float(st.session_state["oat_04h_twb"]),  step=0.1, key="oat_04h_twb_in")
        st.caption("Winter Heating")
        c1, c2 = st.columns(2)
        with c1:
            st.session_state["oat_min_n20_tdb"] = st.number_input("Min N=20 Tdb (°C)",  value=float(st.session_state["oat_min_n20_tdb"]), step=0.1, key="oat_min_n20_tdb_in")
            st.session_state["oat_min_04h_tdb"] = st.number_input("Min 0.4%H Tdb (°C)", value=float(st.session_state["oat_min_04h_tdb"]), step=0.1, key="oat_min_04h_tdb_in")
        with c2:
            st.session_state["oat_min_n20_twb"] = st.number_input("Min N=20 Twb (°C)",  value=float(st.session_state["oat_min_n20_twb"]), step=0.1, key="oat_min_n20_twb_in")
            st.session_state["oat_min_04h_twb"] = st.number_input("Min 0.4%H Twb (°C)", value=float(st.session_state["oat_min_04h_twb"]), step=0.1, key="oat_min_04h_twb_in")

    # ── CRAH Setpoints ────────────────────────────────────────────────────────
    with st.expander("❄️ CRAH Setpoints", expanded=True):
        st.caption("CRAH Off-Coil (Supply to Cold Aisle)")
        c1, c2 = st.columns(2)
        with c1:
            st.session_state["crah_off_tdb"] = st.number_input("Off-Coil Tdb (°C)", value=float(st.session_state["crah_off_tdb"]), min_value=15.0, max_value=35.0, step=0.1, key="crah_off_tdb_in")
        with c2:
            st.session_state["crah_off_twb"] = st.number_input("Off-Coil Twb (°C)", value=float(st.session_state["crah_off_twb"]), min_value=5.0,  max_value=30.0, step=0.1, key="crah_off_twb_in")
        st.caption("CRAH On-Coil (Return from Hot Aisle)")
        c1, c2 = st.columns(2)
        with c1:
            st.session_state["crah_on_tdb"] = st.number_input("On-Coil Tdb (°C)", value=float(st.session_state["crah_on_tdb"]), min_value=20.0, max_value=55.0, step=0.1, key="crah_on_tdb_in")
        with c2:
            st.session_state["crah_on_twb"] = st.number_input("On-Coil Twb (°C)", value=float(st.session_state["crah_on_twb"]), min_value=5.0,  max_value=35.0, step=0.1, key="crah_on_twb_in")
        st.caption("Return Air")
        c1, c2 = st.columns(2)
        with c1:
            st.session_state["ra_tdb"] = st.number_input("Return Air Tdb (°C)", value=float(st.session_state["ra_tdb"]), step=0.1, key="ra_tdb_in")
        with c2:
            st.session_state["ra_twb"] = st.number_input("Return Air Twb (°C)", value=float(st.session_state["ra_twb"]), step=0.1, key="ra_twb_in")

    # ── AHU Off-Coil ──────────────────────────────────────────────────────────
    with st.expander("💨 AHU Off-Coil Conditions", expanded=False):
        st.caption("Derive margins")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.session_state["oc_cool_margin"]  = st.number_input("Cool Margin (°C)",  value=float(st.session_state["oc_cool_margin"]),  min_value=0.0, max_value=10.0, step=0.5, key="oc_cool_margin_in")
        with c2:
            st.session_state["oc_dehum_margin"] = st.number_input("Dehum Margin (°C)", value=float(st.session_state["oc_dehum_margin"]), min_value=0.0, max_value=10.0, step=0.5, key="oc_dehum_margin_in")
        with c3:
            st.session_state["oc_enth_target"]  = st.number_input("Enth Target (kJ/kg)", value=float(st.session_state["oc_enth_target"]), min_value=30.0, max_value=60.0, step=1.0, key="oc_enth_target_in")

        if st.button("⚡ Derive Off-Coil Conditions", use_container_width=True):
            inp = get_inp()
            P = altitude_to_pressure(inp["altitude"])
            try:
                d = derive_off_coil(
                    crah_off_tdb=inp["crah_off_tdb"], crah_off_twb=inp["crah_off_twb"],
                    crah_on_tdb=inp["crah_on_tdb"],
                    oat_min_oah_tdb=inp["oat_min_04h_tdb"], oat_min_oah_twb=inp["oat_min_04h_twb"],
                    oc_cool_margin=inp["oc_cool_margin"], oc_dehum_margin=inp["oc_dehum_margin"],
                    oc_enth_target=inp["oc_enth_target"], P=P,
                )
                for k in ["oc_cool_tdb","oc_cool_twb","oc_enth_tdb","oc_enth_twb",
                          "oc_dehum_tdb","oc_dehum_twb","oc_heat_tdb","oc_heat_twb"]:
                    st.session_state[k] = d[k]
                st.success(f"✅ CRAH DP={d['_crah_off_tdp']:.2f}°C  |  OC Cool={d['oc_cool_tdb']:.1f}°C  |  Dehum={d['oc_dehum_tdb']:.1f}°C")
                st.rerun()
            except Exception as e:
                st.error(f"❌ {e}")

        st.caption("Manual override values")
        cols = st.columns(2)
        labels = [
            ("oc_cool_tdb","OC Cool Tdb"),("oc_cool_twb","OC Cool Twb"),
            ("oc_enth_tdb","OC Enth Tdb"),("oc_enth_twb","OC Enth Twb"),
            ("oc_dehum_tdb","OC Dehum Tdb"),("oc_dehum_twb","OC Dehum Twb"),
            ("oc_heat_tdb","OC Heat Tdb"),("oc_heat_twb","OC Heat Twb"),
        ]
        for i, (k, lbl) in enumerate(labels):
            with cols[i % 2]:
                st.session_state[k] = st.number_input(f"{lbl} (°C)", value=float(st.session_state[k]), step=0.1, key=f"{k}_in")

    # ── ASHRAE A1 Zone ────────────────────────────────────────────────────────
    with st.expander("📐 ASHRAE A1 Zone", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.session_state["ash_twb_low"]     = st.number_input("Lower WB @ 18°C", value=float(st.session_state["ash_twb_low"]),     step=0.1, key="ash_twb_low_in")
            st.session_state["ash_twb_27_low"]  = st.number_input("Lower WB @ 27°C", value=float(st.session_state["ash_twb_27_low"]),  step=0.1, key="ash_twb_27_low_in")
        with c2:
            st.session_state["ash_twb_high"]    = st.number_input("Upper WB @ 18°C", value=float(st.session_state["ash_twb_high"]),    step=0.1, key="ash_twb_high_in")
            st.session_state["ash_twb_27_high"] = st.number_input("Upper WB @ 27°C", value=float(st.session_state["ash_twb_27_high"]), step=0.1, key="ash_twb_27_high_in")

    # ── Chart Options ─────────────────────────────────────────────────────────
    with st.expander("🎨 Chart Options", expanded=False):
        st.session_state["show_ashrae"]     = st.toggle("Show ASHRAE A1 Zone",  value=st.session_state["show_ashrae"])
        st.session_state["show_processes"]  = st.toggle("Show Process Lines",   value=st.session_state["show_processes"])
        st.session_state["show_rh_lines"]   = st.toggle("Show RH Curves",       value=st.session_state["show_rh_lines"])
        st.session_state["show_enth_lines"] = st.toggle("Show Enthalpy Lines",  value=st.session_state["show_enth_lines"])
        st.session_state["show_wb_lines"]   = st.toggle("Show Wet Bulb Lines",  value=st.session_state["show_wb_lines"])

# ── Main area ─────────────────────────────────────────────────────────────────
st.title("AHU Psychrometric Design")
st.caption(f"**{st.session_state['city']}**  |  Alt: {st.session_state['altitude']:.0f}m  |  IT Load: {st.session_state['it_load']:.0f}kW  |  AHU Flow: {st.session_state['ahu_vol_flow']:.3f}m³/s")

inp = get_inp()

try:
    P, states = compute_states(inp)
except Exception as e:
    st.error(f"Error computing states: {e}")
    st.stop()

tab1, tab2, tab3, tab4 = st.tabs(["📊 Psychrometric Chart", "🌡️ Moist Air States", "💧 System Flows", "⚙️ Process Loads"])

# ── Tab 1: Chart ──────────────────────────────────────────────────────────────
with tab1:
    try:
        fig = build_chart(inp, states, P)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Chart error: {e}")

    # Excel download
    try:
        xlsx = build_excel(inp, None, states, P)
        city_slug = inp["city"].replace(" ", "_")
        st.download_button(
            label="📥 Download Excel Report",
            data=xlsx,
            file_name=f"AHU_Design_{city_slug}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except Exception as e:
        st.warning(f"Excel export unavailable: {e}")

# ── Tab 2: Moist Air States ───────────────────────────────────────────────────
with tab2:
    import pandas as pd
    rows = []
    for name, s in states.items():
        rows.append({
            "State":      name,
            "Tdb (°C)":   round(s.tdb,    1),
            "Twb (°C)":   round(s.twb,    2),
            "RH (%)":     round(s.rh*100, 1),
            "W (g/kg)":   round(s.w_gkg,  3),
            "h (kJ/kg)":  round(s.h,      2),
            "Tdp (°C)":   round(s.tdp,    1),
            "ρ (kg/m³)":  round(s.density,4),
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True,
                 column_config={
                     "Tdb (°C)":  st.column_config.NumberColumn(format="%.1f"),
                     "Twb (°C)":  st.column_config.NumberColumn(format="%.2f"),
                     "RH (%)":    st.column_config.NumberColumn(format="%.1f"),
                     "W (g/kg)":  st.column_config.NumberColumn(format="%.3f"),
                     "h (kJ/kg)": st.column_config.NumberColumn(format="%.2f"),
                     "Tdp (°C)":  st.column_config.NumberColumn(format="%.1f"),
                     "ρ (kg/m³)": st.column_config.NumberColumn(format="%.4f"),
                 })
    st.caption(f"Site pressure: {P/1000:.3f} kPa (altitude {inp['altitude']:.0f}m)")

# ── Tab 3: System Flows ───────────────────────────────────────────────────────
with tab3:
    try:
        flows = compute_system_flows(
            it_load_kw=inp["it_load"], ahu_vol_flow_override=inp["ahu_vol_flow"],
            crah_off_tdb=inp["crah_off_tdb"], crah_off_twb=inp["crah_off_twb"],
            crah_on_tdb=inp["crah_on_tdb"],   crah_on_twb=inp["crah_on_twb"],
            oc_dehum_tdb=inp["oc_dehum_tdb"], oc_dehum_twb=inp["oc_dehum_twb"], P=P,
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("IT Load",              f"{inp['it_load']:.0f} kW")
        c2.metric("Total Sensible Load",  f"{flows.Q_sens_total:.1f} kW")
        c3.metric("Fan Load",             f"{flows.fan_load_kw:.2f} kW")
        c4.metric("Fan ΔT",               f"{flows.fan_delta_t:.2f} °C")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("CRAH Mass Flow",   f"{flows.crah_mdot:.2f} kg/s")
        c2.metric("CRAH Volume Flow", f"{flows.crah_vol_flow:.2f} m³/s")
        c3.metric("AHU Volume Flow",  f"{flows.ahu_vol_flow:.4f} m³/s")
        c4.metric("AHU Mass Flow",    f"{flows.ahu_mdot_out:.4f} kg/s")

    except Exception as e:
        st.error(f"System flows error: {e}")

# ── Tab 4: Process Loads ──────────────────────────────────────────────────────
with tab4:
    try:
        flows = compute_system_flows(
            it_load_kw=inp["it_load"], ahu_vol_flow_override=inp["ahu_vol_flow"],
            crah_off_tdb=inp["crah_off_tdb"], crah_off_twb=inp["crah_off_twb"],
            crah_on_tdb=inp["crah_on_tdb"],   crah_on_twb=inp["crah_on_twb"],
            oc_dehum_tdb=inp["oc_dehum_tdb"], oc_dehum_twb=inp["oc_dehum_twb"], P=P,
        )
        procs = compute_processes(inp, flows, P)
        proc_rows = []
        for p in procs:
            proc_rows.append({
                "Process":       p.name,
                "State In":      p.state_in,
                "State Out":     p.state_out,
                "Tdb In (°C)":   p.tdb_in,
                "Tdb Out (°C)":  p.tdb_out,
                "W In (g/kg)":   p.w_in,
                "W Out (g/kg)":  p.w_out,
                "Q Sens (kW)":   p.Q_sens,
                "Q Lat (kW)":    p.Q_lat,
                "Q Total (kW)":  p.Q_total,
                "SHR":           p.SHR,
                "Moisture (g/s)":p.moisture,
            })
        import pandas as pd
        df2 = pd.DataFrame(proc_rows)
        st.dataframe(df2, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Process loads error: {e}")
