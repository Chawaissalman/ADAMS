"""Refrigerant property layer.

Uses CoolProp (NIST-grade) when available; otherwise a crude analytic fallback
so the app still runs. Mirrors the validated notebook logic.
"""
from __future__ import annotations
import numpy as np
from .assumptions import C2K, K2C

try:
    from CoolProp.CoolProp import PropsSI
    HAVE_COOLPROP = True
    COOLPROP_VERSION = __import__("CoolProp").__version__
except Exception:                                   # pragma: no cover
    HAVE_COOLPROP = False
    COOLPROP_VERSION = None

FLUID_ALIAS = {"R1336mzz(Z)": "R1336mzz(Z)", "R1234yf": "R1234yf",
               "R1234ze(E)": "R1234ze(E)", "R134a": "R134a",
               "R513A": "R513A.mix", "CO2": "CO2"}

# R1336mzz(Z) (Honeywell Solstice N40 base) is not in this CoolProp build, so
# we use the vendor saturation curve below plus property estimates.
# (T_C, P_bar) points from the spec:
_R1336_SAT = [(35, 1.3), (40, 1.6), (45, 2.0), (50, 2.5),
              (55, 3.1), (60, 3.8), (65, 4.5), (75, 5.8)]
# Approximate liquid/vapor properties for R1336mzz(Z) (low-pressure HFO):
#   hfg ~166 kJ/kg, rho_l ~1340 (warm), rho_v scales with P, mu_l ~2.0e-4
_R1336_PROPS = dict(hfg=166e3, rho_l=1340.0, mu_l=2.0e-4, cp_l=1300.0, Tcrit=171.3)


def _r1336_psat_bar(T_C):
    """Interpolate/extrapolate saturation pressure [bar] from the vendor curve."""
    pts = _R1336_SAT
    if T_C <= pts[0][0]:
        (t0, p0), (t1, p1) = pts[0], pts[1]
    elif T_C >= pts[-1][0]:
        (t0, p0), (t1, p1) = pts[-2], pts[-1]
    else:
        for i in range(len(pts) - 1):
            if pts[i][0] <= T_C <= pts[i + 1][0]:
                (t0, p0), (t1, p1) = pts[i], pts[i + 1]
                break
    return p0 + (p1 - p0) * (T_C - t0) / (t1 - t0)


def _r1336_tsat_C(P_bar):
    """Inverse: saturation temperature [°C] from pressure [bar]."""
    pts = _R1336_SAT
    if P_bar <= pts[0][1]:
        (t0, p0), (t1, p1) = pts[0], pts[1]
    elif P_bar >= pts[-1][1]:
        (t0, p0), (t1, p1) = pts[-2], pts[-1]
    else:
        for i in range(len(pts) - 1):
            if pts[i][1] <= P_bar <= pts[i + 1][1]:
                (t0, p0), (t1, p1) = pts[i], pts[i + 1]
                break
    return t0 + (t1 - t0) * (P_bar - p0) / (p1 - p0)


# hfg[J/kg], rho_l, rho_v, mu_l[Pa.s], cp_l[J/kgK], Psat@45C[Pa]
_FALLBACK = {
    "R1234yf":    (140e3, 1050, 55, 1.5e-4, 1350, 11.6e5),
    "R1234ze(E)": (155e3, 1100, 40, 1.8e-4, 1400, 8.8e5),
    "R134a":      (160e3, 1150, 55, 1.7e-4, 1430, 11.6e5),
    "R513A":      (145e3, 1100, 55, 1.6e-4, 1380, 11.0e5),
    "CO2":        (160e3, 700, 250, 8e-5, 3000, 90e5),
}


def fluid_critical_C(name: str) -> float:
    if name == "R1336mzz(Z)":
        return _R1336_PROPS["Tcrit"]
    cp = FLUID_ALIAS[name]
    if HAVE_COOLPROP:
        try:
            return float(K2C(PropsSI("Tcrit", cp)))
        except Exception:
            return np.nan
    return {"CO2": 31.0}.get(name, 100.0)


def sat_props(name: str, T_C: float, Q: float) -> dict:
    """Saturation property bundle at temperature T_C, quality Q (0 liq, 1 vap)."""
    # R1336mzz(Z): use the vendor saturation curve + property estimates.
    if name == "R1336mzz(Z)":
        if T_C >= _R1336_PROPS["Tcrit"] - 0.5:
            return {"ok": False, "note": "T>=Tcrit: transcritical"}
        P = _r1336_psat_bar(T_C) * 1e5
        pr = _R1336_PROPS
        # vapor density via ideal-gas estimate (M ~164 g/mol)
        rho_v = max(P * 0.164 / (8.314 * (T_C + 273.15)), 1.0)
        return {"ok": True, "note": "vendor-curve", "P": P,
                "rho_l": pr["rho_l"], "rho_v": rho_v, "hfg": pr["hfg"],
                "mu_l": pr["mu_l"], "cp_l": pr["cp_l"],
                "h_l": 0.0, "h_v": pr["hfg"]}
    cp = FLUID_ALIAS[name]
    T = float(C2K(T_C))
    Tcrit = fluid_critical_C(name)
    if not np.isnan(Tcrit) and T_C >= Tcrit - 0.5:
        return {"ok": False, "note": f"T>=Tcrit ({Tcrit:.1f} C): transcritical"}
    if HAVE_COOLPROP:
        try:
            P = PropsSI("P", "T", T, "Q", Q, cp)
            d = {"ok": True, "note": "", "P": P,
                 "rho_l": PropsSI("D", "T", T, "Q", 0, cp),
                 "rho_v": PropsSI("D", "T", T, "Q", 1, cp),
                 "h_l": PropsSI("H", "T", T, "Q", 0, cp),
                 "h_v": PropsSI("H", "T", T, "Q", 1, cp),
                 "mu_l": PropsSI("V", "T", T, "Q", 0, cp),
                 "cp_l": PropsSI("C", "T", T, "Q", 0, cp)}
            d["hfg"] = d["h_v"] - d["h_l"]
            return d
        except Exception as ex:
            return {"ok": False, "note": f"CoolProp err: {ex}"}
    hfg, rl, rv, mul, cpl, Ps = _FALLBACK[name]
    return {"ok": True, "note": "fallback", "P": Ps, "rho_l": rl, "rho_v": rv,
            "hfg": hfg, "mu_l": mul, "cp_l": cpl, "h_l": 0.0, "h_v": hfg}


def refrigerant_comparison(A, x_out: float = 0.4):
    """Compare all candidate fluids at the current operating point."""
    import pandas as pd
    rows = []
    for name in FLUID_ALIAS:
        ev = sat_props(name, A.T_evap_C, 1.0)
        co = sat_props(name, A.T_cond_C, 0.0)
        if not ev["ok"] or not co["ok"]:
            rows.append({"Fluid": name, "Status": "n/a",
                         "Note": ev.get("note") or co.get("note", "")})
            continue
        hfg = ev["hfg"]
        Q = A.Q_rack_kW * 1e3
        mdot = Q / (hfg * x_out + 1000.0 * A.superheat_K)
        rows.append({
            "Fluid": name, "Status": "OK",
            "Pevap_bar": ev["P"] / 1e5, "Pcond_bar": co["P"] / 1e5,
            "PR": co["P"] / ev["P"], "hfg_kJ_kg": hfg / 1e3,
            "rho_l": co["rho_l"], "mdot_kg_s": mdot,
            "Vdot_Lmin": mdot / co["rho_l"] * 60000,
            "Tcrit_C": fluid_critical_C(name), "Note": ""})
    return pd.DataFrame(rows)
