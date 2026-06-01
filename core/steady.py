"""Steady-state thermodynamics: energy/mass balance, cold plate, condenser, sizing.

Ported verbatim (logic-wise) from the validated notebook so results match.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from dataclasses import dataclass
from .assumptions import CPW
from .fluids import sat_props


def steady_state(A, name=None, x_out=0.4, mode="free") -> dict:
    """Steady-state primary + secondary energy/mass balance."""
    name = name or A.fluid
    ev = sat_props(name, A.T_evap_C, 1.0)
    co = sat_props(name, A.T_cond_C, 0.0)
    if not ev["ok"] or not co["ok"]:
        return {"ok": False, "note": ev.get("note") or co.get("note")}
    hfg = ev["hfg"]
    cp_v = 1000.0
    Q = A.Q_rack_kW * 1e3
    mdot = Q / (hfg * x_out + cp_v * A.superheat_K)
    Vdot = mdot / co["rho_l"]
    dP = (A.dP_coldplate_kPa + A.dP_pipe_kPa) * 1e3 + max(0, co["P"] - ev["P"])
    Wpump = Vdot * dP / max(A.eta_pump, 1e-3)
    Qcond = Q + Wpump
    Tw_in = A.Tw_in_free_C if mode != "hot" else A.Tw_in_hot_C
    dTw = max(A.Tw_out_target_C - Tw_in, 5.0)
    mdot_w = Qcond / (CPW * dTw)
    Vdot_w = mdot_w / 1000.0
    pinch = 5.0
    Tcond_min_feasible = Tw_in + pinch + dTw
    Qchiller = 0.0
    COP = None
    if A.T_cond_C < Tcond_min_feasible:
        Qchiller = Qcond
        COP = 4.5
    W_chiller = (Qchiller / COP) if COP else 0.0
    reuse_min = 45.0
    Q_reuse = Qcond if A.Tw_out_target_C >= reuse_min and mode == "reuse" else 0.0
    W_waterpump = Vdot_w * 150e3 / 0.6
    W_fans = A.fan_frac_of_reject * Qcond
    W_loop = Wpump + W_waterpump + W_chiller + W_fans
    pPUE_loop = (Q + W_loop) / Q
    W_ups = A.ups_loss_frac * Q
    W_misc = A.misc_facility_frac * Q
    W_total = W_loop + W_ups + W_misc
    PUE_full = (Q + W_total) / Q
    return {"ok": True, "fluid": name, "mode": mode, "mdot": mdot,
            "Vdot_Lmin": Vdot * 60000, "Wpump_W": Wpump,
            "Qcond_kW": Qcond / 1e3, "mdot_w": mdot_w,
            "Vdot_w_Lmin": Vdot_w * 60000, "Tw_in": Tw_in,
            "Tw_out": A.Tw_out_target_C, "Qchiller_kW": Qchiller / 1e3,
            "W_chiller_W": W_chiller, "Q_reuse_kW": Q_reuse / 1e3,
            "W_waterpump_W": W_waterpump, "W_fans_W": W_fans,
            "W_ups_W": W_ups, "W_misc_W": W_misc, "W_aux_kW": W_loop / 1e3,
            "W_total_kW": W_total / 1e3, "pPUE": pPUE_loop,
            "pPUE_loop": pPUE_loop, "PUE_full": PUE_full,
            "Pcond_bar": co["P"] / 1e5, "Pevap_bar": ev["P"] / 1e5, "COP": COP}


@dataclass
class ColdPlate:
    d_h_mm: float = 0.5
    n_ch: int = 1000
    L_mm: float = 40.0
    W_mm: float = 40.0
    H_mm: float = 40.0
    phi_fin: float = 1.8
    R_wall_K_W: float = 0.004
    h_tp_nom: float = 25000.0

    def area_flow(self):
        return self.n_ch * math.pi * (self.d_h_mm / 1000 / 2) ** 2

    def area_ht(self):
        return self.n_ch * math.pi * (self.d_h_mm / 1000) * (self.L_mm / 1000)


def coldplate_solve(cp_geo, Q_chip_W, mdot, fluid_props, A) -> dict:
    rho_l = fluid_props["rho_l"]; rho_v = fluid_props["rho_v"]
    hfg = fluid_props["hfg"]; mu_l = fluid_props["mu_l"]
    Af = cp_geo.area_flow(); Aht = cp_geo.area_ht()
    G = mdot / Af
    h_tp = cp_geo.h_tp_nom * np.clip((G / 500.0) ** 0.3, 0.4, 2.0)
    Tsat = A.T_evap_C
    Tchip = Tsat + Q_chip_W * (cp_geo.R_wall_K_W + 1.0 / (h_tp * Aht * cp_geo.phi_fin))
    x_out = Q_chip_W / (mdot * hfg) if mdot > 0 else 1.0
    Re = G * cp_geo.d_h_mm / 1000 / mu_l
    f = 64 / Re if Re < 2300 else 0.316 * Re ** -0.25
    dP_l = f * (cp_geo.L_mm / 1000) / (cp_geo.d_h_mm / 1000) * 0.5 * rho_l * (G / rho_l) ** 2
    phi2 = 1 + x_out * (rho_l / rho_v - 1)
    dP = dP_l * phi2
    q_applied = Q_chip_W / Aht
    q_chf = 0.15 * G * hfg * (rho_v / rho_l) ** 0.4
    chf_margin = q_chf / max(q_applied, 1.0)
    return {"Tchip_C": float(Tchip), "x_out": float(x_out), "G": float(G),
            "h_tp": float(h_tp), "dP_kPa": dP / 1e3,
            "q_applied_kW_m2": q_applied / 1e3, "q_chf_kW_m2": q_chf / 1e3,
            "CHF_margin": float(chf_margin)}


def condenser_solve(Q_W, UA, mdot_w, Tw_in_C, pinch=4.0) -> dict:
    C = mdot_w * CPW
    if C <= 0:
        return {"Tcond_C": np.nan, "Tw_out_C": Tw_in_C, "eps": 0, "feasible": False}
    NTU = UA / C
    eps = 1 - math.exp(-NTU)
    Tcond = Tw_in_C + Q_W / (eps * C)
    Tw_out = Tw_in_C + Q_W / C
    feasible = Tcond >= Tw_out + pinch
    return {"Tcond_C": Tcond, "Tw_out_C": Tw_out, "eps": eps, "NTU": NTU,
            "feasible": feasible}


def sizing(A) -> pd.DataFrame:
    ss = steady_state(A)
    ev = sat_props(A.fluid, A.T_evap_C, 1.0)
    co = sat_props(A.fluid, A.T_cond_C, 0.0)
    mdot = ss["mdot"]; rho_l = co["rho_l"]
    Vdot = mdot / rho_l
    dP = (A.dP_coldplate_kPa + A.dP_pipe_kPa) * 1e3
    head_m = dP / (rho_l * 9.81)
    Wpump = ss["Wpump_W"]
    v_liq = 1.5; d_liq = math.sqrt(4 * Vdot / (math.pi * v_liq))
    rho_v = ev["rho_v"]; Vdot_v = mdot / rho_v; v_vap = 10.0
    d_vap = math.sqrt(4 * Vdot_v / (math.pi * v_vap))
    Vdot_w = ss["mdot_w"] / 1000.0; d_w = math.sqrt(4 * Vdot_w / (math.pi * 1.5))
    Cv_V1 = mdot / math.sqrt(rho_l * max(dP, 1e3))
    Cv_V2 = 0.1 * mdot / math.sqrt(rho_l * max(dP, 1e3))
    Cv_3w = Vdot_w / math.sqrt(1.0 * 100e3)
    V_res = Vdot * 30 * 1.3 * 1000
    P_relief = 1.1 * co["P"] / 1e5
    return pd.DataFrame([
        ("Refrigerant mass flow", mdot, "kg/s"),
        ("Refrigerant vol flow", Vdot * 60000, "L/min"),
        ("Pump head", head_m, "m"),
        ("Pump hydraulic power", Wpump, "W"),
        ("Reservoir volume (sized)", V_res, "L"),
        ("Condenser duty", ss["Qcond_kW"], "kW"),
        ("Secondary water flow", ss["mdot_w"], "kg/s"),
        ("Liquid line ID", d_liq * 1000, "mm"),
        ("Vapor line ID", d_vap * 1000, "mm"),
        ("Water line ID", d_w * 1000, "mm"),
        ("V1 lumped Cv", Cv_V1, "SI"),
        ("V2 lumped Cv", Cv_V2, "SI"),
        ("3-way lumped Cv", Cv_3w, "SI"),
        ("Relief set pressure", P_relief, "bar"),
        ("Heat reuse capacity", ss["Qcond_kW"], "kW"),
        ("Pressure sensor range", 1.5 * co["P"] / 1e5, "bar (min FS)"),
        ("Temp sensor range", 100, "degC (min FS)"),
    ], columns=["Item", "Value", "Unit"])
