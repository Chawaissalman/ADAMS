"""Economics (CAPEX/PBP/NPV), business-as-usual comparison, campus scale-up.

Cost basis from 2026 industry literature (clearly editable):
- advanced air / RDHx  ~$1,800-3,200/kW
- direct-to-chip liquid ~$3,500-5,000/kW
- air PUE ~1.45-1.60 vs liquid full-facility ~1.10-1.18
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict


@dataclass
class Econ:
    elec_price: float = 0.12        # $/kWh
    discount_rate: float = 0.08
    project_years: int = 10
    hours: int = 8760
    capex_air_perkW: float = 2500.0
    capex_2ph_perkW: float = 4200.0
    heat_price_perMWh: float = 25.0
    heat_reuse_frac: float = 0.5
    om_frac: float = 0.04
    redundancy_factor: float = 1.20

    def copy(self, **changes):
        d = asdict(self); d.update(changes); return Econ(**d)


def economics(IT_kW, E, pPUE_2ph, pPUE_air=1.55, reuse_MW_th=0.0, label=""):
    IT_kW = float(IT_kW)
    cool_air = (pPUE_air - 1) * IT_kW * E.hours / 1000
    cool_2ph = (pPUE_2ph - 1) * IT_kW * E.hours / 1000
    energy_save = (cool_air - cool_2ph) * 1000 * E.elec_price
    reuse_MWh = reuse_MW_th * E.hours * E.heat_reuse_frac
    reuse_rev = reuse_MWh * E.heat_price_perMWh
    capex_2ph = E.capex_2ph_perkW * IT_kW * E.redundancy_factor
    capex_air = E.capex_air_perkW * IT_kW
    capex_delta = capex_2ph - capex_air
    om = E.om_frac * capex_2ph
    annual_net = energy_save + reuse_rev - om
    pbp = capex_delta / annual_net if annual_net > 0 else float("inf")
    npv = -capex_delta
    cfs = [-capex_delta]
    for y in range(1, E.project_years + 1):
        npv += annual_net / ((1 + E.discount_rate) ** y)
        cfs.append(annual_net)
    return dict(label=label, capex_2ph=capex_2ph, capex_air=capex_air,
                capex_delta=capex_delta, energy_save=energy_save,
                reuse_rev=reuse_rev, om=om, annual_net=annual_net,
                pbp=pbp, npv=npv, cfs=cfs)


def irr(cashflows, lo=-0.9, hi=2.0, tol=1e-6):
    """Internal rate of return via bisection on NPV(rate)=0. None if no sign change."""
    def npv_at(r):
        return sum(cf / ((1 + r) ** i) for i, cf in enumerate(cashflows))
    f_lo, f_hi = npv_at(lo), npv_at(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = npv_at(mid)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi = mid; f_hi = f_mid
        else:
            lo = mid; f_lo = f_mid
    return (lo + hi) / 2


def yearly_table(r, E):
    """Year-by-year cash-flow / cumulative table for display."""
    rows = []
    cum = 0.0
    cum_disc = 0.0
    for y, cf in enumerate(r["cfs"]):
        disc = cf / ((1 + E.discount_rate) ** y) if y > 0 else cf
        cum += cf
        cum_disc += disc
        rows.append({"Year": y, "Cash flow $": cf, "Discounted $": disc,
                     "Cumulative $": cum, "Cumulative disc. $": cum_disc})
    return pd.DataFrame(rows)


def tco(r, E, IT_kW, pPUE_2ph, pPUE_air=1.55):
    """Total cost of ownership over project life for both options."""
    energy_air = (pPUE_air * IT_kW) * E.hours / 1000 * 1000 * E.elec_price
    energy_2ph = (pPUE_2ph * IT_kW) * E.hours / 1000 * 1000 * E.elec_price
    yrs = E.project_years
    tco_air = r["capex_air"] + energy_air * yrs
    tco_2ph = r["capex_2ph"] + (energy_2ph + r["om"]) * yrs - r["reuse_rev"] * yrs
    return dict(tco_air=tco_air, tco_2ph=tco_2ph)


def cumulative_cashflow(r, E):
    cum = []; tot = 0.0
    for y, cf in enumerate(r["cfs"]):
        disc = cf / ((1 + E.discount_rate) ** y) if y > 0 else cf
        tot += disc; cum.append(tot)
    return cum


def npv_tornado(IT_kW, E, pPUE_2ph, reuse_MW_th, swing=0.30):
    """Vary key drivers +/- swing, return list of (name, lo, hi) NPVs in $M."""
    base = economics(IT_kW, E, pPUE_2ph, reuse_MW_th=reuse_MW_th)["npv"]
    drivers = {"Electricity price": "elec_price",
               "Heat sale price": "heat_price_perMWh",
               "Two-phase CAPEX": "capex_2ph_perkW",
               "Discount rate": "discount_rate",
               "Reuse fraction": "heat_reuse_frac",
               "Redundancy factor": "redundancy_factor"}
    rows = []
    for name, attr in drivers.items():
        b = getattr(E, attr); res = []
        for f in (1 - swing, 1 + swing):
            E2 = E.copy(**{attr: b * f})
            res.append(economics(IT_kW, E2, pPUE_2ph, reuse_MW_th=reuse_MW_th)["npv"] / 1e6)
        rows.append((name, res[0], res[1]))
    rows.sort(key=lambda t: abs(t[2] - t[1]))
    return base / 1e6, rows


def bau_comparison(A, ss, elec=0.12, pue_air=1.55, pue_sp=1.20):
    """Business-as-usual table on full-facility PUE (air/single-phase editable)."""
    Q = A.Q_rack_kW; hours = 8760
    df = pd.DataFrame([
        ("Air (CRAC/CRAH)", pue_air, 25, 0.30, "fans+chiller heavy; density limited"),
        ("Single-phase DLC", pue_sp, 80, 0.55, "high flow, some chiller tempering"),
        ("Two-phase (model)", ss["PUE_full"], 120, 0.80, "latent transport, low pump power"),
    ], columns=["Technology", "PUE", "MaxDensity_kW", "FreeCoolFrac", "Note"])
    df["CoolingOverhead_kW"] = (df["PUE"] - 1.0) * Q
    df["CoolingMWh_yr"] = df["CoolingOverhead_kW"] * hours / 1000
    df["CoolingCost_kUSD_yr"] = df["CoolingMWh_yr"] * 1000 * elec / 1000
    return df


CLIMATE_PROFILES = {
    "Nordic (Stockholm)": dict(free_frac=0.92, dh_demand=0.85, t_ambient=8),
    "Continental (Frankfurt)": dict(free_frac=0.78, dh_demand=0.70, t_ambient=11),
    "Temperate (Virginia)": dict(free_frac=0.62, dh_demand=0.30, t_ambient=14),
    "Hot-dry (Phoenix)": dict(free_frac=0.40, dh_demand=0.05, t_ambient=24),
    "Tropical (Singapore)": dict(free_frac=0.20, dh_demand=0.00, t_ambient=28),
}


def climate_analysis(A, ss, campus_MW, climate_key):
    """Climate-dependent free-cooling fraction, chiller energy, heat-offtake fit."""
    prof = CLIMATE_PROFILES[climate_key]
    Q_reject_MW = campus_MW * ss["PUE_full"]
    free_frac = prof["free_frac"]
    chiller_hours = (1 - free_frac) * 8760
    chiller_MWh = (1 - free_frac) * Q_reject_MW * 8760 / 4.5
    dh_uptake = prof["dh_demand"]
    Tw_out = A.Tw_out_target_C
    grade_frac = 0.85 if Tw_out >= 60 else (0.65 if Tw_out >= 45 else 0.35)
    Q_offtake_MW = Q_reject_MW * grade_frac * dh_uptake
    return dict(prof=prof, Q_reject_MW=Q_reject_MW, free_frac=free_frac,
                chiller_hours=chiller_hours, chiller_MWh=chiller_MWh,
                Q_offtake_MW=Q_offtake_MW, grade_frac=grade_frac,
                dh_uptake=dh_uptake)


def buildout_analysis(A, ss, target_MW, years=5, capex_2ph_perkW=4200,
                      redundancy=1.20, water_l_per_kWh=1.8, grid_kgco2_kwh=0.35):
    """Multi-year phased build: capacity, CAPEX, carbon and water by year."""
    per_year_MW = target_MW / years
    rows = []
    cum_MW = 0.0
    for y in range(1, years + 1):
        cum_MW += per_year_MW
        capex_y = per_year_MW * 1000 * capex_2ph_perkW * redundancy
        it_mwh = cum_MW * 8760
        facility_mwh = it_mwh * ss["PUE_full"]
        water_m3 = facility_mwh * 1000 * water_l_per_kWh * 0.15 / 1000
        co2_kt = facility_mwh * grid_kgco2_kwh / 1e3
        rows.append({"Year": y, "Added MW": per_year_MW, "Cumulative MW": cum_MW,
                     "CAPEX $M": capex_y / 1e6, "Facility GWh/yr": facility_mwh / 1000,
                     "Water Mm³/yr": water_m3 / 1e6, "Grid CO₂ kt/yr": co2_kt})
    return pd.DataFrame(rows)


def campus_scaleup(A, ss, campus_MW=100.0):
    rack_kW = A.Q_rack_kW
    n_racks = campus_MW * 1000 / rack_kW
    Q_reject_MW = campus_MW * ss["PUE_full"]
    Tw_out = A.Tw_out_target_C
    if Tw_out >= 60:
        rec_frac, grade = 0.85, "high (district heat direct)"
    elif Tw_out >= 45:
        rec_frac, grade = 0.65, "medium (heat-pump boost to DH)"
    else:
        rec_frac, grade = 0.35, "low (pre-heat / process only)"
    Q_recover_MW = Q_reject_MW * rec_frac
    homes = Q_recover_MW * 200
    Q_abs_cool_MW = Q_recover_MW * 0.7
    heat_GWh = Q_recover_MW * 8760 / 1000
    co2_avoided_kt = heat_GWh * 1000 * 0.20 / 1000
    tbl = pd.DataFrame([
        ("IT load", campus_MW, "MW"),
        ("Number of racks", n_racks, "racks"),
        ("Total heat rejected", Q_reject_MW, "MW_th"),
        ("Heat grade", Tw_out, "°C water-out"),
        ("Recoverable fraction", rec_frac * 100, "%"),
        ("Recoverable waste heat", Q_recover_MW, "MW_th"),
        ("Homes heated (district heat)", homes, "homes"),
        ("Absorption cooling produced", Q_abs_cool_MW, "MW_cool"),
        ("Recoverable heat per year", heat_GWh, "GWh_th/yr"),
        ("CO2 avoided (vs gas heat)", co2_avoided_kt, "kt/yr"),
    ], columns=["Metric", "Value", "Unit"])
    return tbl, dict(n_racks=n_racks, Q_reject_MW=Q_reject_MW,
                     Q_recover_MW=Q_recover_MW, grade=grade,
                     co2_avoided_kt=co2_avoided_kt, heat_GWh=heat_GWh)
