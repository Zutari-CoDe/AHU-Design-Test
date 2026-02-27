"""
chart_png.py — Psychrometric chart matching the Excel reference image.

Layout:
  - X axis (bottom):       Dry Bulb Temperature [°C]   -5 to 50
  - Y axis (RIGHT side):   Humidity Ratio W [g/kg]      0 to 36
  - Left Y axis:           tick marks only (no label) — mirrored from right
  - Diagonal WB/enthalpy lines running bottom-left to top-right
  - Curved RH lines
  - Saturation curve sweeping from bottom-left to top-right
"""
import io
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import psychrolib

psychrolib.SetUnitSystem(psychrolib.SI)

# ── Colors matching the Excel chart ──────────────────────────────────────────
C = {
    "sat":            "#cc0000",     # red saturation curve (like Excel)
    "wb":             "#e8dfc8",     # warm beige WB/enthalpy lines
    "enth":           "#e8dfc8",     # same
    "rh":             "#e8dfc8",     # same
    "ashrae_a1":      "#22aa44",     # green dashed ASHRAE box
    "ashrae_a1_fill": "#22aa44",
    "crah":           "#000000",     # black CRAH line
    "outdoor_n20":    "#0066cc",     # blue  — MAX OAT N=20 line
    "outdoor_enth":   "#f5c518",     # yellow — OAE enthalpy line
    "outdoor_oah":    "#1a7a3a",     # dark green — OAH line
    "offcoil":        "#000000",     # black X markers
    "return":         "#7d3c98",
    "marker":         "#000000",     # all markers are black X like Excel
}

POINT_STYLES = {
    "ASHRAE 18 Low" : ("ASHRAE A1",    C["ashrae_a1"], "x", 60),
    "ASHRAE 18 High": ("ASHRAE A1",    C["ashrae_a1"], "x", 60),
    "ASHRAE 27 Low" : ("ASHRAE A1",    C["ashrae_a1"], "x", 60),
    "ASHRAE 27 High": ("ASHRAE A1",    C["ashrae_a1"], "x", 60),
    "CRAH Off-Coil" : ("CRAH",         "#000000",      "x", 70),
    "CRAH On-Coil"  : ("CRAH",         "#000000",      "x", 70),
    "OAT Max N=20"  : ("Outdoor",      "#000000",      "o", 80),  # filled circle
    "OAT Max 0.4%E" : ("Outdoor",      "#000000",      "x", 70),
    "OAT Max 0.4%H" : ("Outdoor",      "#000000",      "x", 70),
    "OAT Min N=20"  : ("Outdoor",      "#000000",      "x", 70),
    "OAT Min 0.4%H" : ("Outdoor",      "#000000",      "x", 70),
    "OC Max Cool"   : ("AHU Off-Coil", "#000000",      "x", 70),
    "OC Enthalpy"   : ("AHU Off-Coil", "#000000",      "x", 70),
    "OC Dehum"      : ("AHU Off-Coil", "#000000",      "x", 70),
    "OC Heat"       : ("AHU Off-Coil", "#000000",      "x", 70),
    "Return Air"    : ("Return Air",   "#000000",      "x", 70),
}

LABEL_MAP = {
    "ASHRAE 18 Low": None, "ASHRAE 18 High": None,
    "ASHRAE 27 Low": None, "ASHRAE 27 High": None,
    "CRAH Off-Coil":  "CRAH OFF COIL",
    "CRAH On-Coil":   "CRAH ON COIL",
    "OAT Max N=20":   "MAX OAT (N=20)",
    "OAT Max 0.4%E":  "MAX OAE (0.4%)",
    "OAT Max 0.4%H":  "MAX OAH (0.4%)",
    "OAT Min N=20":   "MIN OAT (N=20)",
    "OAT Min 0.4%H":  "MIN OAH (99.6%)",
    "OC Max Cool":    "OFF COIL MAX COOL",
    "OC Enthalpy":    "OFF COIL ENTHALPY",
    "OC Dehum":       "OFF COIL DEHUM",
    "OC Heat":        "OFF COIL HEATING FOR HUMIDIFICATION",
    "Return Air":     None,
}

# ── Psychro helpers ───────────────────────────────────────────────────────────
def _w_rh(t, rh, P):
    try:    return psychrolib.GetHumRatioFromRelHum(t, rh, P) * 1000
    except: return np.nan

def _w_wb(t, twb, P):
    try:    return psychrolib.GetHumRatioFromTWetBulb(t, twb, P) * 1000
    except: return np.nan

