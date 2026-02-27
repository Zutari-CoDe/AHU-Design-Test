"""
psychro_engine.py — Auto-derivation & process heat calculations
================================================================
Derives off-coil conditions from control setpoints and computes
all psychrometric process loads (Section 4 of the Excel sheet).

Formulas verified against AHU_Design.xlsx:
  - Q_total  = mdot_out * (h_out - h_in)          [kW]
  - Q_sens   = mdot_out * Cp * (Tdb_out - Tdb_in) [kW]
  - Q_lat    = Q_total - Q_sens                    [kW]
  - SHR      = Q_sens / Q_total
  - Moisture = (W_in - W_out) * mdot_out           [g/s, +ve = dehumidification]
  - mdot     = vol_flow * rho_at_state             [kg/s]
"""

import psychrolib
import numpy as np
from dataclasses import dataclass
from typing import Optional

psychrolib.SetUnitSystem(psychrolib.SI)

# ── Constants ─────────────────────────────────────────────────────────────────
Cp_air    = 1.008   # kJ/(kg·K) moist air specific heat
L_v       = 2501.0  # kJ/kg latent heat of vaporisation
ASHRAE_A1 = {       # Fixed ASHRAE 2021 A1 zone corners — never user inputs
    "ash_twb_low"     : 6.4,
    "ash_twb_high"    : 14.4,
    "ash_twb_27_low"  : 10.27,
    "ash_twb_27_high" : 13.2,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sat_tdb_for_enthalpy(target_h_kJ: float, P: float) -> float:
    """Find saturated Tdb such that h_sat = target_h_kJ [kJ/kg]."""
    from scipy.optimize import brentq
    def err(t):
        w = psychrolib.GetSatHumRatio(t, P)
        return psychrolib.GetMoistAirEnthalpy(t, w) / 1000 - target_h_kJ
    try:
        return round(brentq(err, 0.0, 30.0, xtol=0.01), 2)
    except Exception:
        return 14.55  # fallback to typical value


def _tdp(tdb, twb, P):
    w = psychrolib.GetHumRatioFromTWetBulb(tdb, twb, P)
    return psychrolib.GetTDewPointFromHumRatio(tdb, w, P)


def _twb_from_tdb_w(tdb, w, P):
    return psychrolib.GetTWetBulbFromHumRatio(tdb, w, P)


def _rho(tdb, twb, P):
    w = psychrolib.GetHumRatioFromTWetBulb(tdb, twb, P)
    return psychrolib.GetMoistAirDensity(tdb, w, P)


def _h(tdb, twb, P):
    w = psychrolib.GetHumRatioFromTWetBulb(tdb, twb, P)
    return psychrolib.GetMoistAirEnthalpy(tdb, w, P) / 1000  # kJ/kg


# ── Derived off-coil conditions ───────────────────────────────────────────────

def derive_off_coil(
    crah_off_tdb: float, crah_off_twb: float,
    crah_on_tdb: float,
    oat_min_oah_tdb: float, oat_min_oah_twb: float,
    oc_cool_margin: float,   # °C above CRAH dew point for OC Cool (default 2)
    oc_dehum_margin: float,  # °C above CRAH dew point for OC Dehum (default 4)
    oc_enth_target: float,   # target enthalpy kJ/kg for OC Enthalpy (default 44)
    P: float
) -> dict:
    """
    Auto-derive all AHU off-coil conditions from control setpoints.

    Returns dict of {field_id: value} matching app input field names.
    All off-coil states are at saturation (Twb = Tdb).
    """
    # CRAH off-coil dew point
    crah_off_tdp = _tdp(crah_off_tdb, crah_off_twb, P)

    # 1. OC Max Cool — saturated just above CRAH dew point (ensures CRAH coil stays dry)
    oc_cool_tdb = round(crah_off_tdp + oc_cool_margin, 1)
    oc_cool_twb = oc_cool_tdb  # saturated

    # 2. OC Dehum — saturated above CRAH DP (CRAH can still dehumidify)
    oc_dehum_tdb = round(crah_off_tdp + oc_dehum_margin, 1)
    oc_dehum_twb = oc_dehum_tdb

    # 3. OC Enthalpy — saturated at target enthalpy band
    oc_enth_tdb = _sat_tdb_for_enthalpy(oc_enth_target, P)
    oc_enth_twb = oc_enth_tdb

    # 4. OC Heat for humidification — sensible heat to CRAH on-coil Tdb,
    #    humidity ratio preserved from winter OA (sensible process, W = const)
    w_winter = psychrolib.GetHumRatioFromTWetBulb(oat_min_oah_tdb, oat_min_oah_twb, P)
    oc_heat_tdb = crah_on_tdb
    oc_heat_twb = round(_twb_from_tdb_w(crah_on_tdb, w_winter, P), 2)

    return {
        "oc_cool_tdb"  : oc_cool_tdb,
        "oc_cool_twb"  : oc_cool_twb,
        "oc_dehum_tdb" : oc_dehum_tdb,
        "oc_dehum_twb" : oc_dehum_twb,
        "oc_enth_tdb"  : oc_enth_tdb,
        "oc_enth_twb"  : oc_enth_twb,
        "oc_heat_tdb"  : oc_heat_tdb,
        "oc_heat_twb"  : oc_heat_twb,
        # Diagnostic
        "_crah_off_tdp"      : round(crah_off_tdp, 2),
        "_oc_cool_margin"    : oc_cool_margin,
        "_oc_dehum_margin"   : oc_dehum_margin,
        "_oc_enth_target_h"  : oc_enth_target,
    }


# ── Airflow & system calculations ─────────────────────────────────────────────

@dataclass
class SystemFlows:
    ahu_vol_flow: float    # m³/s — AHU DOAS volume flow
    ahu_mdot_out: float    # kg/s — AHU mass flow at off-coil density
    crah_vol_flow: float   # m³/s — total CRAH room volume flow
    crah_mdot: float       # kg/s — CRAH mass flow
    fan_load_kw: float     # kW — estimated fan electrical load
    fan_delta_t: float     # °C — fan heat rise
    Q_sens_total: float    # kW — total sensible load (IT + fans)


def compute_system_flows(
    it_load_kw: float,
    crah_off_tdb: float, crah_off_twb: float,
    crah_on_tdb: float,  crah_on_twb: float,
    oc_dehum_tdb: float, oc_dehum_twb: float,
    ahu_vol_flow_override: Optional[float],  # None = auto-calculate
    P: float,
    ahu_pressure_drop_pa: float = 600.0,    # assumed AHU duct pressure drop [Pa]
    aux_load_factor: float = 1.055,         # auxiliary heat factor (Excel D13: IT * 1.055)
) -> SystemFlows:
    """Compute all system flows from IT load and CRAH setpoints.

    Excel formulas replicated:
      D13: Q_sens = IT_load * 1.055  (5.5% for aux heat: lighting, UPS losses, people)
      D14: CRAH_mdot = Q_sens / (dT_CRAH * Cp_on_coil)
      D18: fan_kW = ahu_vol_flow * pressure_drop_Pa / 1000
      D19: fan_dT = fan_kW / (ahu_vol_flow * Cp_off_coil)  [Excel formula, W/vol basis]
    """
    # D13: total sensible load including auxiliary heat
    Q_sens = it_load_kw * aux_load_factor

    # D18: fan electrical load from volume flow and pressure drop
    if ahu_vol_flow_override and ahu_vol_flow_override > 0:
        ahu_vol_for_fan = ahu_vol_flow_override
    else:
        ahu_vol_for_fan = 0.0
    fan_load = round(ahu_vol_for_fan * ahu_pressure_drop_pa / 1000, 3)

    # CRAH flows
    rho_crah_in  = _rho(crah_on_tdb,  crah_on_twb,  P)
    rho_crah_out = _rho(crah_off_tdb, crah_off_twb, P)
    rho_crah_avg = (rho_crah_in + rho_crah_out) / 2
    dT_crah      = crah_on_tdb - crah_off_tdb

    crah_mdot    = Q_sens / (Cp_air * dT_crah)
    crah_vol     = crah_mdot / rho_crah_avg

    # AHU DOAS flows
    rho_ahu_out  = _rho(oc_dehum_tdb, oc_dehum_twb, P)

    if ahu_vol_flow_override and ahu_vol_flow_override > 0:
        ahu_vol = ahu_vol_flow_override
    else:
        # Auto: size AHU for 100% outdoor air makeup — typical 10-15% of room flow
        ahu_vol = round(crah_vol * 0.011, 3)  # ~1.1% of room flow

    ahu_mdot_out = ahu_vol * rho_ahu_out

    # D19: fan delta-T = fan_kW / (ahu_vol_flow * Cp_off_coil)
    # Excel formula: =D18/(D15*M37) — uses vol flow and Cp of off-coil state
    oc_dehum_w  = psychrolib.GetHumRatioFromTWetBulb(oc_dehum_tdb, oc_dehum_twb, P)
    Cp_oc       = 1.006 + 1.86 * oc_dehum_w  # Cp at off-coil state
    ahu_vol_fan = ahu_vol_flow_override if ahu_vol_flow_override else ahu_vol
    fan_delta_t = fan_load / (ahu_vol_fan * Cp_oc) if ahu_vol_fan > 0 else 0

    return SystemFlows(
        ahu_vol_flow  = round(ahu_vol, 4),
        ahu_mdot_out  = round(ahu_mdot_out, 4),
        crah_vol_flow = round(crah_vol, 2),
        crah_mdot     = round(crah_mdot, 2),
        fan_load_kw   = fan_load,
        fan_delta_t   = round(fan_delta_t, 3),
        Q_sens_total  = round(Q_sens, 1),
    )


# ── Process heat calculations (Section 4) ─────────────────────────────────────

@dataclass
class Process:
    name:     str
    state_in: str
    state_out: str
    tdb_in:   float
    w_in:     float    # g/kg
    h_in:     float    # kJ/kg
    tdb_out:  float
    w_out:    float    # g/kg
    h_out:    float    # kJ/kg
    mdot_in:  float    # kg/s
    mdot_out: float    # kg/s
    moisture: float    # g/s (+ve = dehumidification, -ve = humidification)
    Q_sens:   float    # kW
    Q_lat:    float    # kW
    Q_total:  float    # kW
    SHR:      float


def _process(name, state_in, state_out,
             tdb_in, twb_in, tdb_out, twb_out, vol_flow, P) -> Process:
    """
    Compute one psychrometric process using exact Excel formula structure:
      G_in  = vol_flow * rho_in
      G_out = vol_flow * rho_out
      H     = G_out * (W_in - W_out)                    [g/s moisture]
      I     = G_out * Cp_IN * (Tdb_out - Tdb_in)        [kW sensible, Cp of IN state]
      K     = -G_out * (h_in - h_out)                   [kW total]
      J     = K - I                                      [kW latent]
      L     = I / K                                      [SHR]
    """
    w_in_kg  = psychrolib.GetHumRatioFromTWetBulb(tdb_in,  twb_in,  P)  # kg/kg
    w_out_kg = psychrolib.GetHumRatioFromTWetBulb(tdb_out, twb_out, P)
    w_in     = w_in_kg  * 1000  # g/kg
    w_out    = w_out_kg * 1000

    h_in   = psychrolib.GetMoistAirEnthalpy(tdb_in,  w_in_kg)  / 1000  # kJ/kg
    h_out  = psychrolib.GetMoistAirEnthalpy(tdb_out, w_out_kg) / 1000

    rho_in  = psychrolib.GetMoistAirDensity(tdb_in,  w_in_kg,  P)
    rho_out = psychrolib.GetMoistAirDensity(tdb_out, w_out_kg, P)

    mdot_in  = vol_flow * rho_in
    mdot_out = vol_flow * rho_out

    # Cp of IN state: ASHRAE formula Cp_moist = 1.006 + 1.86*W [kJ/(kg.K)]
    # Matches Excel col M (Specific heat capacity) used in Qsens formula
    Cp_in = 1.006 + 1.86 * w_in_kg

    # Exact Excel formulas:
    Q_total  = -mdot_out * (h_in - h_out)            # = mdot_out*(h_out-h_in)
    Q_sens   = mdot_out * Cp_in * (tdb_out - tdb_in) # Cp of IN state
    Q_lat    = Q_total - Q_sens
    SHR      = Q_sens / Q_total if abs(Q_total) > 0.001 else float('nan')
    moisture = mdot_out * (w_in - w_out)              # g/s, +ve = dehumidification

    return Process(
        name=name, state_in=state_in, state_out=state_out,
        tdb_in=round(tdb_in,2), w_in=round(w_in,3), h_in=round(h_in,3),
        tdb_out=round(tdb_out,2), w_out=round(w_out,3), h_out=round(h_out,3),
        mdot_in=round(mdot_in,4), mdot_out=round(mdot_out,4),
        moisture=round(moisture,3),
        Q_sens=round(Q_sens,2), Q_lat=round(Q_lat,2),
        Q_total=round(Q_total,2),
        SHR=round(SHR,4) if not np.isnan(SHR) else None,
    )


def compute_processes(inp: dict, flows: SystemFlows, P: float) -> list[Process]:
    """
    Compute all psychrometric processes.
    inp: full input dict with all air state Tdb/Twb values.
    flows: SystemFlows from compute_system_flows().
    Returns list of Process objects.
    """
    V_ahu  = flows.ahu_vol_flow
    V_crah = flows.crah_vol_flow

    def f(key_tdb, key_twb): return float(inp[key_tdb]), float(inp[key_twb])

    oat_n20_tdb,    oat_n20_twb    = f("oat_n20_tdb",    "oat_n20_twb")
    oat_04e_tdb,    oat_04e_twb    = f("oat_04e_tdb",    "oat_04e_twb")
    oat_04h_tdb,    oat_04h_twb    = f("oat_04h_tdb",    "oat_04h_twb")
    oat_min_n20_tdb,oat_min_n20_twb= f("oat_min_n20_tdb","oat_min_n20_twb")
    oat_min_04h_tdb,oat_min_04h_twb= f("oat_min_04h_tdb","oat_min_04h_twb")
    crah_off_tdb,   crah_off_twb   = f("crah_off_tdb",   "crah_off_twb")
    crah_on_tdb,    crah_on_twb    = f("crah_on_tdb",    "crah_on_twb")
    oc_cool_tdb,    oc_cool_twb    = f("oc_cool_tdb",    "oc_cool_twb")
    oc_enth_tdb,    oc_enth_twb    = f("oc_enth_tdb",    "oc_enth_twb")
    oc_dehum_tdb,   oc_dehum_twb   = f("oc_dehum_tdb",   "oc_dehum_twb")
    oc_heat_tdb,    oc_heat_twb    = f("oc_heat_tdb",    "oc_heat_twb")
    ra_tdb,         ra_twb         = f("ra_tdb",         "ra_twb")

    processes = [
        _process("Summer Max Cooling",
                 "OAT Max N=20", "OC Max Cool",
                 oat_n20_tdb, oat_n20_twb, oc_cool_tdb, oc_cool_twb, V_ahu, P),

        _process("Summer Enthalpy Cooling",
                 "OAT Max 0.4%E", "OC Enthalpy",
                 oat_04e_tdb, oat_04e_twb, oc_enth_tdb, oc_enth_twb, V_ahu, P),

        _process("Summer Dehumidification",
                 "OAT Max 0.4%H", "OC Dehum",
                 oat_04h_tdb, oat_04h_twb, oc_dehum_tdb, oc_dehum_twb, V_ahu, P),

        _process("CRAH Cooling Loop",
                 "CRAH On-Coil", "CRAH Off-Coil",
                 crah_on_tdb, crah_on_twb, crah_off_tdb, crah_off_twb, V_crah, P),

        _process("Winter Heating",
                 "OAT Min N=20", "OC Heat",
                 oat_min_n20_tdb, oat_min_n20_twb, oc_heat_tdb, oc_heat_twb, V_ahu, P),

        _process("Winter Min OAH Heating",
                 "OAT Min 0.4%H", "OC Heat",
                 oat_min_04h_tdb, oat_min_04h_twb, oc_heat_tdb, oc_heat_twb, V_ahu, P),
    ]
    return processes


def process_to_dict(p: Process) -> dict:
    return {
        "name"    : p.name,
        "state_in": p.state_in,
        "state_out": p.state_out,
        "tdb_in"  : p.tdb_in,   "w_in"  : p.w_in,   "h_in"  : p.h_in,
        "tdb_out" : p.tdb_out,  "w_out" : p.w_out,  "h_out" : p.h_out,
        "mdot_in" : p.mdot_in,  "mdot_out": p.mdot_out,
        "moisture": p.moisture,
        "Q_sens"  : p.Q_sens,   "Q_lat" : p.Q_lat,  "Q_total": p.Q_total,
        "SHR"     : p.SHR,
    }
