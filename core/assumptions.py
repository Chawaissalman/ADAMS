"""Engineering assumptions and unit helpers for the two-phase cooling model.

All inputs live in the `Assumptions` dataclass so the Streamlit UI can build
sliders directly from the field metadata. Values are SI unless the name says
otherwise (kW, kPa, L, etc.).
"""
from __future__ import annotations
from dataclasses import dataclass, asdict, fields
import numpy as np

CPW = 4180.0  # water specific heat [J/kg.K]


# ---- unit conversion helpers ------------------------------------------------
def C2K(t):    return np.asarray(t, float) + 273.15
def K2C(t):    return np.asarray(t, float) - 273.15
def bar2Pa(p): return np.asarray(p, float) * 1e5
def Pa2bar(p): return np.asarray(p, float) / 1e5
def lpm2m3s(q): return np.asarray(q, float) / 60000.0
def m3s2lpm(q): return np.asarray(q, float) * 60000.0


@dataclass
class Assumptions:
    # ---- IT load -----------------------------------------------------------
    Q_rack_kW: float = 80.0          # design IT heat load per rack [kW]
    n_chips: int = 12                # cold plates / chips per rack
    # ---- Temperatures (deg C) ---------------------------------------------
    T_chip_target_C: float = 68.0
    T_chip_trip_C:   float = 90.0
    T_evap_C: float = 45.0
    T_cond_C: float = 58.0
    superheat_K: float = 4.0
    subcool_K:   float = 3.0
    # ---- Secondary water ---------------------------------------------------
    Tw_in_free_C: float = 30.0
    Tw_in_hot_C:  float = 40.0
    Tw_out_target_C: float = 50.0
    # ---- Equipment ---------------------------------------------------------
    eta_pump: float = 0.75
    UA_cond_W_K: float = 9000.0
    eff_cond: float = 0.80
    dP_coldplate_kPa: float = 60.0
    dP_pipe_kPa: float = 25.0
    # ---- Reservoir / inventory --------------------------------------------
    V_reservoir_L: float = 25.0
    reservoir_fill_frac0: float = 0.6
    charge_total_kg: float = 18.0
    # ---- Refrigerant -------------------------------------------------------
    fluid: str = "R1336mzz(Z)"
    # ---- Dynamic sim -------------------------------------------------------
    dt_s: float = 0.5
    t_end_s: float = 600.0
    # ---- Ambient -----------------------------------------------------------
    T_amb_C: float = 22.0
    # ---- Facility overheads (for full-PUE accounting) ---------------------
    fan_frac_of_reject: float = 0.015
    ups_loss_frac: float = 0.08
    misc_facility_frac: float = 0.03

    def copy(self, **changes):
        d = asdict(self)
        d.update(changes)
        return Assumptions(**d)


# Slider metadata for the UI: field -> (label, min, max, step, help)
UI_RANGES = {
    "Q_rack_kW":        ("IT load per rack [kW]", 20.0, 200.0, 5.0),
    "n_chips":          ("Chips / cold plates per rack", 4, 24, 1),
    "T_chip_target_C":  ("Chip target temp [°C]", 55.0, 80.0, 1.0),
    "T_chip_trip_C":    ("Chip trip temp [°C]", 80.0, 105.0, 1.0),
    "T_evap_C":         ("Evaporation temp [°C]", 30.0, 55.0, 1.0),
    "T_cond_C":         ("Condensing temp [°C]", 45.0, 70.0, 1.0),
    "superheat_K":      ("Superheat [K]", 1.0, 10.0, 0.5),
    "subcool_K":        ("Subcooling [K]", 1.0, 8.0, 0.5),
    "Tw_in_free_C":     ("Water supply (free cooling) [°C]", 18.0, 38.0, 1.0),
    "Tw_out_target_C":  ("Water return target [°C]", 35.0, 60.0, 1.0),
    "eta_pump":         ("Pump efficiency [-]", 0.35, 0.75, 0.01),
    "UA_cond_W_K":      ("Condenser UA [W/K]", 3000.0, 18000.0, 500.0),
    "dP_coldplate_kPa": ("Cold-plate ΔP [kPa]", 20.0, 120.0, 5.0),
    "dP_pipe_kPa":      ("Pipe ΔP [kPa]", 5.0, 60.0, 5.0),
    "V_reservoir_L":    ("Reservoir volume [L]", 10.0, 60.0, 1.0),
    "charge_total_kg":  ("Refrigerant charge [kg]", 8.0, 40.0, 1.0),
    "fan_frac_of_reject": ("Heat-reject fan frac [-]", 0.0, 0.05, 0.005),
    "ups_loss_frac":    ("UPS+distribution loss frac [-]", 0.0, 0.15, 0.01),
    "misc_facility_frac": ("Misc facility frac [-]", 0.0, 0.10, 0.01),
    "dt_s":             ("Control time step [s]", 0.1, 2.0, 0.1),
    "t_end_s":          ("Sim duration [s]", 120.0, 1200.0, 30.0),
}

FLUID_CHOICES = ["R1336mzz(Z)", "R1234yf", "R1234ze(E)", "R134a", "R513A", "CO2"]