def _sat(P, t0, t1, n=500):
    ts = np.linspace(t0, t1, n)
    ws = np.array([_w_rh(t, 1.0, P) for t in ts])
    return ts, ws

def _rh_curve(rh, P, t0, t1, n=300):
    ts = np.linspace(t0, t1, n)
    ws = np.array([_w_rh(t, rh, P) for t in ts])
    return ts, ws

def _wb_line(twb, P, t0, t1, n=200):
    ts = np.linspace(max(t0, twb - 0.01), t1, n)
    ws = np.array([_w_wb(t, twb, P) for t in ts])
    return ts, ws

def _enth_line(h, P, t0, t1, n=200):
    ts = np.linspace(t0, t1, n)
    ws = []
    for t in ts:
        d = 2501 + 1.86*t
        ws.append((h - 1.006*t)/d*1000 if abs(d) > 1e-6 else np.nan)
    return ts, np.array(ws)

# ── Process line colors matching Excel ───────────────────────────────────────
PROC_COLORS = {
    ("OAT Max N=20",  "OC Max Cool"):   "#0066cc",   # blue
    ("OAT Max 0.4%E", "OC Enthalpy"):   "#f5c518",   # yellow
    ("OAT Max 0.4%H", "OC Dehum"):      "#1a7a3a",   # dark green
    ("OAT Min N=20",  "OC Heat"):       "#0066cc",   # blue
    ("OC Max Cool",   "CRAH Off-Coil"): "#000000",   # black
    ("CRAH On-Coil",  "CRAH Off-Coil"): "#000000",   # black
    ("Return Air",    "CRAH On-Coil"):  "#000000",
}


