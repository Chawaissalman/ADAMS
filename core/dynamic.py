"""Dynamic lumped-capacitance plant + closed-loop simulator + scenario builder.

The plant is a 6-state lumped ODE integrated with scipy solve_ivp between
0.5 s PLC scans. The scenario builder lets the UI compose arbitrary cases:
load steps/ramps, water-temperature changes, and timed fault injections.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from dataclasses import dataclass
from scipy.integrate import solve_ivp

from .fluids import sat_props
from .control import PLCController, Supervisor, State


@dataclass
class PlantParams:
    C_chip: float = 6000.0
    C_wall: float = 12000.0
    C_evap: float = 8000.0
    C_cond: float = 20000.0
    C_water: float = 30000.0
    R_cw: float = 2.0e-4
    R_wr: float = 9.0e-5
    Q_nom_m3s: float = 1.6e-3
    UA_cond: float = 9000.0
    hfg: float = 140e3
    rho_l: float = 1050.0


def make_props(A):
    ev = sat_props(A.fluid, A.T_evap_C, 1.0)
    co = sat_props(A.fluid, A.T_cond_C, 0.0)
    return ev, co


def plant_rhs(t, y, cmd, env, P, A):
    """Lumped dynamic plant RHS. States: Tchip,Twall,Tevap,Tcond,mres,Twout."""
    Tchip, Twall, Tevap, Tcond, mres, Twout = y
    Q_IT = env["Q_IT"](t) * 1e3
    Tw_in = env["Tw_in"](t)
    derate = float(np.clip(1.0 - 0.015 * (Tcond - A.T_cond_C), 0.4, 1.0))
    mdot = P.rho_l * P.Q_nom_m3s * np.clip(cmd["pump"], 0, 1.2) * derate
    mdot = max(mdot, 1e-3)
    q_chip_wall = (Tchip - Twall) / P.R_cw
    q_wall_ref = max((Twall - Tevap) / P.R_wr, 0.0)
    x_out = np.clip(q_wall_ref / (mdot * P.hfg), 0.02, 1.3)
    mdot_w = max(0.3 + 2.2 * cmd["water"], 0.05)
    eps = 1 - math.exp(-P.UA_cond / (mdot_w * 4180.0))
    Q_cond_water = eps * mdot_w * 4180.0 * max(Tcond - Tw_in, 0.0)
    Q_chiller = cmd.get("chiller", 0.0) * A.Q_rack_kW * 1e3
    Q_transport = q_wall_ref
    dTchip = (Q_IT - q_chip_wall) / P.C_chip
    dTwall = (q_chip_wall - q_wall_ref) / P.C_wall
    dTevap = (q_wall_ref - Q_transport - 50.0 * mdot * (Tevap - (Tcond - 8.0))) / P.C_evap
    dTcond = (Q_transport - Q_cond_water - Q_chiller) / P.C_cond
    m_V1 = mdot * 0.99
    m_V2 = (cmd["V2"] - 0.3) * 0.06
    dmres = m_V1 - mdot + m_V2
    dTwout = (Q_cond_water - mdot_w * 4180.0 * (Twout - Tw_in)) / P.C_water
    return [dTchip, dTwall, dTevap, dTcond, dmres, dTwout], dict(
        mdot=mdot, x_out=x_out, mdot_w=mdot_w, Qcond=Q_cond_water,
        Qchiller=Q_chiller)


def simulate_scn(A, scn, progress=None):
    """Closed-loop sim with physical fault injection. Returns a log DataFrame.

    scn keys: env={"Q_IT":fn(t),"Tw_in":fn(t)}, faults=fn(t,pv)->list,
              reuse_demand=bool, t_end=float
    progress: optional callback(frac) for UI progress bars.
    """
    P = PlantParams(UA_cond=A.UA_cond_W_K)
    ev, co = make_props(A)
    if ev["ok"]:
        P.hfg = ev["hfg"]; P.rho_l = co["rho_l"]
    dt = A.dt_s
    t_end = scn.get("t_end", A.t_end_s)
    plc = PLCController(A); sup = Supervisor(A); plc.start_cmd = True
    m_full = A.V_reservoir_L / 1000 * P.rho_l
    y = [A.T_chip_target_C, A.T_evap_C + 8, A.T_evap_C, A.T_cond_C,
         A.reservoir_fill_frac0 * m_full, A.Tw_out_target_C]
    log = []; t = 0.0; pump_failed = False
    n_steps = max(int(t_end / dt), 1)
    step_i = 0
    while t < t_end - 1e-9:
        Tchip, Twall, Tevap, Tcond, mres, Twout = y
        flist = scn["faults"](t, None)
        if "lowlevel_event" in flist:
            mres = max(mres - 0.02 * m_full, 0.0); y[4] = mres
        if "pump_fault" in flist:
            pump_failed = True
        water_failed = "water_flow_fail" in flist
        highpress = "highpress_event" in flist
        Pevap = sat_props(A.fluid, float(np.clip(Tevap, -5, 80)), 1.0)
        Pcond = sat_props(A.fluid, float(np.clip(Tcond, 0, 85)), 0.0)
        level = 100 * mres / m_full
        _, aux = plant_rhs(t, y, plc.cmd, scn["env"], P, A)
        Tchip_meas = Tchip
        if "sensor:Tchip_inject" in flist:
            Tchip_meas = 999.0
        pv = dict(Tchip=Tchip_meas, Twall=Twall, Tevap=Tevap, Tcond=Tcond,
                  Pevap=Pevap["P"] / 1e5 if Pevap["ok"] else 12.0,
                  Pcond=Pcond["P"] / 1e5 if Pcond["ok"] else 16.0,
                  level=level, mdot=aux["mdot"], x_out=aux["x_out"],
                  Tw_in=scn["env"]["Tw_in"](t), Tw_out=Twout,
                  reuse_demand=scn.get("reuse_demand", False), Tchip_last=Tchip)
        if highpress:
            pv["Pcond"] = 24.0          # blocked condenser / overcharge spike
        faults = [f for f in flist if not f.startswith("sensor:Tchip")]
        if pump_failed:
            faults = faults + ["pump_fault"]
        if water_failed:
            faults = faults + ["water_flow_fail"]
        pv_c, bad = plc.validate(pv)
        for b in bad:
            faults = faults + [f"sensor:{b}"]
        sreq = sup.optimize(pv_c, t)
        plc.step_state(pv_c, faults, sreq, dt)
        cmd = plc.actuate(pv_c, sreq, dt)
        if pump_failed:
            cmd["pump"] = 0.0
        if water_failed:
            cmd["water"] = 0.0          # secondary water pump lost
        sol = solve_ivp(lambda tt, yy: plant_rhs(tt, yy, cmd, scn["env"], P, A)[0],
                        (t, t + dt), y, method="RK45", max_step=dt,
                        rtol=1e-4, atol=1e-6)
        y = list(sol.y[:, -1]); y[4] = float(np.clip(y[4], 0, m_full))
        log.append(dict(t=t, state=plc.state.name, Tchip=Tchip, Tevap=Tevap,
                        Tcond=Tcond, Pcond=pv["Pcond"], level=level,
                        mdot=aux["mdot"], x_out=aux["x_out"], Tw_in=pv["Tw_in"],
                        Tw_out=Twout, cmd_pump=cmd["pump"], cmd_V1=cmd["V1"],
                        cmd_V2=cmd["V2"], cmd_water=cmd["water"],
                        cmd_chiller=cmd["chiller"], n_alarms=len(plc.alarms),
                        n_trips=len(plc.trips), alarms=";".join(plc.alarms),
                        trips=";".join(plc.trips)))
        t += dt
        step_i += 1
        if progress and step_i % 20 == 0:
            progress(min(step_i / n_steps, 1.0))
    if progress:
        progress(1.0)
    return pd.DataFrame(log)


# ---------------------------------------------------------------------------
# Scenario builder: turn UI parameters into an scn dict
# ---------------------------------------------------------------------------
def _step(t, t0, v0, v1):
    return v0 if t < t0 else v1


def _ramp(t, t0, t1, v0, v1):
    if t <= t0:
        return v0
    if t >= t1:
        return v1
    return v0 + (v1 - v0) * (t - t0) / (t1 - t0)


def build_scenario(load_mode="constant", Q0=80.0, Q1=80.0, t_change=150.0,
                   ramp_end=None, water_mode="constant", Tw0=30.0, Tw1=30.0,
                   tw_change=150.0, fault=None, fault_start=200.0,
                   fault_end=260.0, reuse_demand=False, t_end=400.0):
    """Compose a scenario from UI controls.

    load_mode: 'constant' | 'step' | 'ramp'
    water_mode: 'constant' | 'step'
    fault: None | 'lowlevel' | 'pumpfail' | 'sensorfail'
    """
    if load_mode == "constant":
        Q_IT = lambda t: Q0
    elif load_mode == "step":
        Q_IT = lambda t: _step(t, t_change, Q0, Q1)
    else:  # ramp
        re = ramp_end if ramp_end else t_change + 100
        Q_IT = lambda t: _ramp(t, t_change, re, Q0, Q1)

    if water_mode == "constant":
        Tw_in = lambda t: Tw0
    else:
        Tw_in = lambda t: _step(t, tw_change, Tw0, Tw1)

    if fault == "lowlevel":
        faults = lambda t, pv: (["lowlevel_event"] if fault_start < t < fault_end else [])
    elif fault == "pumpfail":
        faults = lambda t, pv: (["pump_fault"] if t >= fault_start else [])
    elif fault == "sensorfail":
        faults = lambda t, pv: (["sensor:Tchip_inject"] if fault_start < t < fault_end else [])
    elif fault == "highpress":
        faults = lambda t, pv: (["highpress_event"] if t >= fault_start else [])
    elif fault == "waterfail":
        faults = lambda t, pv: (["water_flow_fail"] if t >= fault_start else [])
    else:
        faults = lambda t, pv: []

    return dict(env={"Q_IT": Q_IT, "Tw_in": Tw_in}, faults=faults,
                reuse_demand=reuse_demand, t_end=t_end)


# Pre-built canonical scenarios (match the notebook's 8)
def canonical_scenarios():
    return {
        "1 - Normal startup": build_scenario(t_end=240),
        "2 - Load step 40→80 kW": build_scenario(load_mode="step", Q0=40, Q1=80,
                                                 t_change=150, t_end=400),
        "3 - Warm water → chiller": build_scenario(water_mode="step", Tw0=28, Tw1=38,
                                                   tw_change=150, t_end=500),
        "4 - Heat-reuse mode": build_scenario(reuse_demand=True, t_end=400),
        "5 - Low reservoir level": build_scenario(fault="lowlevel", fault_start=200,
                                                  fault_end=260, t_end=400),
        "6 - Pump failure": build_scenario(fault="pumpfail", fault_start=250, t_end=360),
        "7 - Overload chip trip": build_scenario(load_mode="step", Q0=80, Q1=140,
                                                 t_change=250, t_end=420),
        "8 - Sensor fault": build_scenario(fault="sensorfail", fault_start=200,
                                           fault_end=240, t_end=400),
        "9 - High-pressure event": build_scenario(fault="highpress",
                                                  fault_start=200, t_end=360),
        "10 - Water-loop failure": build_scenario(fault="waterfail",
                                                  fault_start=200, t_end=360),
    }


def scenario_outcome(df):
    """Summarize a run: end state, peak chip temp, trips."""
    return dict(end_state=df.state.iloc[-1],
                peak_Tchip=df.Tchip.max(),
                min_level=df.level.min(),
                total_trips=int(df.n_trips.max()),
                total_alarms=int(df.n_alarms.max()))