# Help text shown as the (?) tooltip next to each sidebar slider.
UI_HELP = {
    "Q_rack_kW": "Total IT heat the rack dumps into the cooling system. Sets "
                 "everything downstream — flow, pump power, condenser size.",
    "n_chips": "Number of chips / cold plates in the rack. Heat per chip = "
               "rack load ÷ this.",
    "T_chip_target_C": "Temperature you want to hold the chip at. Lower is "
                       "safer for the silicon but needs more cooling effort.",
    "T_chip_trip_C": "Hard safety limit. If the chip reaches this, the system "
                     "trips to protect the hardware.",
    "T_evap_C": "Temperature at which the refrigerant BOILS inside the cold "
                "plate. This is the cold side of the loop — it sets how cold "
                "the chip can be kept (chip ≈ evaporation temp + cold-plate ΔT) "
                "and fixes the low-side pressure. Lower = colder chips but "
                "lower pressure and bigger components.",
    "T_cond_C": "Temperature at which the refrigerant CONDENSES back to liquid "
                "in the condenser. This is the hot side — it must be high "
                "enough to reject heat into the water loop. Setting it above "
                "the water/ambient lets you use free cooling and reuse the "
                "heat; too low forces a chiller on.",
    "superheat_K": "An INPUT target (not automatic). How many degrees above "
                   "boiling the vapor is when it leaves the cold plate. The "
                   "controller maintains it to guarantee ONLY vapor leaves — no "
                   "liquid droplets carried downstream. Typical 2–8 K.",
    "subcool_K": "An INPUT target (not automatic). How many degrees below "
                 "condensing the liquid is leaving the condenser. Maintained to "
                 "guarantee ONLY liquid enters the pump — vapor bubbles cause "
                 "cavitation that destroys pumps. Typical 2–5 K.",
    "Tw_in_free_C": "Temperature of the cold water supplied to the condenser. "
                    "Warmer supply enables more free cooling (lower PUE) — until "
                    "it's too warm and forces the chiller on.",
    "Tw_out_target_C": "Target temperature of the warm water leaving. Must stay "
                       "above the supply (water is heated, not cooled). A higher "
                       "value means less water flow and makes the heat reusable.",
    "eta_pump": "Overall pump efficiency (hydraulic × motor). Higher = less "
                "pump power for the same flow.",
    "UA_cond_W_K": "Condenser thermal conductance (size × heat-transfer "
                   "coefficient). Bigger UA rejects heat at a smaller "
                   "temperature difference.",
    "dP_coldplate_kPa": "Pressure drop the refrigerant loses flowing through "
                        "the cold plate — the pump must make this up.",
    "dP_pipe_kPa": "Pressure drop in the connecting pipework.",
    "V_reservoir_L": "Liquid reservoir size — buffers inventory and rides out "
                     "transients.",
    "charge_total_kg": "Total refrigerant mass in the loop + reservoir.",
    "fan_frac_of_reject": "Heat-rejection fan power as a fraction of heat "
                          "rejected — part of the full-facility PUE.",
    "ups_loss_frac": "UPS + power-distribution losses as a fraction of IT load "
                     "(~8% typical). Part of full-facility PUE.",
    "misc_facility_frac": "Lighting, controls, non-IT HVAC as a fraction of IT "
                          "load (~3% typical).",
    "dt_s": "Control scan / integration time step for the dynamic simulation.",
    "t_end_s": "How long the dynamic simulation runs.",
}


def sanity_check(A):
    """Return (warnings, errors) lists of human-readable strings.

    Errors are physically impossible / will break the model; warnings are
    questionable but allowed. The UI surfaces both.
    """
    warns, errs = [], []
    # water loop: return must be warmer than supply (heat is added to it)
    if A.Tw_out_target_C <= A.Tw_in_free_C:
        errs.append(
            f"Water return target ({A.Tw_out_target_C:.0f}°C) must be higher "
            f"than supply ({A.Tw_in_free_C:.0f}°C) — the water is heated by the "
            f"condenser. Raise the return target or lower the supply.")
    elif A.Tw_out_target_C - A.Tw_in_free_C < 3:
        warns.append("Water ΔT < 3°C means very high water flow; consider a "
                     "wider supply-return spread.")
    # condensing must sit above evaporation (heat flows hot->cold)
    if A.T_cond_C <= A.T_evap_C:
        errs.append(f"Condensing temp ({A.T_cond_C:.0f}°C) must exceed "
                    f"evaporation temp ({A.T_evap_C:.0f}°C).")
    elif A.T_cond_C - A.T_evap_C < 5:
        warns.append("Cond–evap lift < 5°C is optimistic; condenser and lines "
                     "need to be generously sized.")
    # chip target should be above evaporation (there is a cold-plate ΔT)
    if A.T_chip_target_C <= A.T_evap_C:
        warns.append("Chip target at/below evaporation temp implies zero or "
                     "negative cold-plate ΔT — not physical.")
    # trip must be above target
    if A.T_chip_trip_C <= A.T_chip_target_C:
        errs.append("Chip trip temp must be above the chip target temp.")
    # condensing must be rejectable to the water (needs Tcond > water return)
    if A.T_cond_C <= A.Tw_out_target_C:
        warns.append(f"Condensing temp ({A.T_cond_C:.0f}°C) is not above the "
                     f"water return ({A.Tw_out_target_C:.0f}°C); a chiller will "
                     f"be required to reject heat.")
    # pump efficiency sanity
    if not (0.3 <= A.eta_pump <= 0.85):
        warns.append("Pump efficiency outside the typical 0.3–0.85 range.")
    # charge vs reservoir
    if A.charge_total_kg < A.V_reservoir_L / 1000 * 600:
        warns.append("Refrigerant charge looks low for the loop + reservoir "
                     "volume; check inventory.")
    return warns, errs