def render_chart_png(inp: dict, states: dict, P: float) -> bytes:

    T0, T1 = -5,  50    # Dry bulb X axis
    W0, W1 =  0,  36    # Humidity Y axis (right side)

    fig, ax = plt.subplots(figsize=(16, 10), dpi=140)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(T0, T1)
    ax.set_ylim(W0, W1)

    def _clip(ts, ws):
        m = (ts >= T0) & (ts <= T1) & (ws >= W0-0.2) & (ws <= W1+0.2) & \
            np.isfinite(ts) & np.isfinite(ws)
        return ts[m], ws[m]

    # ── Enthalpy / WB diagonal lines (beige, same style as Excel) ────────
    for h in range(-20, 160, 10):
        ts, ws = _enth_line(h, P, T0-5, T1+5)
        tc, wc = _clip(ts, ws)
        if len(tc) < 2: continue
        ax.plot(tc, wc, color=C["enth"], lw=0.6, zorder=1)

    for twb in range(-5, 51, 5):
        ts, ws = _wb_line(twb, P, T0, T1)
        tc, wc = _clip(ts, ws)
        if len(tc) < 2: continue
        ax.plot(tc, wc, color=C["wb"], lw=0.5, zorder=1)

    # ── RH curves (beige) ─────────────────────────────────────────────────
    for rh in [0.10,0.20,0.30,0.40,0.50,0.60,0.70,0.80,0.90]:
        ts, ws = _rh_curve(rh, P, T0, T1)
        tc, wc = _clip(ts, ws)
        if len(tc) < 2: continue
        ax.plot(tc, wc, color=C["rh"], lw=0.65, zorder=2)

    # ── Saturation curve (red, like Excel) ───────────────────────────────
    ts_sat, ws_sat = _sat(P, T0, T1)
    tc, wc = _clip(ts_sat, ws_sat)
    ax.plot(tc, wc, color=C["sat"], lw=1.8, zorder=5)

    # ── ASHRAE A1 zone – constant RH boundaries matching Excel TC9.9 zone ─
    ashrae_req = ["ASHRAE 18 Low","ASHRAE 18 High","ASHRAE 27 Low","ASHRAE 27 High"]
    if all(p in states for p in ashrae_req):
        import numpy as _np, psychrolib as _psl
        _psl.SetUnitSystem(_psl.SI)
        s18L = states["ASHRAE 18 Low"];  s18H = states["ASHRAE 18 High"]
        # Derive the two RH boundaries from the 18°C corner points
        rh_low  = _psl.GetRelHumFromHumRatio(s18L.tdb, s18L.w_gkg/1000, P)
        rh_high = _psl.GetRelHumFromHumRatio(s18H.tdb, s18H.w_gkg/1000, P)
        _tdbs = _np.linspace(18, 27, 60)
        # bottom boundary: constant RH low (tdb 18→27)
        bot_x = list(_tdbs)
        bot_y = [_psl.GetHumRatioFromRelHum(t, rh_low, P)*1000 for t in _tdbs]
        # right edge at tdb=27 (bottom to top)
        right_x = [27.0, 27.0]
        right_y = [_psl.GetHumRatioFromRelHum(27.0, rh_low, P)*1000,
                   _psl.GetHumRatioFromRelHum(27.0, rh_high, P)*1000]
        # top boundary: constant RH high (tdb 27→18)
        top_x = list(reversed(_tdbs))
        top_y = [_psl.GetHumRatioFromRelHum(t, rh_high, P)*1000 for t in reversed(_tdbs)]
        # left edge at tdb=18 closes the polygon
        zx = bot_x + right_x + top_x + [18.0]
        zy = bot_y + right_y + top_y + [s18L.w_gkg]
        ax.fill(zx, zy, color=C["ashrae_a1_fill"], alpha=0.10, zorder=3)
        ax.plot(zx, zy, color=C["ashrae_a1"], lw=1.5, ls="--", zorder=4)

    # ── Process lines ─────────────────────────────────────────────────────
    proc_pairs = [
        ("OAT Max N=20",  "OC Max Cool"),
        ("OAT Max 0.4%E", "OC Enthalpy"),
        ("OAT Max 0.4%H", "OC Dehum"),
        ("OAT Min N=20",  "OC Heat"),
        ("OC Max Cool",   "CRAH Off-Coil"),
        ("CRAH On-Coil",  "CRAH Off-Coil"),
        ("Return Air",    "CRAH On-Coil"),
    ]
    for a, b in proc_pairs:
        if a in states and b in states:
            col = PROC_COLORS.get((a, b), "#555555")
            p1, p2 = states[a], states[b]
            ax.plot([p1.tdb, p2.tdb], [p1.w_gkg, p2.w_gkg],
                    color=col, lw=2.0, zorder=6, solid_capstyle="round")

    # ── State points & labels ─────────────────────────────────────────────
    for name, st in states.items():
        _, col, mk, ms = POINT_STYLES.get(name, ("Other","#000","x",60))
        lw = 2.0 if mk == "x" else 1.5
        fc = col if mk == "o" else "none"
        ax.scatter(st.tdb, st.w_gkg, s=ms, c=fc,
                   edgecolors=col, linewidths=lw, marker=mk, zorder=9)
        lbl = LABEL_MAP.get(name, name)
        if lbl:
            # offset label below-right like the Excel chart
            ax.text(st.tdb + 0.4, st.w_gkg - 0.5, lbl,
                    fontsize=6.8, color="#333333",
                    ha="left", va="top", zorder=10,
                    fontfamily="Arial")

    # ── Right Y axis for Humidity Ratio ──────────────────────────────────
    # Hide left Y axis ticks/label, put humidity on right
    ax.yaxis.set_ticks_position("right")
    ax.yaxis.set_label_position("right")
    ax.set_ylabel("HUMIDITY G/KG",
                  fontsize=9, fontweight="bold", color="#cc0000",
                  labelpad=10, rotation=270, va="bottom")
    ax.set_yticks(range(W0, W1+1, 1))
    ax.yaxis.set_tick_params(labelsize=8, colors="#333333",
                              direction="out", length=3)

    # Light left Y tick marks (no labels) for grid reference
    ax.tick_params(axis="y", which="both", right=True, left=True,
                   labelleft=False, labelright=True)

    # ── X axis (bottom) ──────────────────────────────────────────────────
    ax.set_xlabel("DRY BULB TEMPERATURE °C",
                  fontsize=10, fontweight="bold", color="#000000", labelpad=6)
    ax.set_xticks(range(T0, T1+1, 5))
    ax.xaxis.set_tick_params(labelsize=9, colors="#333333",
                              direction="out", length=3)

    # ── Grid ──────────────────────────────────────────────────────────────
    ax.grid(True, color="#e8e8e8", lw=0.4, zorder=0)
    ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_color("#cccccc")
        s.set_linewidth(0.7)



    # ── Title ─────────────────────────────────────────────────────────────
    city = inp.get("city","")
    alt  = float(inp.get("altitude", 0))
    load = float(inp.get("it_load",  0))
    ax.set_title(
        f"Psychrometric chart  ·  {city}  ·  Alt {alt:.0f} m  ·  "
        f"P = {P/1000:.3f} kPa  ·  IT Load {load:.0f} kW",
        fontsize=11, color="#1a1a2e", pad=10)

    plt.tight_layout(pad=1.2)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150,
                facecolor="white", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.read()
